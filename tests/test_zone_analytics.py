from types import SimpleNamespace
from uuid import uuid4
import pytest
from contracts.video import VideoCalibration, TrackedVehicle
from contracts.analytics import ComparisonInput
from backend.app.zone_analytics import ZoneDemandCollector


def calibration():
    return VideoCalibration(lanes={name:[dict(x=x,y=y) for x,y in [(a,.2),(b,.2),(b,.95),(a,.95)]]
        for name,a,b in [('outer',.05,.25),('middle',.35,.55),('inner',.65,.85)]},
        stop_line=[dict(x=0,y=.8),dict(x=1,y=.8)],upstream_queue_visible=False)


def track(identity,kind='car',x=.45,y=.6,coasted=False):
    return TrackedVehicle(track_id=identity,class_name=kind,confidence=.95,bbox=[x-.01,y-.02,x+.01,y],coasted=coasted)


def hub():
    channels={}
    for d in 'UTSB':
        c=SimpleNamespace(session=uuid4(),tracker_session=uuid4(),tracked_id=0,tracked_at=0.,
            source='recording',loop_count=0,calibration=calibration(),tracks=[],ready=True,state='playing')
        c.view=lambda c=c:SimpleNamespace(detection_ready=c.ready,state=c.state)
        channels[d]=c
    return SimpleNamespace(channels=channels)


def advance(collector,h,seconds,tracks=None):
    for c in h.channels.values():
        c.tracked_at=float(seconds); c.tracked_id+=1; c.tracks=tracks or []
    collector.observe(h)


def collect_profile():
    collector,h=ZoneDemandCollector(),hub()
    advance(collector,h,0,[track(1)])  # standing population excluded
    for t in range(1,62):
        advance(collector,h,t,[track(1),track(2,'motorcycle'),track(3,'truck',x=.75)])
    return collector,h,collector.snapshot(now=61)


def test_profile_counts_only_unique_current_entries_in_calibrated_upstream_zones():
    collector,h=ZoneDemandCollector(),hub()
    advance(collector,h,0,[track(1)])
    for t in range(1,62):
        advance(collector,h,t,[track(1),track(2),track(2),track(3,x=.99),track(4,y=.9),
            track(5,coasted=True),track(6,'ambulance'),track(7,'fire_truck')])
    p=collector.snapshot(now=61)
    assert p.ready
    assert all(a.entries==1 and a.by_class['car']==1 and a.by_movement['straight']==1 for a in p.approaches)
    assert p.approaches[0].demand_per_minute==pytest.approx(60/61,abs=.0001)
    collector.observe(h)  # same frame must not duplicate an entry
    assert collector.snapshot(now=61).approaches==p.approaches


def test_server_freezes_real_profile_and_overrides_client_forged_demand_and_mix():
    collector,h,p=collect_profile()
    spec=ComparisonInput(demand_source='zone_observation',observation_fingerprint=p.fingerprint,
        demand_per_minute=dict.fromkeys('UTSB',180),class_mix=dict(car=1,motorcycle=0,bus=0,truck=0))
    resolved,provenance=collector.resolve(spec,now=62)
    assert resolved.demand_per_minute=={d:round(120/61,4) for d in 'UTSB'}
    assert resolved.approach_composition['U'].class_mix==dict(car=0,motorcycle=1,bus=0,truck=1)
    assert provenance.source=='zone_observation' and provenance.fingerprint==p.fingerprint
    assert resolved.queue_visibility=='partial'


def test_capture_expires_and_source_change_invalidates_even_before_next_tracking_callback():
    collector,h,p=collect_profile()
    spec=ComparisonInput(demand_source='zone_observation',observation_fingerprint=p.fingerprint)
    with pytest.raises(ValueError): collector.resolve(spec,now=662)
    h.channels['U'].session=uuid4()
    with pytest.raises(ValueError): collector.resolve(spec,now=62)
    assert not collector.snapshot(now=62).ready


def test_tracking_gap_or_calibration_change_starts_new_continuous_observation():
    collector,h,p=collect_profile()
    advance(collector,h,65,[track(99)])
    assert not collector.snapshot(now=65).ready
    assert collector.snapshot(now=65).approaches[0].entries==0
    h.channels['U'].calibration.upstream_queue_visible=True
    advance(collector,h,66,[track(100)])
    assert collector.snapshot(now=66).approaches[0].observed_seconds==0


def test_loop_initial_population_not_counted_as_arrivals_and_marked_repeated_recording():
    collector,h,p=collect_profile()
    for c in h.channels.values(): c.tracker_session=uuid4(); c.loop_count=1
    advance(collector,h,62,[track(1),track(2),track(3)])
    p=collector.snapshot(now=62)
    assert p.ready and all(a.entries==2 and a.loop_count==1 for a in p.approaches)


def test_missing_camera_or_stale_tracking_withholds_profile_without_fabricated_counts():
    collector,h,p=collect_profile()
    assert not collector.snapshot(now=65).ready
    h.channels['B'].ready=False
    advance(collector,h,62)
    p=collector.snapshot(now=62)
    assert not p.ready and p.fingerprint is None
    assert p.approaches[-1].state=='unavailable' and p.approaches[-1].entries==0


def test_valid_empty_observation_is_zero_demand_not_an_invented_default():
    collector,h=ZoneDemandCollector(),hub()
    for t in range(61): advance(collector,h,t)
    p=collector.snapshot(now=60)
    assert p.ready and all(a.entries==a.demand_per_minute==0 for a in p.approaches)
    resolved,_=collector.resolve(ComparisonInput(demand_source='zone_observation',observation_fingerprint=p.fingerprint),now=60)
    assert all(v==0 for v in resolved.demand_per_minute.values())


def test_ambiguous_lane_calibration_cannot_be_mistaken_for_zero_demand():
    collector,h=ZoneDemandCollector(),hub()
    h.channels['U'].calibration.lanes['inner']=h.channels['U'].calibration.lanes['middle']
    for t in range(61): advance(collector,h,t,[track(1)])
    p=collector.snapshot(now=60)
    assert not p.ready and p.approaches[0].state=='unavailable'
