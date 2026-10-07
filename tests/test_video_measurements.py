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
    assert next(v.id for v in provider.vehicles if v.origin == 'U') == old_identity
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


def fresh_video_hub(clock, monkeypatch, tmp_path, marked=True):
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
    for channel in hub.channels.values():
        channel.source, channel.state = 'recording', 'playing'
        channel.calibration = VideoCalibration.model_validate(calibration()) if marked else None
        channel.received = channel.tracked_at = clock.monotonic()
        channel.tracked_session, channel.tracked_id = channel.session, 1
    return hub


def test_all_tracks_appear_without_calibration_on_their_camera_approach(clock, monkeypatch, tmp_path):
    hub = fresh_video_hub(clock, monkeypatch, tmp_path, marked=False)
    classes = ['car', 'motorcycle', 'bus', 'truck', 'ambulance', 'fire_truck']
    for i, channel in enumerate(hub.channels.values()):
        channel.tracks = [TrackedVehicle(track_id=j+1, class_name=classes[j % 6], confidence=.9,
            bbox=[.4, .2, .5, .4]) for j in range(6+i)]
    provider = VideoMeasurements('test')
    batch = provider.snapshot(hub)
    assert len(provider.vehicles) == sum(len(c.tracks) for c in hub.channels.values()) == 30
    assert len({v.id for v in provider.vehicles}) == 30
    for direction, channel in hub.channels.items():
        displayed = [v for v in provider.vehicles if v.origin == direction]
        assert len(displayed) == len(channel.tracks)
        assert len({(v.x, v.y) for v in displayed}) == len(displayed)
        # Rotate back to the north approach to verify all cars are on a road.
        for vehicle in displayed:
            x, y = vehicle.x, vehicle.y
            for _ in range('UTSB'.index(direction)):
                x, y = y, 800-x
            assert x == 470 and -385 <= y <= 240
    assert {'ambulance', 'fire_engine'} <= {v.kind for v in provider.vehicles}
    assert all(not v.usable and v.controlled_count == v.queue_count == v.slip_count == 0
               for v in batch.approaches.values())
    assert set(provider.issues) == set('UTSB')


def test_outside_roi_and_past_stop_line_keep_map_count_without_inflating_demand(clock, monkeypatch, tmp_path):
    hub = fresh_video_hub(clock, monkeypatch, tmp_path)
    channel = hub.channels['U']
    channel.tracks = [TrackedVehicle(track_id=i+1, class_name='car', confidence=.9, bbox=box)
        for i, box in enumerate(([.43, .2, .47, .4], [.96, .2, 1, .4], [.43, .7, .47, .85]))]
    provider = VideoMeasurements('test')
    batch = provider.snapshot(hub)
    assert len(provider.vehicles) == len(channel.tracks) == 3
    assert batch.approaches['U'].usable and batch.approaches['U'].controlled_count == 1
    assert sum(v.served for v in provider.vehicles) == 1
    ids = {v.id for v in provider.vehicles}
    provider.snapshot(hub)
    assert {v.id for v in provider.vehicles} == ids
    assert all(v.origin == 'U' for v in provider.vehicles)


def test_ambiguous_lane_keeps_every_track_and_blocks_control(clock, monkeypatch, tmp_path):
    hub = fresh_video_hub(clock, monkeypatch, tmp_path)
    channel = hub.channels['T']
    marked = calibration()
    marked['lanes']['inner'] = marked['lanes']['middle']
    channel.calibration = VideoCalibration.model_validate(marked)
    channel.tracks = [TrackedVehicle(track_id=1, class_name='truck', confidence=.9, bbox=[.4, .2, .5, .4])]
    provider = VideoMeasurements('test')
    batch = provider.snapshot(hub)
    assert len(provider.vehicles) == 1 and provider.vehicles[0].origin == 'T'
    assert not batch.approaches['T'].usable and batch.approaches['T'].controlled_count == 0


def test_fresh_map_is_independent_of_controller_and_source_changes_clear_old_tracks(clock, monkeypatch, tmp_path):
    hub = fresh_video_hub(clock, monkeypatch, tmp_path, marked=False)
    channel = hub.channels['S']
    channel.tracks = [TrackedVehicle(track_id=1, class_name='ambulance', confidence=.9, bbox=[.1,.2,.2,.4])]
    sender = AdaptiveSender(Settings(_env_file=None, sigap_yolo_enabled=True), 'test')
    sender.video = hub
    sender.state, sender.batch = 'unavailable', None
    snapshot = sender.snapshot()
    assert snapshot.status == 'unavailable' and len(snapshot.map_vehicles) == 1
    assert not snapshot.measurements.approaches['S'].usable
    original_stamp = snapshot.measurements.approaches['S'].observed_at
    original_id = snapshot.map_vehicles[0].id
    clock.advance(1)
    channel.tracker_session = uuid4()
    channel.reset_tracking()
    boundary = sender.snapshot()
    assert boundary.map_vehicles[0].id == original_id
    assert boundary.measurements.approaches['S'].observed_at == original_stamp
    clock.advance(3)
    assert not sender.snapshot().map_vehicles  # Bridge cannot manufacture fresh data.
    channel.tracks = [TrackedVehicle(track_id=1, class_name='car', confidence=.9, bbox=[.1,.2,.2,.4])]
    channel.received = channel.tracked_at = clock.monotonic()
    channel.tracked_id = 2
    refreshed = sender.snapshot()
    assert len(refreshed.map_vehicles) == 1 and refreshed.map_vehicles[0].id != original_id
    channel.session = uuid4()
    channel.reset_tracking()
    assert not sender.snapshot().map_vehicles  # Never reuse the replaced source's IDs.


def test_crowded_lane_keeps_every_track_at_a_distinct_map_position(clock, monkeypatch, tmp_path):
    hub = fresh_video_hub(clock, monkeypatch, tmp_path, marked=False)
    channel = hub.channels['B']
    channel.tracks = [TrackedVehicle(track_id=i+1, class_name='motorcycle', confidence=.9,
        bbox=[.1,.2,.2,.4]) for i in range(180)]
    provider = VideoMeasurements('test')
    provider.snapshot(hub)
    assert len(provider.vehicles) == 180
    assert len({(v.x, v.y) for v in provider.vehicles}) == 180
    assert all(-385 <= v.x <= 85 and v.y == 290 for v in provider.vehicles)


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
