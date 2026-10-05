import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from adaptive.policy import AdaptivePolicy, measure_world
from atcs_simulator.app.traffic import TrafficWorld
from atcs_simulator.app.experiment import Experiment
from backend.app.adaptive import AdaptiveSender
from backend.app.settings import Settings
from contracts.adaptive import MeasurementBatch
from contracts.configuration import load_config
from contracts.control import ControlCommand
from test_control import Rig
from test_auth import auth_context, login, ORIGIN
from test_control_api import connected, observation, operator_request, KEY

AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def measurements(at=AT, **overrides):
    values = {d: dict(observed_at=at, usable=True, controlled_count=0, queue_count=0,
                     oldest_wait_seconds=0, slip_count=0, exit_available=True) for d in 'UTSB'}
    for d, fields in overrides.items():
        values[d].update(fields)
    return MeasurementBatch(intersection_id=load_config().intersection_id, source='synthetic',
                            source_session=uuid4(), sequence=1, approaches=values)


def test_priority_bounds_slips_and_applied_only_fairness():
    policy = AdaptivePolicy()
    batch = measurements(U=dict(slip_count=1000), T=dict(controlled_count=50, queue_count=50),
                         B=dict(controlled_count=1, queue_count=1, oldest_wait_seconds=250))
    decision = policy.choose(batch, 0, AT)
    assert decision.approach == 'B' and decision.green_seconds == 12
    assert policy.previous is None and set(policy.last_served.values()) == {0}
    policy.served('B', 1)
    decision = policy.choose(batch, 2, AT)
    assert decision.approach == 'T' and decision.green_seconds == 60
    policy.served('T', 2)
    empty = policy.choose(measurements(), 3, AT)
    assert empty.green_seconds == 10 and empty.approach != 'T'


def test_small_queues_are_served_under_continuous_heavy_demand():
    policy = AdaptivePolicy()
    batch = measurements(**{d: dict(controlled_count=100 if d == 'U' else 1,
                                   queue_count=100 if d == 'U' else 1) for d in 'UTSB'})
    served = []
    now = 0
    for _ in range(12):
        decision = policy.choose(batch, now, AT)
        served.append(decision.approach)
        policy.served(decision.approach, now)
        now += decision.green_seconds+5
    assert set(served[:6]) == set('UTSB')
    assert all(now-policy.last_served[d] <= 185 for d in 'UTSB')


@pytest.mark.parametrize('age,usable', [(3.01, True), (-.51, True), (0, False)])
def test_bad_measurement_never_produces_a_plan(age, usable):
    batch = measurements(U=dict(observed_at=AT-timedelta(seconds=age), usable=usable))
    assert AdaptivePolicy().choose(batch, 0, AT).approach is None


def test_blocked_exits_and_deterministic_ties():
    policy = AdaptivePolicy()
    batch = measurements(**{d: dict(controlled_count=2, queue_count=2) for d in 'UTSB'})
    assert policy.choose(batch, 0, AT).approach == 'U'
    batch.approaches['U'].exit_available = False
    assert policy.choose(batch, 0, AT).approach == 'T'
    for v in batch.approaches.values():
        v.exit_available = False
    assert policy.choose(batch, 0, AT).approach is None


def test_measurement_contract_and_lane_classification():
    with pytest.raises(ValidationError):
        measurements(U=dict(queue_count=5, controlled_count=1))
    world = TrafficWorld(demand=0)
    slip = world.spawn('U', movement='left')
    slip.distance = 200
    straight = world.spawn('U', movement='straight')
    straight.stopped, straight.wait = True, 25
    batch = measure_world(world, load_config().intersection_id, uuid4(), AT)
    assert batch.approaches['U'].controlled_count == batch.approaches['U'].queue_count == 1
    assert batch.approaches['U'].slip_count == 1
    assert batch.approaches['U'].oldest_wait_seconds == 25


@pytest.mark.parametrize('fault,expected', [('frozen_data', 'DATA_UNUSABLE'),
    ('invalid_data', 'DATA_UNUSABLE'), ('sender_stopped', 'DATA_UNUSABLE')])
def test_autonomous_sender_apply_fallback_and_manual_recovery(clock, monkeypatch, fault, expected):
    import backend.app.adaptive as module
    class ControlledDate:
        @staticmethod
        def now(tz):
            return clock.utcnow()
    monkeypatch.setattr(module, 'datetime', ControlledDate)
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=clock.monotonic))
    rig = Rig(clock)
    settings = Settings(_env_file=None, sigap_adaptive_synthetic=True, sigap_control_api_key=SecretStr('test-only-key-'*4))
    sender = AdaptiveSender(settings, load_config().intersection_id)
    plans = []

    def transport(request):
        if request.url.path == '/control':
            value = rig.control.snapshot(clock.monotonic(), clock.utcnow())
        elif request.url.path == '/measurements':
            value = measurements(clock.utcnow(), T=dict(controlled_count=3, queue_count=3))
            value.source_session = rig.engine.run_id
            value.sequence = int(clock.elapsed*10)
        elif request.url.path == '/status':
            value = rig.engine.snapshot(clock.utcnow())
        else:
            cmd = ControlCommand.model_validate_json(request.content)
            value = rig.submit(cmd)
            if cmd.action == 'plan':
                plans.append(cmd)
        return httpx.Response(200, json=value.model_dump(mode='json'))

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url='http://atcs') as client:
            sender.client = client
            await sender.cycle()
            assert sender.state == 'ready' and rig.control.session is None  # no implicit acquisition
            rig.sender = sender.sender
            assert rig.send('activate').outcome == 'accepted'
            async def advance(n):
                for _ in range(n):
                    clock.advance(.5)
                    rig.engine.tick(now=clock.monotonic(), at=clock.utcnow(), conflict=rig.conflict())
                    await sender.cycle()
            await advance(100)
            assert rig.control.state == 'adaptive'
            assert any(d.outcome == 'applied' for d in sender.decisions)
            assert all(10 <= p.green_seconds <= 60 for p in plans)
            assert sender.policy.previous in 'UTSB'
            run = rig.engine.run_id
            sender.fault = fault
            await advance(12)
            assert rig.control.fallback_code == expected
            assert rig.control.session is None
            if fault == 'sender_stopped':
                assert sender.snapshot().measurements is None and sender.preview is None
            sender.fault = 'none'
            await advance(40)
            assert rig.control.state == 'fixed_time' and rig.control.session is None
            assert rig.engine.run_id == run and sender.state == 'ready'
            assert rig.send('activate').outcome == 'accepted'
            await advance(40)
            assert rig.control.state == 'adaptive'
    asyncio.run(scenario())


def test_adaptive_endpoints_require_auth_csrf_and_explicit_enable(auth_context):
    client, app, _, _ = auth_context
    assert client.get('/api/adaptive').status_code == 401
    view = login(client).json()
    assert client.get('/api/adaptive').json()['status'] == 'disabled'
    assert client.post('/api/adaptive/fault', headers=ORIGIN, json={'fault': 'none'}).status_code == 403
    assert client.post('/api/adaptive/hold', headers=ORIGIN, json={}).status_code == 403
    headers = {**ORIGIN, 'X-CSRF-Token': view['csrf_token']}
    assert client.post('/api/adaptive/fault', headers=headers, json={'fault': 'none'}).status_code == 409
    assert client.post('/api/adaptive/hold', headers=headers, json={}).status_code == 409
    app.state.adaptive.enabled = True
    assert client.post('/api/adaptive/fault', headers=headers, json={'fault': 'frozen_data'}).status_code == 200
    assert client.post('/api/adaptive/fault', headers=headers, json={'fault': 'none', 'extra': True}).status_code == 422


def test_evp_suspends_policy_then_recomputes_from_current_world():
    exp = Experiment(load_config())
    exp.world.demand = dict.fromkeys('UTSB', 0)
    car = exp.world.spawn('T', kind='ambulance')
    seen_emergency = False
    for _ in range(2200):
        exp.tick(.05)
        if exp.emergency:
            seen_emergency = True
            assert exp.decision is None
        if seen_emergency and not exp.emergency:
            assert exp.decision.outcome == 'applied'
            assert exp.decision.measurement_sequence == exp.world.sequence
            assert not exp.world.candidates()
            break
    else:
        pytest.fail('EVP did not finish and return to adaptive policy')


def test_operator_test_source_requires_both_gates(connected, clock):
    client, app, atcs, atcs_app = connected
    atcs_app.state.runtime.engine.control.settings.atcs_enable_test_source = True
    csrf = login(client).json()['csrf_token']
    payload = observation(atcs.get('/control').json(), clock.utcnow(), source='integration_test')
    assert atcs.post('/control/commands', headers={'Authorization':'Bearer '+KEY}, json=payload).status_code == 200
    headers = {**ORIGIN,'X-CSRF-Token':csrf}
    assert client.post('/api/control/commands',headers=headers,json=operator_request(client)).status_code == 409
    app.state.control.settings.sigap_adaptive_synthetic = True
    result = client.post('/api/control/commands',headers=headers,json=operator_request(client))
    assert result.status_code == 200 and result.json()['outcome'] == 'accepted'


def test_measurements_endpoint_requires_service_key(connected):
    _, _, atcs, _ = connected
    assert atcs.get('/measurements').status_code == 401
    data = atcs.get('/measurements',headers={'Authorization':'Bearer '+KEY})
    batch = MeasurementBatch.model_validate(data.json())
    assert batch.source == 'synthetic' and set(batch.approaches) == set('UTSB')


def test_evaluation_trace_and_results_repeat_without_reseeding_on_admission():
    from adaptive.evaluate import arrivals, run
    trace = arrivals(7,'changing',30)
    assert trace == arrivals(7,'changing',30)
    result = run(trace,'adaptive',30,20)
    assert result == run(trace,'adaptive',30,20)
    assert result['attempted'] == result['admitted']+result['refused']
    assert result['admitted'] == result['completed']+result['residual']
