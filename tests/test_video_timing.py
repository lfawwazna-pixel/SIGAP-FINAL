from datetime import timedelta
from adaptive.policy import AdaptivePolicy
from contracts.adaptive import AdaptivePolicyConfig
from test_adaptive import measurements, AT

def video(**values):
    batch=measurements(T=dict(controlled_count=5,queue_count=5,**values))
    batch.source='recording'
    return batch

def test_partial_camera_cannot_turn_150_seconds_into_twenty():
    policy=AdaptivePolicy(AdaptivePolicyConfig(maximum_green=180))
    decision=policy.choose(video(),0,AT)
    assert decision.approach=='T' and decision.green_seconds==120
    policy.served('T',1,decision.green_seconds)
    # Preview never changes the applied-duration memory.
    policy.previous=None
    assert policy.choose(video(),2,AT).green_seconds==112.5
    assert policy.choose(video(),2,AT).green_seconds==112.5

def test_congestion_at_camera_boundary_or_long_queue_preserves_baseline():
    p=AdaptivePolicy(AdaptivePolicyConfig(maximum_green=180))
    for values in (dict(queue_reaches_boundary=True),dict(occupancy_ratio=.4),dict(oldest_wait_seconds=25)):
        assert p.choose(video(**values),0,AT).green_seconds==150

def test_full_view_can_reduce_gradually_and_invalid_data_still_blocks_plan():
    p=AdaptivePolicy(AdaptivePolicyConfig(maximum_green=180))
    batch=video(queue_visibility='full')
    first=p.choose(batch,0,AT)
    assert first.green_seconds==120
    p.served('T',1,120);p.previous=None
    assert p.choose(batch,2,AT).green_seconds==96
    batch.approaches['T'].usable=False
    assert p.choose(batch,3,AT).approach is None

def test_legacy_synthetic_provider_keeps_its_bounded_policy():
    assert AdaptivePolicy().choose(measurements(T=dict(controlled_count=5,queue_count=5)),0,AT).green_seconds==20


def test_zero_detections_in_partial_view_does_not_remove_an_approach_from_fair_service():
    p = AdaptivePolicy(AdaptivePolicyConfig(maximum_green=180))
    p.served('T', 290, 120)
    batch = video()
    decision = p.choose(batch, 300, AT)
    assert decision.approach == 'U'
    assert decision.inputs['U'].controlled_count == 0
    assert decision.green_seconds == 68
    # A confirmed full view can avoid an empty approach; synthetic logic is unchanged.
    for d in ('U','S','B'):
        batch.approaches[d].queue_visibility = 'full'
    assert p.choose(batch, 300, AT).approach == 'T'


def test_runtime_accepts_long_green_after_clearance_and_still_expires_stale_data(clock):
    import asyncio
    from types import SimpleNamespace
    from pydantic import SecretStr
    from atcs_simulator.app.runtime import AtcsRuntime
    from atcs_simulator.app.control_settings import ControlSettings
    from contracts.configuration import load_config
    from test_control import Rig

    runtime = AtcsRuntime(load_config(), clock=clock,
        conflict_provider=SimpleNamespace(source='provider', read=lambda: 'clear'),
        control_settings=ControlSettings(_env_file=None, atcs_enable_test_source=True,
            sigap_control_api_key=SecretStr('test-only-key-'*4)))

    async def scenario():
        await runtime.start()
        try:
            rig = Rig(clock)
            rig.engine, rig.control = runtime.engine, runtime.engine.control
            assert rig.control.policy.maximum_green_seconds == 180
            assert rig.control.policy.maximum_plan_horizon_seconds == 300
            assert rig.send('observe').outcome == 'applied'
            assert rig.send('activate').outcome == 'accepted'
            assert rig.send('plan', green_seconds=180,
                plan_valid_until=clock.utcnow()+timedelta(seconds=300)).outcome == 'accepted'
            rig.advance(3)
            assert rig.engine.phase == 'green' and rig.engine.active_approach == 'T'
            rig.advance(160)
            assert rig.engine.phase == 'green' and rig.control.state == 'adaptive'
            rig.advance(4, data=False)
            assert rig.control.state != 'adaptive' and rig.control.session is None
        finally:
            await runtime.stop()
    asyncio.run(scenario())
