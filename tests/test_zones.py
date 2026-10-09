import asyncio
import time
from types import SimpleNamespace
from uuid import uuid4

from contracts.zones import inside, zone_tracks
from contracts.video import TrackedVehicle, VideoCalibration
from backend.app.measurements import VideoMeasurements
from backend.app.video import VideoChannel
from test_video import calibration
from test_video_measurements import fresh_video_hub


def test_footpoint_boundaries_overlap_and_duplicate_identity():
    polygon = [dict(x=.2,y=.2),dict(x=.8,y=.2),dict(x=.8,y=.8),dict(x=.2,y=.8)]
    marked = dict(lanes={'middle':polygon, 'inner':polygon})
    tracks = [dict(track_id=1, confidence=.9,bbox=[.1,.1,.3,.9]),
              dict(track_id=2, confidence=.5,coasted=True,bbox=[.1,.1,.3,.8]),
              dict(track_id=2, confidence=.4,bbox=[.1,.1,.3,.8])]
    accepted = zone_tracks(tracks, marked)
    assert accepted == [tracks[2]]  # Box overlap alone is insufficient; edges are included once.
    assert inside(.8,.8,polygon) and not inside(.80001,.8,polygon)
    assert zone_tracks(tracks,None) == []


def test_all_classes_share_zone_admission_and_exit_immediately(clock,monkeypatch,tmp_path):
    hub = fresh_video_hub(clock,monkeypatch,tmp_path)
    c = hub.channels['U']
    classes = ['car','motorcycle','bus','truck','ambulance','fire_truck']
    c.tracks = [TrackedVehicle(track_id=i+1,class_name=name,confidence=.9,bbox=[.4,.2,.5,.4])
                for i,name in enumerate(classes)]
    c.tracks = c.tracks + [TrackedVehicle(track_id=99,class_name='car',confidence=.99,bbox=[.9,.2,1,.4])]
    provider = VideoMeasurements('test')
    batch = provider.snapshot(hub)
    assert len(c.tracking_view().tracks) == len(c.tracks) == len(provider.vehicles) == 6
    assert batch.approaches['U'].controlled_count == 6
    assert [v.kind for v in provider.vehicles] == ['car','motorcycle','bus','truck','ambulance','fire_engine']
    identities = [v.id for v in provider.vehicles]
    c.tracks = [t.model_copy(update={'class_name':'truck'}) if t.track_id == 1 else t for t in c.tracks]
    c.tracked_id += 1
    provider.snapshot(hub)
    assert provider.vehicles[0].kind == 'truck'
    assert [v.id for v in provider.vehicles] == identities  # Reclassification never creates a new vehicle.
    c.tracks = [t.model_copy(update={'bbox':[.9,.2,1,.4]}) for t in c.tracks]
    c.tracked_id += 1
    batch = provider.snapshot(hub)
    assert not c.tracks and not provider.vehicles and batch.approaches['U'].controlled_count == 0


def test_reentry_does_not_inherit_wait_from_before_zone_exit(clock,monkeypatch,tmp_path):
    hub = fresh_video_hub(clock,monkeypatch,tmp_path)
    c = hub.channels['U']
    p = VideoMeasurements('test')
    def capture(box):
        c.tracks = [TrackedVehicle(track_id=1,class_name='car',confidence=.9,bbox=box)]
        c.tracked_id += 1
        c.tracked_at = c.received = clock.monotonic()
        return p.snapshot(hub).approaches['U']
    box=[.4,.2,.5,.4]
    capture(box)
    clock.advance(1)
    assert capture(box).queue_count == 1
    clock.advance(.2)
    assert capture([.9,.2,1,.4]).queue_count == 0
    clock.advance(.2)
    returned=capture(box)
    assert returned.controlled_count == 1 and returned.queue_count == 0 and returned.oldest_wait_seconds == 0


def test_calibration_changed_during_inference_rejects_old_overlay(tmp_path):
    async def scenario():
        c = VideoChannel('U',tmp_path)
        c.calibration = VideoCalibration.model_validate(calibration())
        c.state='playing'
        async def infer(*args,**kwargs):
            assert kwargs['calibration'] == calibration() | {'upstream_queue_visible':False}
            c.tracker_session=uuid4()
            c.reset_tracking()
            return dict(jpeg=b'old',tracks=[],device='cpu',processing_ms=1)
        c.vision=SimpleNamespace(infer=infer)
        await c.track(b'raw',1,c.session,0,time.monotonic())
        assert c.tracked_frame is None and not c.tracks
    asyncio.run(scenario())
