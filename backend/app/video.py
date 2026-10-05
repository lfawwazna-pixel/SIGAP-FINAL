"""Shared raw video and matching YOLO/ByteTrack frames, keyed by camera session."""
import asyncio
from collections import deque
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, Request, Response
from imageio_ffmpeg import get_ffmpeg_exe
from backend.app.auth import require_operator, error
from backend.app.mutations import require_mutation
from contracts.models import Direction
from contracts.video import VideoCommand, VideoStatus, VideoChannelView, VideoCalibration, TrackingView
from backend.app.vision import VisionWorker


class VideoChannel:
    def __init__(self, direction, directory, live_url='', vision=None):
        self.direction, self.directory, self.live_url = direction, directory, live_url
        self.lock = asyncio.Lock()
        self.source = 'none'
        self.session = uuid4()
        self.state, self.message, self.label = 'empty', 'Pilih rekaman atau kamera.', 'Belum ada sumber'
        self.path = None
        self.frame, self.frame_id, self.received = None, 0, None
        self.position = 0.0
        self.calibration = None
        self.task = self.process = None
        self.vision = vision
        self.tracking_task = None
        self.tracked_frame = None
        self.tracked_id = 0
        self.tracked_session = self.session
        self.tracked_at = self.tracked_position = None
        self.tracks = []
        self.processing_times = deque(maxlen=20)
        self.tracking_times = deque(maxlen=20)
        self.device = None
        saved = directory/f'{direction}.json'
        if saved.exists():
            try:
                info = json.loads(saved.read_text(encoding='utf-8'))
                path = (directory/info.get('file', '')).resolve()
                if info.get('source') == 'live' and live_url:
                    self.source, self.label, self.state = 'live', f'CCTV {direction}', 'ready'
                    self.calibration = VideoCalibration.model_validate(info['calibration']) if info.get('calibration') else None
                elif info.get('source', 'recording') == 'recording' and path.parent == directory.resolve() and path.suffix == '.mp4' and path.is_file():
                    self.source, self.path, self.label, self.state = 'recording', path, info['label'], 'ready'
                    self.calibration = VideoCalibration.model_validate(info['calibration']) if info.get('calibration') else None
            except (ValueError, KeyError, OSError):
                pass

    def reset_tracking(self):
        self.tracked_frame = None
        self.tracked_id = 0
        self.tracked_session = self.session
        self.tracked_at = self.tracked_position = None
        self.tracks = []
        self.processing_times.clear()
        self.tracking_times.clear()

    async def track(self, jpeg, frame_id, session, position, captured):
        result = await self.vision.infer(self.direction, session, frame_id, jpeg, captured)
        if result is None or self.session != session or self.state not in ('playing', 'paused'):
            return
        self.tracked_frame, self.tracked_id = result['jpeg'], frame_id
        self.tracked_session, self.tracked_at, self.tracked_position = session, captured, position
        self.tracks, self.device = result['tracks'], result['device']
        if self.tracking_times:
            # Exclude the initial model warmup from the displayed throughput.
            self.processing_times.append(result['processing_ms'])
        self.tracking_times.append(time.monotonic())

    def persist(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        value = dict(source=self.source, file=self.path.name if self.path else '', label=self.label,
            calibration=self.calibration.model_dump() if self.calibration else None)
        target = self.directory/f'{self.direction}.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(value), encoding='utf-8')
        temp.replace(target)

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None
        if self.tracking_task:
            self.tracking_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.tracking_task
            self.tracking_task = None

    async def decode(self):
        offset = self.position
        decoded = 0
        self.state, self.message = 'connecting', 'Menghubungkan decoder video.'
        args = [get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-threads', '1']
        if self.source == 'recording':
            args += ['-re', '-ss', str(offset), '-protocol_whitelist', 'file,pipe', '-i', str(self.path)]
        else:
            if self.live_url.startswith('rtsp://'):
                args += ['-rtsp_transport', 'tcp']
            args += ['-i', self.live_url]
        args += ['-an', '-vf', 'fps=5,scale=640:-2', '-threads', '1', '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '5', 'pipe:1']
        try:
            kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            self.process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, **kwargs)
            buffer = b''
            while True:
                chunk = await asyncio.wait_for(self.process.stdout.read(65536), 15)
                if not chunk:
                    code = await self.process.wait()
                    self.state = 'ended' if self.source == 'recording' and decoded and code == 0 else 'error'
                    self.message = 'Rekaman selesai; tidak diputar ulang otomatis.' if self.state == 'ended' else 'Video tidak dapat dibaca atau koneksi terputus.'
                    self.frame = None
                    return
                buffer += chunk
                if len(buffer) > 4_000_000:
                    raise ValueError('Frame limit exceeded')
                while (end := buffer.find(b'\xff\xd9')) >= 0:
                    jpeg, buffer = buffer[:end+2], buffer[end+2:]
                    if not jpeg.startswith(b'\xff\xd8'):
                        raise ValueError('Invalid frame')
                    decoded += 1
                    self.frame_id += 1
                    self.frame, self.received = jpeg, time.monotonic()
                    self.position = offset+decoded/5
                    self.state, self.message = 'playing', 'Video sumber bersama berjalan.'
                    if self.vision and self.vision.enabled and (not self.tracking_task or self.tracking_task.done()):
                        self.tracking_task = asyncio.create_task(self.track(jpeg, self.frame_id, self.session,
                            self.position, self.received), name=f'tracking-{self.direction}')
        except asyncio.CancelledError:
            raise
        except Exception:
            self.state, self.message, self.frame = 'error', 'Decoder gagal atau frame berhenti diterima. Hubungkan ulang sumber.', None
        finally:
            if self.process and self.process.returncode is None:
                self.process.kill()
                await self.process.wait()
            self.process = None

    def view(self):
        age = max(0, time.monotonic()-self.received) if self.received else None
        state = 'stale' if self.state == 'playing' and age is not None and age > 3 else self.state
        tracking = self.tracking_view()
        return VideoChannelView(direction=self.direction, source=self.source, source_session=self.session,
            state=state, label=self.label, frame_id=self.frame_id, media_seconds=self.position if self.source == 'recording' else None,
            frame_age_seconds=age, live_configured=bool(self.live_url), calibration=self.calibration,
            detection_ready=bool(tracking and tracking.state == 'tracking'), tracking=tracking,
            message='Frame video tidak mutakhir.' if state == 'stale' else self.message)

    def tracking_view(self):
        if not self.vision:
            return None
        age = max(0, time.monotonic() - self.tracked_at) if self.tracked_at else None
        fresh = self.tracked_session == self.session and self.state in ('playing', 'paused') and age is not None and (age <= 3 if self.state == 'playing' else self.tracked_id == self.frame_id)
        state = 'disabled' if not self.vision.enabled else 'tracking' if fresh else 'error' if self.vision.retry_after > time.monotonic() else 'stale' if self.tracked_at else 'warming'
        fps = 1000 / (sum(self.processing_times) / len(self.processing_times)) if self.processing_times else None
        times = self.tracking_times
        observed = (len(times)-1)/(times[-1]-times[0]) if len(times)>1 and times[-1]>times[0] else None
        return TrackingView(state=state, source_session=self.session, frame_id=self.tracked_id,
            age_seconds=age, processing_fps=round(fps, 2) if fps else None,
            observed_fps=round(observed, 2) if observed else None, device=self.device,
            tracks=self.tracks if fresh else [], message=self.vision.message)


class VideoHub:
    def __init__(self, settings):
        directory = Path(settings.sigap_media_dir).resolve()
        self.vision = VisionWorker(settings)
        self.channels = {d: VideoChannel(d, directory, settings.sigap_camera_urls.get(d, '').get_secret_value()
            if d in settings.sigap_camera_urls else '', self.vision) for d in 'UTSB'}

    async def stop(self):
        for channel in self.channels.values():
            await channel.stop()
        await self.vision.close()

    def snapshot(self):
        return VideoStatus(channels=[c.view() for c in self.channels.values()])


router = APIRouter(prefix='/api/video', tags=['Video bersama'])

@router.get('', response_model=VideoStatus, dependencies=[Depends(require_operator)])
async def status(request: Request):
    return request.app.state.video.snapshot()

@router.get('/{direction}/frame', dependencies=[Depends(require_operator)])
async def frame(direction: Direction, request: Request, overlay: bool = False):
    channel = request.app.state.video.channels[direction]
    if channel.view().state not in ('playing', 'paused') or channel.frame is None:
        raise error(503, 'FRAME_UNAVAILABLE', channel.view().message)
    detected = overlay and channel.view().detection_ready and channel.tracked_frame is not None
    return Response(channel.tracked_frame if detected else channel.frame, media_type='image/jpeg', headers={
        'X-Source-Session': str(channel.session), 'X-Frame-Id': str(channel.tracked_id if detected else channel.frame_id),
        'X-Media-Seconds': str(channel.tracked_position if detected else channel.position),
        'X-Tracking': 'ByteTrack' if detected else 'none', 'Cache-Control': 'private, no-store'})

@router.post('/{direction}/upload', response_model=VideoChannelView, dependencies=[Depends(require_mutation)])
async def upload(direction: Direction, expected_session: UUID, request: Request):
    channel = request.app.state.video.channels[direction]
    async with channel.lock:
        if expected_session != channel.session:
            raise error(409, 'SOURCE_CHANGED', 'Sumber sudah berubah. Muat keadaan terbaru.')
        channel.directory.mkdir(parents=True, exist_ok=True)
        target = channel.directory/f'{uuid4()}.mp4'
        count, header = 0, b''
        try:
            with target.open('xb') as output:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > 256*1024*1024:
                        raise error(413, 'VIDEO_TOO_LARGE', 'Ukuran video maksimal 256 MB.')
                    header = (header+chunk)[:32]
                    await asyncio.to_thread(output.write, chunk)
            if count < 32 or header[4:8] != b'ftyp':
                raise error(422, 'INVALID_VIDEO', 'Gunakan file MP4 yang valid.')
            await channel.stop()
            old = channel.path
            channel.source, channel.path, channel.label = 'recording', target, f'Rekaman {direction}'
            channel.session, channel.frame_id, channel.frame = uuid4(), 0, None
            channel.reset_tracking()
            channel.position, channel.received, channel.calibration = 0, None, None
            channel.state, channel.message = 'ready', 'Rekaman siap. Jalankan untuk melihat video.'
            channel.persist()
            if old and old.parent == channel.directory and old != target:
                old.unlink(missing_ok=True)
        except BaseException:
            if channel.path != target:
                target.unlink(missing_ok=True)
            raise
    return channel.view()

@router.post('/{direction}/commands', response_model=VideoChannelView, dependencies=[Depends(require_mutation)])
async def command(direction: Direction, payload: VideoCommand, request: Request):
    channel = request.app.state.video.channels[direction]
    async with channel.lock:
        if payload.expected_session != channel.session:
            raise error(409, 'SOURCE_CHANGED', 'Sumber sudah berubah. Muat keadaan terbaru.')
        if payload.action == 'calibrate':
            if channel.source == 'none':
                raise error(409, 'NO_SOURCE', 'Pilih sumber video dahulu.')
            channel.calibration = payload.calibration
            channel.persist()
        elif payload.action == 'pause':
            if channel.source != 'recording':
                raise error(409, 'LIVE_CLOCK', 'Kamera langsung mengikuti waktu sumber.')
            await channel.stop()
            channel.state, channel.message = 'paused', 'Rekaman dijeda; pengamatan tidak dianggap data baru.'
        else:
            if payload.action == 'use_live':
                if not channel.live_url:
                    raise error(409, 'NO_CAMERA', 'Kamera langsung belum dikonfigurasi.')
                await channel.stop()
                old = channel.path
                channel.source, channel.label, channel.position = 'live', f'CCTV {direction}', 0
                channel.session, channel.frame_id, channel.frame, channel.calibration = uuid4(), 0, None, None
                channel.reset_tracking()
                channel.path, channel.received = None, None
                channel.persist()
                if old and old.parent == channel.directory:
                    old.unlink(missing_ok=True)
            elif channel.source == 'none':
                raise error(409, 'NO_SOURCE', 'Pilih sumber video dahulu.')
            elif payload.action == 'restart':
                if channel.source != 'recording':
                    raise error(409, 'LIVE_CLOCK', 'Kamera langsung tidak dapat diputar ulang.')
                await channel.stop()
                channel.position, channel.frame_id, channel.frame = 0, 0, None
                channel.received = None
                channel.session = uuid4()
                channel.reset_tracking()
            if channel.task is None or channel.task.done():
                channel.task = asyncio.create_task(channel.decode(), name=f'video-{direction}')
                channel.state = 'connecting'
    return channel.view()
