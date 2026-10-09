import asyncio
import time
import sys
from types import SimpleNamespace
from uuid import uuid4

from backend.app.settings import Settings
from backend.app.video import VideoChannel
from backend.app.vision import VisionWorker
from contracts.video import TrackedVehicle
from test_auth import auth_context, login  # noqa: F401
from test_video import calibration, video_context  # noqa: F401


def test_worker_shutdown_reaps_real_child_and_closes_its_pipes(tmp_path):
    async def scenario():
        worker = VisionWorker(Settings(_env_file=None, sigap_yolo_model=str(tmp_path/'unused.pt')))
        process = await asyncio.create_subprocess_exec(sys.executable, '-u', '-c',
            'import sys; print("ready", flush=True); sys.stdin.buffer.read()',
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL)
        worker.process = process
        try:
            assert (await asyncio.wait_for(process.stdout.readline(), 10)).rstrip(b'\r\n') == b'ready'
            await asyncio.wait_for(worker.close(), 10)
            assert process.returncode is not None and worker.process is None
            assert process.stdin.is_closing() and process.stdout.at_eof()
            await worker.close()  # Repeated shutdown stays harmless.
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
    asyncio.run(scenario())


def test_overlay_uses_its_own_frame_and_falls_back_when_stale(video_context):
    client, app = video_context
    login(client)
    channel = app.state.video.channels['U']
    channel.vision.enabled = True
    channel.source, channel.state = 'recording', 'playing'
    channel.frame, channel.frame_id, channel.received = b'\xff\xd8raw\xff\xd9', 20, time.monotonic()
    channel.position = 4
    channel.tracked_frame, channel.tracked_id = b'\xff\xd8tracked\xff\xd9', 19
    channel.tracked_raw = b'\xff\xd8matchedraw\xff\xd9'
    channel.tracked_at, channel.tracked_position = time.monotonic(), 3.8
    from contracts.video import VideoCalibration
    channel.calibration = VideoCalibration.model_validate(calibration())
    channel.tracks = [TrackedVehicle(track_id=1, class_name='car', confidence=.8, bbox=[.1,.1,.4,.4])]
    raw = client.get('/api/video/U/frame?overlay=false')
    tracked = client.get('/api/video/U/frame?overlay=true')
    assert raw.content == channel.tracked_raw and raw.headers['x-tracking'] == 'none'
    assert raw.headers['x-frame-id'] == tracked.headers['x-frame-id'] == '19'
    assert raw.headers['x-media-seconds'] == tracked.headers['x-media-seconds'] == '3.8'
    assert tracked.content == channel.tracked_frame and tracked.headers['x-tracking'] == 'ByteTrack'
    assert tracked.headers['x-frame-id'] == '19' and tracked.headers['x-media-seconds'] == '3.8'
    assert tracked.headers['x-source-session'] == raw.headers['x-source-session']
    assert raw.headers['x-track-count'] == tracked.headers['x-track-count'] == '1'
    channel.tracks += [TrackedVehicle(track_id=2, class_name='truck', confidence=.95, bbox=[.9,.1,1,.4])]
    assert client.get('/api/video/U/frame?overlay=true').headers['x-track-count'] == '1'
    assert len(channel.view().tracking.tracks) == 1
    channel.tracks = []
    assert client.get('/api/video/U/frame?overlay=true').headers['x-track-count'] == '0'
    channel.tracked_at -= 4
    assert client.get('/api/video/U/frame?overlay=true').content == channel.frame
    assert client.get('/api/video/U/frame?overlay=true').headers['x-track-count'] == ''
    assert channel.view().detection_ready is False and channel.view().tracking.tracks == []
    channel.tracked_at = time.monotonic()
    channel.session = uuid4()
    assert client.get('/api/video/U/frame?overlay=true').headers['x-tracking'] == 'none'
    assert client.get('/api/video/U/frame?overlay=true').headers['x-track-count'] == ''


def test_result_finishing_after_source_change_is_discarded(tmp_path):
    async def scenario():
        channel = VideoChannel('U', tmp_path)
        session = channel.session
        async def infer(*args, **kwargs):
            channel.session = uuid4()
            return dict(jpeg=b'old', tracks=[], device='cpu', processing_ms=100)
        channel.vision = SimpleNamespace(infer=infer)
        channel.state = 'playing'
        await channel.track(b'frame', 1, session, .2, time.monotonic())
        assert channel.tracked_frame is None
    asyncio.run(scenario())


def test_worker_samples_latest_frame_after_waiting_instead_of_processing_old_input(tmp_path):
    import base64
    import json
    async def scenario():
        model = tmp_path/'model.pt'
        model.touch()
        worker = VisionWorker(Settings(_env_file=None, sigap_yolo_enabled=True, sigap_yolo_model=str(model)))
        session = uuid4()
        fresh = time.monotonic()
        written = []
        class Input:
            def write(self, data):
                written.append(json.loads(data))
            async def drain(self):
                pass
        class Output:
            async def readline(self):
                return json.dumps(dict(direction='U',session=str(session),frame_id=7,tracks=[],device='cpu',
                    processing_ms=100,jpeg=base64.b64encode(b'\xff\xd8overlay\xff\xd9').decode())).encode()
        worker.process = SimpleNamespace(returncode=None,stdin=Input(),stdout=Output())
        result = await worker.infer('U',session,1,b'old',fresh-4,
            latest=lambda:(7,b'new',fresh,1.4))
        assert written[0]['frame_id'] == result['input_frame_id'] == 7
        assert result['input_jpeg'] == b'new' and result['input_captured'] == fresh
        assert result['input_position'] == 1.4
        assert await worker.infer('U',session,8,b'old',latest=lambda:None) is None
        assert len(written) == 1
    asyncio.run(scenario())


def test_missing_model_and_expired_work_do_not_break_raw_video(tmp_path):
    async def scenario():
        worker = VisionWorker(Settings(_env_file=None, sigap_yolo_enabled=True,
            sigap_yolo_model=str(tmp_path/'missing.pt')))
        assert await worker.infer('U', uuid4(), 1, b'jpeg', time.monotonic()-4) is None
        assert worker.retry_after == 0  # stale jobs never trigger worker startup
        assert await worker.infer('U', uuid4(), 2, b'jpeg') is None
        assert worker.retry_after > time.monotonic() and worker.process is None
        channel = VideoChannel('U', tmp_path, vision=worker)
        channel.state, channel.source = 'playing', 'live'
        channel.frame, channel.received = b'raw', time.monotonic()
        assert channel.view().state == 'playing' and channel.view().tracking.state == 'error'
    asyncio.run(scenario())


def test_tracking_observer_runs_only_after_accepted_current_session_result(tmp_path):
    async def run():
        c=VideoChannel('U',tmp_path);calls=[];c.tracking_observer=lambda:calls.append(c.tracked_id)
        c.state='playing';c.frame=b'raw';c.frame_id=1;c.received=time.monotonic()
        async def infer(*args,**kw):
            return dict(jpeg=b'overlay',tracks=[],device='cpu',processing_ms=10)
        c.vision=SimpleNamespace(infer=infer)
        await c.track(b'raw',1,c.session,.2,c.received)
        assert calls==[1]
        async def late(*args,**kw):
            c.tracker_session=uuid4()
            return dict(jpeg=b'old',tracks=[],device='cpu',processing_ms=10)
        c.vision=SimpleNamespace(infer=late)
        await c.track(b'raw',2,c.session,.4,c.received)
        assert calls==[1]
    asyncio.run(run())
