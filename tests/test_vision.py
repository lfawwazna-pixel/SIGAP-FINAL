import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

from backend.app.settings import Settings
from backend.app.video import VideoChannel
from backend.app.vision import VisionWorker
from contracts.video import TrackedVehicle
from test_auth import auth_context, login  # noqa: F401
from test_video import video_context  # noqa: F401


def test_overlay_uses_its_own_frame_and_falls_back_when_stale(video_context):
    client, app = video_context
    login(client)
    channel = app.state.video.channels['U']
    channel.vision.enabled = True
    channel.source, channel.state = 'recording', 'playing'
    channel.frame, channel.frame_id, channel.received = b'\xff\xd8raw\xff\xd9', 20, time.monotonic()
    channel.position = 4
    channel.tracked_frame, channel.tracked_id = b'\xff\xd8tracked\xff\xd9', 19
    channel.tracked_at, channel.tracked_position = time.monotonic(), 3.8
    channel.tracks = [TrackedVehicle(track_id=1, class_name='car', confidence=.8, bbox=[.1,.1,.4,.4])]
    raw = client.get('/api/video/U/frame?overlay=false')
    tracked = client.get('/api/video/U/frame?overlay=true')
    assert raw.content == channel.frame and raw.headers['x-tracking'] == 'none'
    assert tracked.content == channel.tracked_frame and tracked.headers['x-tracking'] == 'ByteTrack'
    assert tracked.headers['x-frame-id'] == '19' and tracked.headers['x-media-seconds'] == '3.8'
    assert tracked.headers['x-source-session'] == raw.headers['x-source-session']
    channel.tracked_at -= 4
    assert client.get('/api/video/U/frame?overlay=true').content == channel.frame
    assert channel.view().detection_ready is False and channel.view().tracking.tracks == []
    channel.tracked_at = time.monotonic()
    channel.session = uuid4()
    assert client.get('/api/video/U/frame?overlay=true').headers['x-tracking'] == 'none'


def test_result_finishing_after_source_change_is_discarded(tmp_path):
    async def scenario():
        channel = VideoChannel('U', tmp_path)
        session = channel.session
        async def infer(*args):
            channel.session = uuid4()
            return dict(jpeg=b'old', tracks=[], device='cpu', processing_ms=100)
        channel.vision = SimpleNamespace(infer=infer)
        channel.state = 'playing'
        await channel.track(b'frame', 1, session, .2, time.monotonic())
        assert channel.tracked_frame is None
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
