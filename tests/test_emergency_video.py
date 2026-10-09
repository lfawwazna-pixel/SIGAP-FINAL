from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from backend.app.emergency import EmergencyCoordinator
from contracts.emergency import EmergencyTarget
from contracts.video import TrackedVehicle
from test_video_measurements import fresh_video_hub
from test_control import Rig


def target(rig, direction='T', kind='ambulance', event_id='test-evp', **kw):
    return EmergencyTarget(event_id=event_id,direction=direction,source_session=uuid4(),track_id=42,
        kind=kind,confidence=.85,distance_to_stop=.3,observed_at=rig.clock.utcnow(),**kw)

def priority(rig, value):
    command=rig.command('priority', session_id=rig.control.session, sequence=rig.control.sequences['priority']+1, priority_target=value)
    return rig.submit(command)

def fresh(rig, value, seconds=1, conflict='clear'):
    for _ in range(seconds):
        rig.clock.advance(1)
        rig.send('observe',source='cctv')
        rig.send('heartbeat')
        value=value.model_copy(update={'observed_at':rig.clock.utcnow()})
        assert priority(rig,value).outcome!='rejected'
        rig.engine.tick(now=rig.clock.monotonic(),at=rig.clock.utcnow(),conflict=rig.conflict(conflict))
    return value

def activate_cctv(rig):
    rig.send('observe',source='cctv');rig.send('activate');rig.send('plan',approach='U')
    rig.advance(2,data=False)  # Initial engine starts all-red, so acquisition is immediate.
    rig.send('observe',source='cctv')

@pytest.mark.parametrize('direction',list('UTSB'))
@pytest.mark.parametrize('kind',['ambulance','fire_truck'])
def test_video_priority_minimum_green_yellow_allred_clearance_and_recovery(clock,direction,kind):
    rig=Rig(clock);activate_cctv(rig);value=target(rig,direction,kind)
    assert priority(rig,value).outcome!='rejected'
    value=fresh(rig,value,9)
    assert rig.engine.phase=='green'
    value=fresh(rig,value,1)
    assert rig.engine.phase=='yellow'
    value=fresh(rig,value,3)
    assert rig.engine.phase=='all_red'
    value=fresh(rig,value,2,conflict='occupied')
    assert rig.engine.phase=='all_red'
    value=fresh(rig,value,1,conflict='unknown')
    assert rig.engine.phase=='all_red'
    value=fresh(rig,value,1)
    assert rig.engine.phase=='green' and rig.engine.active_approach==direction
    assert rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving
    assert list(rig.engine.snapshot(clock.utcnow()).signals.values()).count('green')==1
    assert priority(rig,None).outcome=='applied'
    assert rig.control.emergency is None
    rig.send('plan',approach='B')
    for _ in range(20):
        clock.advance(1);rig.send('observe',source='cctv');rig.send('heartbeat')
        rig.engine.tick(now=clock.monotonic(),at=clock.utcnow(),conflict=rig.conflict())
    assert rig.control.state=='adaptive' and rig.engine.active_approach=='B'
    assert not rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving

def test_priority_rejects_weak_replayed_changed_identity_and_queue_plans(clock):
    rig=Rig(clock);activate_cctv(rig);value=target(rig)
    assert priority(rig,value.model_copy(update={'confidence':.59})).code=='EVP_EVIDENCE'
    assert priority(rig,value.model_copy(update={'observed_at':clock.utcnow()-timedelta(seconds=3)})).code=='EVP_EVIDENCE'
    assert priority(rig,value).outcome!='rejected'
    assert rig.send('plan').code=='EVP_ACTIVE'
    assert priority(rig,value.model_copy(update={'direction':'B'})).code=='EVP_IDENTITY'
    assert priority(rig,value.model_copy(update={'event_id':'other'})).code=='EVP_BUSY'
    deadline=rig.control.emergency_deadline
    clock.advance(1);rig.send('observe',source='cctv');rig.send('heartbeat')
    assert priority(rig,value).outcome!='rejected'
    assert rig.control.emergency_deadline==deadline
    clock.advance(1);rig.send('observe',source='cctv')
    rig.engine.tick(now=clock.monotonic(),at=clock.utcnow(),conflict=rig.conflict())
    assert rig.control.fallback_code=='EVP_EVIDENCE_EXPIRED'

def test_priority_disappearance_cancels_pending_before_green(clock):
    rig=Rig(clock);activate_cctv(rig);value=target(rig)
    priority(rig,value);pending=rig.control.pending.request_id
    priority(rig,None)
    assert rig.control.pending is None
    assert rig.control.receipts[pending][1].code=='EVP_CLEARED'
    rig.send('plan',approach='S')
    for _ in range(16):
        clock.advance(1);rig.send('observe',source='cctv');rig.send('heartbeat')
        rig.engine.tick(now=clock.monotonic(),at=clock.utcnow(),conflict=rig.conflict())
    assert rig.engine.active_approach=='S'

def test_priority_data_loss_falls_back_and_fences_old_session(clock):
    rig=Rig(clock);activate_cctv(rig);value=target(rig)
    priority(rig,value);session=rig.control.session
    rig.advance(4,data=False)
    assert rig.control.session is None and rig.control.emergency is None
    assert rig.send('heartbeat',session_id=session).code=='SESSION_REVOKED'

def test_normal_car_single_prediction_coasted_boxes_and_repeated_frame_never_trigger(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator();c=hub.channels['U']
    c.tracks=[TrackedVehicle(track_id=7,class_name='car',confidence=.99,bbox=[.4,.2,.5,.4])]
    assert co.update(hub,clock.monotonic(),clock.utcnow()).target is None
    c.tracks[0].class_name='ambulance'
    for _ in range(8):
        clock.advance(.1)
        assert co.update(hub,clock.monotonic(),clock.utcnow()).target is None
    c.tracks[0].coasted=True
    for _ in range(4):
        clock.advance(.2);c.tracked_at=c.received=clock.monotonic();c.tracked_id+=1
        assert co.update(hub,clock.monotonic(),clock.utcnow()).target is None

def sample(hub,co,clock,kind='ambulance',bbox=None,d='U',ident=7):
    clock.advance(.4);c=hub.channels[d];c.tracked_id+=1;c.tracked_at=c.received=clock.monotonic()
    c.tracks=[TrackedVehicle(track_id=ident,class_name=kind,confidence=.9,bbox=bbox or [.4,.2,.5,.4])]
    return co.update(hub,clock.monotonic(),clock.utcnow())

def test_confirm_track_hold_loss_recovery_and_no_restart_of_completed_target(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator()
    assert sample(hub,co,clock).target is None
    assert sample(hub,co,clock).target is None
    confirmed=sample(hub,co,clock);assert confirmed.target and confirmed.focus
    first=confirmed.target.event_id
    c=hub.channels['U'];c.tracks=[]
    clock.advance(.5);assert co.update(hub,clock.monotonic(),clock.utcnow()).target.event_id==first
    clock.advance(1);assert co.update(hub,clock.monotonic(),clock.utcnow()).target is None
    for _ in range(4):assert sample(hub,co,clock).target is None

def test_stop_line_pass_source_change_slip_lane_and_maximum_duration(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator()
    for _ in range(3):sample(hub,co,clock)
    assert co.target
    passed=sample(hub,co,clock,bbox=[.4,.85,.5,.95])
    assert passed.target is None and passed.state=='recovering'
    co.recovered()  # Controller acknowledged clearance before the next target.
    for _ in range(3):sample(hub,co,clock,ident=8)
    assert co.target
    hub.channels['U'].tracker_session=uuid4();hub.channels['U'].tracks=[]
    clock.advance(1.3);assert co.update(hub,clock.monotonic(),clock.utcnow()).target is None
    for _ in range(4):assert sample(hub,co,clock,bbox=[.1,.2,.2,.4],ident=9).target is None
    co2=EmergencyCoordinator(maximum_seconds=1)
    for _ in range(3):sample(hub,co2,clock,ident=10)
    assert co2.target
    for _ in range(3):sample(hub,co2,clock,ident=10)
    assert co2.target is None



def test_full_sender_pipeline_focus_priority_and_recovery(clock,monkeypatch,tmp_path):
    import asyncio, httpx
    from pydantic import SecretStr
    import backend.app.adaptive as sender_module
    import backend.app.emergency as emergency_module
    from backend.app.adaptive import AdaptiveSender
    from backend.app.settings import Settings
    from contracts.control import ControlCommand
    from contracts.configuration import load_config
    class Date:
        @staticmethod
        def now(tz):return clock.utcnow()
    monkeypatch.setattr(sender_module,'datetime',Date)
    monkeypatch.setattr(emergency_module,'datetime',Date)
    timer=SimpleNamespace(monotonic=clock.monotonic)
    monkeypatch.setattr(sender_module,'time',timer)
    monkeypatch.setattr(emergency_module,'time',timer)
    hub=fresh_video_hub(clock,monkeypatch,tmp_path)
    rig=Rig(clock)
    settings=Settings(_env_file=None,sigap_yolo_enabled=True,sigap_adaptive_video=True,
        sigap_control_api_key=SecretStr('test-only-key-'*4))
    sender=AdaptiveSender(settings,load_config().intersection_id);sender.video=hub
    actions=[]
    def transport(request):
        if request.url.path=='/control':value=rig.control.snapshot(clock.monotonic(),clock.utcnow())
        elif request.url.path=='/status':value=rig.engine.snapshot(clock.utcnow())
        else:
            command=ControlCommand.model_validate_json(request.content)
            actions.append(command.action)
            value=rig.submit(command)
        return httpx.Response(200,json=value.model_dump(mode='json'))
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport),base_url='http://atcs') as client:
            sender.client=client
            await sender.cycle();rig.sender=sender.sender
            async def step(emergency=True):
                clock.advance(.4)
                for direction,c in hub.channels.items():
                    c.tracked_id+=1;c.tracked_at=c.received=clock.monotonic()
                    c.tracks=[TrackedVehicle(track_id=7,class_name='ambulance' if direction=='T' and emergency else 'car',confidence=.9,bbox=[.4,.2,.5,.4])]
                    sender.observe_emergency_frame()
                rig.engine.tick(now=clock.monotonic(),at=clock.utcnow(),conflict=rig.conflict())
                await sender.cycle()
            for _ in range(8):await step()
            assert sender.emergency.target is None and not hub.vision.focus
            assert not sender.snapshot().emergency.events and 'priority' not in actions
            assert rig.control.emergency is None and rig.control.state=='fixed_time'
            assert rig.send('activate').outcome=='accepted'
            sender.auto_resume=True
            async def serve():
                for _ in range(120):
                    await step()
                    if rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving:
                        return
                pytest.fail('Confirmed EVP was not served through the safe transition')
            await serve()
            assert rig.control.emergency is not None
            assert rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving
            assert hub.vision.focus
            assert rig.engine.active_approach=='T'
            assert sender.snapshot().emergency.state=='servicing'
            before=len(sender.decisions)
            for _ in range(5):await step()
            assert len(sender.decisions)==before  # Ordinary adaptive plans are suspended.
            for _ in range(30):await step(False)
            assert rig.control.emergency is None and not hub.vision.focus
            assert sender.snapshot().emergency.target is None
            assert rig.control.state=='adaptive'
            # A new confirmed emergency can run, but operator release fences it
            # immediately while the ATCS engine completes the physical clearance.
            await serve()
            assert rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving
            run_id=rig.engine.run_id
            await sender.hold()
            priority_count=actions.count('priority')
            assert rig.control.state=='returning_atcs' and rig.control.emergency is None
            assert sender.snapshot().emergency.target is None and not hub.vision.focus
            for _ in range(60):await step()
            assert rig.control.state=='fixed_time' and rig.engine.run_id==run_id
            assert actions.count('priority')==priority_count
            assert not sender.emergency.records and not sender.emergency.candidates
    asyncio.run(run())


def test_priority_waits_for_actual_acquisition_and_release_clears_through_safe_transition(clock):
    rig=Rig(clock)
    rig.send('observe',source='cctv')
    outside=rig.command('priority',session_id=uuid4(),sequence=1,priority_target=target(rig))
    assert rig.submit(outside).code=='SESSION_REVOKED'
    rig.advance(2,data=False,heartbeat=False)
    rig.send('observe',source='cctv')
    assert rig.send('activate').outcome=='accepted'
    assert rig.control.state=='activating'
    assert priority(rig,target(rig)).code=='EVP_CONTROL_INACTIVE'
    assert rig.control.emergency is None
    rig.send('plan',approach='U')
    # Keep measurements fresh through acquisition; no emergency is queued yet.
    for _ in range(16):
        rig.clock.advance(1);rig.send('observe',source='cctv');rig.send('heartbeat')
        rig.engine.tick(now=clock.monotonic(),at=clock.utcnow(),conflict=rig.conflict())
    assert rig.control.state=='adaptive'
    value=target(rig)
    assert priority(rig,value).outcome!='rejected'
    for _ in range(20):
        value=fresh(rig,value)
        if rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving:break
    assert rig.control.snapshot(clock.monotonic(),clock.utcnow()).emergency_serving
    phase,approach,run_id=rig.engine.phase,rig.engine.active_approach,rig.engine.run_id
    old_session=rig.control.session
    assert rig.send('release').outcome=='accepted'
    assert rig.control.state=='returning_atcs' and rig.control.emergency is None
    assert (rig.engine.phase,rig.engine.active_approach)==(phase,approach)
    rig.advance(9)
    assert rig.engine.phase=='green'
    rig.advance(1)
    assert rig.engine.phase=='yellow'
    rig.advance(3)
    assert rig.engine.phase=='all_red'
    rig.advance(2,conflict='occupied')
    assert rig.control.state=='returning_atcs' and rig.engine.phase=='all_red'
    rig.advance(1,conflict='unknown')
    assert rig.control.state=='returning_atcs'
    rig.advance(1)
    assert rig.control.state=='fixed_time' and rig.engine.run_id==run_id
    stale=rig.command('priority',session_id=old_session,sequence=999,priority_target=target(rig))
    assert rig.submit(stale).code=='SESSION_REVOKED'


def test_confirmation_requires_consistent_kind_and_locked_target_expires_on_class_flip(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator()
    for kind in ('ambulance','fire_truck','ambulance','fire_truck'):
        assert sample(hub,co,clock,kind=kind).target is None
    for _ in range(3):sample(hub,co,clock,kind='ambulance')
    assert co.target and co.target.kind=='ambulance'
    for _ in range(4):sample(hub,co,clock,kind='fire_truck')
    assert co.target is None and co.state=='recovering'

def test_second_camera_target_waits_for_acknowledged_recovery(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator()
    for _ in range(3):sample(hub,co,clock,d='U')
    assert co.target.direction=='U'
    for _ in range(3):
        sample(hub,co,clock,d='U')
        sample(hub,co,clock,d='T',ident=12)
    assert co.target.direction=='U'  # Ranking changes cannot switch the locked approach.
    sample(hub,co,clock,d='U',bbox=[.4,.85,.5,.95])
    assert co.state=='recovering' and co.target is None
    for _ in range(3):assert sample(hub,co,clock,d='T',ident=12).target is None
    co.recovered()
    assert sample(hub,co,clock,d='T',ident=12).target.direction=='T'


def test_inactive_detection_needs_new_confirmation_and_lost_target_can_be_reverified(clock,monkeypatch,tmp_path):
    hub=fresh_video_hub(clock,monkeypatch,tmp_path);co=EmergencyCoordinator(maximum_seconds=1)
    for _ in range(8):
        c=hub.channels['U'];clock.advance(.4);c.tracked_id+=1;c.tracked_at=c.received=clock.monotonic()
        c.tracks=[TrackedVehicle(track_id=7,class_name='ambulance',confidence=.9,bbox=[.4,.2,.5,.4])]
        co.update(hub,clock.monotonic(),clock.utcnow(),control_active=False)
    assert co.target is None and co.started is None
    assert not co.records and not co.candidates and not co.events
    assert sample(hub,co,clock).target is None
    assert sample(hub,co,clock).target is None
    assert sample(hub,co,clock).target is not None
    assert co.started==clock.monotonic()
    co2=EmergencyCoordinator()
    for _ in range(3):sample(hub,co2,clock)
    hub.channels['U'].tracks=[];clock.advance(1.3);co2.update(hub,clock.monotonic(),clock.utcnow())
    assert co2.target is None and co2.state=='recovering'
    co2.recovered();clock.advance(3.1)
    assert sample(hub,co2,clock).target is None
    assert sample(hub,co2,clock).target is None
    assert sample(hub,co2,clock).target is not None


def test_every_tracking_result_is_consumed_even_between_controller_polls(clock,monkeypatch,tmp_path):
    from backend.app.adaptive import AdaptiveSender
    from backend.app.settings import Settings
    import backend.app.emergency as module
    class Date:
        @staticmethod
        def now(tz):return clock.utcnow()
    monkeypatch.setattr(module,'datetime',Date)
    monkeypatch.setattr(module,'time',SimpleNamespace(monotonic=clock.monotonic))
    hub=fresh_video_hub(clock,monkeypatch,tmp_path)
    sender=AdaptiveSender(Settings(_env_file=None,sigap_yolo_enabled=True,sigap_adaptive_video=True),'test')
    sender.video=hub;sender.control_owned=True
    hub.set_tracking_observer(sender.observe_emergency_frame)
    c=hub.channels['U']
    # HTTP controller polling can miss these fresh ambulance observations.
    for _ in range(5):
        clock.advance(.2);c.tracked_at=c.received=clock.monotonic();c.tracked_id+=1
        c.tracks=[TrackedVehicle(track_id=7,class_name='ambulance',confidence=.9,bbox=[.4,.2,.5,.4])]
        c.tracking_observer()
    assert sender.emergency.target and sender.emergency.target.track_id==7
    for _ in range(3):
        clock.advance(.2);c.tracked_at=c.received=clock.monotonic();c.tracked_id+=1
        c.tracks=[TrackedVehicle(track_id=7,class_name='car',confidence=.9,bbox=[.4,.2,.5,.4])]
        c.tracking_observer()
    assert sender.emergency.target  # Short classification gaps do not erase real evidence.
    clock.advance(.7);c.tracking_observer()
    assert sender.emergency.target is None and sender.emergency.state=='recovering'
