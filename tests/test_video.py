import asyncio
import subprocess
import time
from dataclasses import replace
from uuid import uuid4

import pytest
from imageio_ffmpeg import get_ffmpeg_exe
from pydantic import ValidationError

from backend.app.auth import require_operator, COOKIE_NAME
from backend.app.settings import Settings
from backend.app.video import VideoChannel, VideoHub
from contracts.video import VideoCalibration
from test_auth import auth_context, login, ORIGIN


def calibration():
    return dict(lanes={k: [dict(x=x, y=.1), dict(x=x+.2, y=.1), dict(x=x+.2, y=.9), dict(x=x, y=.9)]
                       for k,x in zip(('outer','middle','inner'), (.05,.35,.65))},
                stop_line=[dict(x=.05,y=.8),dict(x=.85,y=.8)])


@pytest.fixture
def video_context(auth_context, tmp_path):
    client, app, _, _ = auth_context
    app.state.video = VideoHub(Settings(_env_file=None, sigap_media_dir=str(tmp_path)))
    return client, app


def test_video_auth_csrf_source_guards_and_calibration(video_context):
    client, app = video_context
    assert client.get('/api/video').status_code == 401
    assert client.get('/api/video/U/frame').status_code == 401
    csrf = login(client).json()['csrf_token']
    headers = {**ORIGIN, 'X-CSRF-Token': csrf}
    state = client.get('/api/video').json()['channels'][0]
    assert state['source'] == 'none' and state['detection_ready'] is False
    query = '/api/video/U/upload?expected_session='+state['source_session']
    assert client.post(query, headers=ORIGIN, content=b'bad').status_code == 403
    assert client.post(query, headers=headers, content=b'bad').status_code == 422
    assert not list(app.state.video.channels['U'].directory.glob('*.mp4'))
    # Header-only fixture tests upload transport; real decoding is tested separately.
    mp4 = b'\x00\x00\x00\x20ftypisom'+b'\x00'*40
    response = client.post(query, headers=headers, content=mp4)
    assert response.status_code == 200
    state = response.json()
    assert state['state'] == 'connecting' and state['source'] == 'recording'
    assert client.post(query, headers=headers, content=mp4).status_code == 409
    command = dict(expected_session=state['source_session'], action='calibrate', calibration=calibration())
    assert client.post('/api/video/U/commands', headers=headers, json=command).status_code == 200
    channel = app.state.video.channels['U']
    restored = VideoChannel('U', channel.directory)
    assert restored.calibration == channel.calibration and restored.source == 'recording'
    assert restored.session != channel.session and restored.frame is None
    bad = calibration(); bad['lanes']['outer'] = [dict(x=.1,y=.1)]*3
    assert client.post('/api/video/U/commands', headers=headers, json={**command,'calibration':bad}).status_code == 422
    assert client.post('/api/video/U/commands', headers=headers,
        json=dict(expected_session=state['source_session'],action='use_live')).status_code == 409
    principal = app.state.auth.current(client.cookies[COOKIE_NAME])
    app.dependency_overrides[require_operator] = lambda: replace(principal,
        operator=principal.operator.model_copy(update={'permissions': ['monitor:read']}))
    assert client.post('/api/video/U/commands', headers=headers, json=command).status_code == 403


def test_shared_frame_identity_stale_and_session_revocation(video_context):
    client, app = video_context
    csrf = login(client).json()['csrf_token']
    channel = app.state.video.channels['U']
    channel.source, channel.state = 'live', 'playing'
    channel.frame, channel.frame_id, channel.received = b'\xff\xd8fixture\xff\xd9', 37, time.monotonic()
    atcs = client.get('/api/video/U/frame')
    sigap = client.get('/api/video/U/frame')
    assert atcs.content == sigap.content == channel.frame
    assert atcs.headers['x-source-session'] == sigap.headers['x-source-session'] == str(channel.session)
    assert atcs.headers['x-frame-id'] == sigap.headers['x-frame-id'] == '37'
    channel.received -= 4
    assert client.get('/api/video').json()['channels'][0]['state'] == 'stale'
    assert client.get('/api/video/U/frame').status_code == 503
    channel.state = 'paused'; channel.source = 'recording'
    assert client.get('/api/video/U/frame').status_code == 503
    client.post('/api/auth/logout', headers={**ORIGIN,'X-CSRF-Token':csrf})
    assert client.get('/api/video/U/frame').status_code == 401


def test_live_persistence_never_relabels_old_recording_or_exposes_url(tmp_path):
    channel = VideoChannel('U', tmp_path, 'rtsp://private:secret@camera.invalid/live')
    channel.source, channel.label, channel.calibration = 'live', 'CCTV U', VideoCalibration.model_validate(calibration())
    channel.persist()
    restored = VideoChannel('U', tmp_path, channel.live_url)
    assert restored.source == 'live' and restored.path is None and restored.calibration == channel.calibration
    assert 'secret' not in restored.view().model_dump_json()
    assert 'secret' not in (tmp_path/'U.json').read_text()
    assert VideoChannel('U', tmp_path).source == 'none'


def test_live_reconnect_preserves_calibration_and_fences_tracker(tmp_path):
    async def scenario():
        hub = VideoHub(Settings(_env_file=None, sigap_media_dir=str(tmp_path)))
        channel = hub.channels['U']
        channel.source, channel.state = 'live', 'error'
        channel.calibration = VideoCalibration.model_validate(calibration())
        session, tracker = channel.session, channel.tracker_session
        async def decode():
            channel.state = 'playing'
            await asyncio.Event().wait()
        channel.decode = decode
        await hub.reconnect_live()
        await asyncio.sleep(0)
        assert channel.state == 'playing' and not channel.task.done()
        assert channel.session == session and channel.tracker_session != tracker
        assert channel.calibration == VideoCalibration.model_validate(calibration())
        task = channel.task
        await hub.reconnect_live()
        assert channel.task is task  # Never start a second decoder while connected.
        await hub.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mapping', [{'X':'https://example.com/camera'}, {'U':'file:///secret'}, {'T':'https:///missing'}])
def test_camera_configuration_rejects_invalid_sources(mapping):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, sigap_camera_urls=mapping)


def test_real_ffmpeg_autostart_loop_and_persisted_default(tmp_path):
    path = tmp_path/'fixture.mp4'
    subprocess.run([get_ffmpeg_exe(), '-hide_banner','-loglevel','error','-f','lavfi','-i',
        'testsrc2=size=320x180:rate=10','-t','3','-c:v','libx264','-pix_fmt','yuv420p',str(path)],
        check=True, timeout=20, capture_output=True)
    async def scenario():
        channel = VideoChannel('U', tmp_path)
        channel.source, channel.path, channel.label = 'recording', path, 'Video utama'
        channel.calibration = VideoCalibration.model_validate(calibration())
        channel.persist()
        channel = VideoChannel('U', tmp_path)
        assert channel.path == path and channel.label == 'Video utama'
        session = channel.session
        tracker = channel.tracker_session
        channel.start()
        for _ in range(180):
            if channel.loop_count >= 1 and channel.frame_id >= 18:
                break
            await asyncio.sleep(.05)
        assert channel.state == 'playing' and channel.frame.startswith(b'\xff\xd8')
        assert channel.loop_count >= 1 and channel.frame_id >= 18
        assert channel.session == session and channel.tracker_session != tracker
        assert channel.calibration == VideoCalibration.model_validate(calibration())
        assert not channel.task.done()
        await channel.stop()
        assert channel.process is None
    asyncio.run(scenario())


@pytest.mark.parametrize('action', ['play', 'pause', 'restart'])
def test_retired_playback_commands_are_rejected(video_context, action):
    client, app = video_context
    csrf = login(client).json()['csrf_token']
    response = client.post('/api/video/U/commands', headers={**ORIGIN, 'X-CSRF-Token':csrf},
        json=dict(expected_session=str(app.state.video.channels['U'].session), action=action))
    assert response.status_code == 422
