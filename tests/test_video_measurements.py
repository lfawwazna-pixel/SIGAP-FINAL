import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
from pydantic import SecretStr

from backend.app.adaptive import AdaptiveSender
from backend.app.measurements import VideoMeasurements
from backend.app.settings import Settings
from backend.app.video import VideoHub
from contracts.configuration import load_config
from contracts.control import ControlCommand
from contracts.video import TrackedVehicle, VideoCalibration
from test_adaptive import measurements
from test_control import Rig
from test_video import calibration


def test_lane_counts_stationary_wait_replay_source_change_and_stale(clock, monkeypatch, tmp_path):
    import backend.app.measurements as module
    import backend.app.video as video_module
    class Date:
        @staticmethod
        def now(tz):
            return clock.utcnow()
    monkeypatch.setattr(module, 'datetime', Date)
    timer = SimpleNamespace(monotonic=clock.monotonic)
    monkeypatch.setattr(module, 'time', timer)
    monkeypatch.setattr(video_module, 'time', timer)
    hub = VideoHub(Settings(_env_file=None, sigap_media_dir=str(tmp_path), sigap_yolo_enabled=True))
    provider = VideoMeasurements('test')
    for channel in hub.channels.values():
        channel.source, channel.state = 'recording', 'playing'
        channel.calibration = VideoCalibration.model_validate(calibration())
        channel.tracks = [TrackedVehicle(track_id=i+1, class_name='car', confidence=.9,
            bbox=[x-.02,.2,x+.02,.4]) for i,x in enumerate((.15,.45,.75))]
    def capture():
        for channel in hub.channels.values():
            channel.received = channel.tracked_at = clock.monotonic()
            channel.tracked_session = channel.session
            channel.tracked_id += 1
        return provider.snapshot(hub)
    first = capture()
    assert all(v.controlled_count == 2 and v.slip_count == 1 and v.queue_count == 0 for v in first.approaches.values())
    assert len(provider.vehicles) == 12 and len({v.id for v in provider.vehicles}) == 12
    assert all(-420 <= v.x <= 1220 and -420 <= v.y <= 1220 for v in provider.vehicles)
    clock.advance(1)
    queued = capture()
    assert all(v.queue_count == 2 and v.oldest_wait_seconds == 1 for v in queued.approaches.values())
    sequence = queued.sequence
    clock.advance(.5)
    replay = provider.snapshot(hub)
    assert replay.sequence == sequence
    assert replay.approaches['U'].oldest_wait_seconds == 1  # Repeated result doesn't extend a wait.
    old_identity = next(v.id for v in provider.vehicles if v.origin == 'U')
    hub.channels['U'].tracker_session = uuid4()  # New loop starts with clean IDs and waits.
    hub.channels['U'].reset_tracking()
    boundary = provider.snapshot(hub)
    assert boundary.approaches['U'].usable
    assert boundary.approaches['U'].observed_at == replay.approaches['U'].observed_at
    hub.channels['U'].tracks = hub.channels['T'].tracks.copy()
    reset = capture()
    assert reset.approaches['U'].queue_count == 0
    assert next(v.id for v in provider.vehicles if v.origin == 'U') != old_identity
    hub.channels['T'].calibration = None
    invalid = provider.snapshot(hub)
    assert not invalid.approaches['T'].usable and 'T' in provider.issues
    clock.advance(4)
    stale = provider.snapshot(hub)
    assert not any(v.usable for v in stale.approaches.values()) and not provider.vehicles


def test_video_sender_requires_activation_falls_back_recovers_and_manual_release_stays_off(clock, monkeypatch):
    import backend.app.adaptive as module
    class Date:
        @staticmethod
        def now(tz):
            return clock.utcnow()
    monkeypatch.setattr(module, 'datetime', Date)
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=clock.monotonic))
    rig = Rig(clock)
    rig.control.settings.atcs_enable_test_source = False
    sender = AdaptiveSender(Settings(_env_file=None, sigap_yolo_enabled=True,
        sigap_control_api_key=SecretStr('test-only-key-'*4)), load_config().intersection_id)
    healthy = True
    provider_session = uuid4()
    class Provider:
        issues, vehicles, source_sessions = {}, [], {}
        def snapshot(self, hub):
            value = measurements(clock.utcnow(), T=dict(controlled_count=4, queue_count=4), U=dict(usable=healthy))
            value.source, value.source_session, value.sequence = 'recording', provider_session, int(clock.elapsed*10)
            return value
    sender.video_measurements = Provider()
    actions = []
    def transport(request):
        assert request.url.path != '/measurements', 'Video mode must never read synthetic measurements'
        if request.url.path == '/control':
            value = rig.control.snapshot(clock.monotonic(), clock.utcnow())
        elif request.url.path == '/status':
            value = rig.engine.snapshot(clock.utcnow())
        else:
            command = ControlCommand.model_validate_json(request.content)
            actions.append(command.action)
            value = rig.submit(command)
        return httpx.Response(200, json=value.model_dump(mode='json'))
    async def scenario():
        nonlocal healthy
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url='http://atcs') as client:
            sender.client = client
            await sender.cycle()
            assert sender.state == 'ready' and not sender.auto_resume and rig.control.session is None
            assert sender.snapshot().source == 'recording' and rig.control.source == 'cctv'
            rig.sender = sender.sender
            assert rig.send('activate').outcome == 'accepted'
            sender.auto_resume = True  # Operator API arms recovery on successful activation.
            async def advance(n):
                for _ in range(n):
                    clock.advance(.5)
                    rig.engine.tick(now=clock.monotonic(), at=clock.utcnow(), conflict=rig.conflict())
                    await sender.cycle()
            await advance(40)
            assert rig.control.state == 'adaptive' and sender.state == 'active'
            assert sender.auto_resume
            healthy = False
            await advance(30)
            assert rig.control.state == 'fixed_time' and rig.control.session is None
            assert sender.state == 'unavailable' and rig.control.fallback_code == 'DATA_UNUSABLE'
            healthy = True
            await advance(40)
            assert rig.control.state == 'adaptive' and actions.count('activate') == 1
            await sender.hold()  # The hold control works even when no operator session is shown.
            await advance(40)
            assert rig.control.state == 'fixed_time' and not sender.auto_resume
            assert actions.count('activate') == 1
    asyncio.run(scenario())
