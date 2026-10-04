from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from atcs_simulator.app.control import ManagedEngine
from atcs_simulator.app.control_settings import ControlSettings
from contracts.configuration import load_config
from contracts.control import ControlCommand, ControlPolicy, ControlStatus
from contracts.models import AtcsStatus, ConflictArea


class Rig:
    def __init__(self, clock):
        self.clock = clock
        self.sender = uuid4()
        self.sequences = dict(observe=0, heartbeat=0, plan=0)
        self.engine = ManagedEngine(load_config(), now=clock.monotonic(), at=clock.utcnow(),
            conflict=self.conflict(), control_settings=ControlSettings(_env_file=None,
                sigap_control_api_key=SecretStr('test-only-key-'*4), atcs_enable_test_source=True))
        self.control = self.engine.control

    def conflict(self, state='clear'):
        return ConflictArea(state=state, source='provider', checked_at=self.clock.utcnow())

    def command(self, action, **values):
        at = self.clock.utcnow()
        fields = dict(request_id=uuid4(), atcs_run_id=self.engine.run_id, sender_id=self.sender,
                      action=action, issued_at=at, expires_at=at+timedelta(seconds=3))
        if action in self.sequences:
            self.sequences[action] += 1
            fields['sequence'] = self.sequences[action]
        if action in ('heartbeat', 'plan', 'release'):
            fields['session_id'] = self.control.session
        if action in ('activate', 'release'):
            fields['expected_revision'] = self.control.revision
        if action == 'observe':
            fields.update(source='integration_test', observations={d: dict(observed_at=at, usable=True) for d in 'UTSB'})
        if action == 'plan':
            fields.update(approach='T', green_seconds=10, plan_valid_until=at+timedelta(seconds=120))
        return ControlCommand(**{**fields, **values})

    def send(self, action, **values):
        command = self.command(action, **values)
        return self.submit(command)

    def submit(self, command):
        return self.control.submit(command, self.clock.monotonic(), self.clock.utcnow())

    def advance(self, seconds=1, *, data=True, heartbeat=True, conflict='clear'):
        for _ in range(seconds):
            self.clock.advance(1)
            if data:
                self.send('observe')
            if heartbeat and self.control.session:
                self.send('heartbeat')
            self.engine.tick(now=self.clock.monotonic(), at=self.clock.utcnow(), conflict=self.conflict(conflict))
            AtcsStatus.model_validate(self.engine.snapshot(self.clock.utcnow()).model_dump())
            ControlStatus.model_validate(self.control.snapshot(self.clock.monotonic(), self.clock.utcnow()).model_dump())

    def activate(self):
        self.send('observe')
        acquired = self.send('activate')
        assert acquired.outcome == 'accepted'
        plan = self.send('plan')
        assert plan.outcome == 'accepted'
        return acquired, plan


@pytest.fixture
def rig(clock):
    return Rig(clock)


def test_handover_waits_min_green_yellow_allred_and_conflict(rig):
    rig.advance(2)
    assert rig.engine.active_approach == 'U'
    acquired, plan = rig.activate()
    rig.advance(9)
    assert rig.engine.phase == 'green'
    assert rig.engine.snapshot(rig.clock.utcnow()).remaining_seconds == 1
    rig.advance()
    assert rig.engine.phase == 'yellow'
    rig.advance(2)
    assert rig.engine.phase == 'yellow'
    rig.advance()
    assert rig.engine.phase == 'all_red'
    rig.advance(2, conflict='occupied')
    assert rig.engine.clearance_state == 'waiting_conflict'
    rig.advance(conflict='unknown')
    assert rig.engine.phase == 'all_red'
    rig.advance()
    assert rig.engine.active_approach == 'T'
    assert rig.control.state == 'adaptive'
    assert rig.control.receipts[plan.request_id][1].outcome == 'applied'
    assert rig.control.receipts[acquired.request_id][1].code == 'CONTROL_ACQUIRED'


@pytest.mark.parametrize('failure,expected', [('heartbeat', 'HEARTBEAT_LOST'), ('data', 'DATA_UNUSABLE')])
def test_independent_watchdogs_and_no_automatic_recovery(rig, failure, expected):
    rig.activate()
    rig.advance(2)
    previous_run, previous_session = rig.engine.run_id, rig.control.session
    rig.advance(4, data=failure != 'data', heartbeat=failure != 'heartbeat')
    assert rig.control.fallback_code == expected
    assert rig.control.session is None
    assert rig.send('heartbeat', session_id=previous_session).code == 'SESSION_REVOKED'
    rig.advance(20)
    assert rig.control.state == 'fixed_time'
    assert rig.engine.run_id == previous_run
    assert rig.engine.active_approach == 'S'  # Continue after last SIGAP phase T.
    assert rig.control.snapshot(rig.clock.monotonic(), rig.clock.utcnow()).ready
    assert rig.control.session is None
    assert rig.send('activate').outcome == 'accepted'
    assert rig.control.session != previous_session


def test_repeated_frames_do_not_refresh_data_even_with_live_heartbeat(rig):
    rig.activate()
    observations = rig.control.observations.copy()
    rig.advance(2, data=False)
    rig.send('observe', observations=observations)
    rig.advance(1, data=False)
    assert rig.control.fallback_code == 'DATA_UNUSABLE'


def test_duplicate_heartbeat_and_changed_request_cannot_extend_lease(rig):
    rig.activate()
    command = rig.command('heartbeat')
    first = rig.submit(command)
    deadline = rig.control.heartbeat_deadline
    rig.advance(2, heartbeat=False)
    repeated = rig.submit(command)
    assert repeated.duplicate and repeated.request_id == first.request_id
    assert rig.control.heartbeat_deadline == deadline
    assert rig.submit(command.model_copy(update={'sequence': 999})).code == 'REQUEST_ID_REUSED'
    rig.advance(1, heartbeat=False)
    assert rig.control.fallback_code == 'HEARTBEAT_LOST'


def test_expired_out_of_order_wrong_run_and_bounds(rig):
    rig.activate()
    assert rig.send('plan', green_seconds=9).code == 'GREEN_BOUNDS'
    assert rig.send('plan', green_seconds=61).code == 'GREEN_BOUNDS'
    assert rig.send('plan', plan_valid_until=rig.clock.utcnow()+timedelta(seconds=5)).code == 'PLAN_LIFETIME'
    assert rig.send('plan', sequence=1).code == 'OUT_OF_ORDER'
    assert rig.send('heartbeat', atcs_run_id=uuid4()).code == 'RUN_CHANGED'
    old = rig.command('heartbeat', issued_at=rig.clock.utcnow()-timedelta(seconds=4), expires_at=rig.clock.utcnow()-timedelta(seconds=1))
    assert rig.submit(old).code == 'COMMAND_EXPIRED'
    assert rig.send('activate', expected_revision=999).code == 'REVISION_CHANGED'


def test_no_decision_and_expired_queued_decision_fall_back(rig):
    rig.send('observe')
    rig.send('activate')
    rig.advance(8)
    assert rig.control.fallback_code == 'PLAN_MISSING'


def test_missing_next_plan_holds_allred_then_returns_atcs(rig):
    rig.activate()
    rig.advance(17)
    assert rig.engine.clearance_state == 'waiting_command'
    assert rig.engine.snapshot(rig.clock.utcnow()).remaining_seconds == 8
    rig.advance(8)
    assert rig.control.fallback_code == 'PLAN_MISSING'
    assert rig.control.state == 'fixed_time'


def test_plan_must_remain_valid_for_full_green_when_applied(rig):
    rig.send('observe')
    rig.send('activate')
    receipt = rig.send('plan', plan_valid_until=rig.clock.utcnow()+timedelta(seconds=10))
    rig.advance(2)
    assert rig.control.fallback_code == 'PLAN_EXPIRED'
    assert rig.engine.phase == 'all_red'
    assert rig.control.receipts[receipt.request_id][1].outcome == 'cancelled'


def test_release_has_separate_acceptance_and_application(rig):
    rig.activate()
    rig.advance(2)
    receipt = rig.send('release')
    assert receipt.outcome == 'accepted'
    assert rig.control.state == 'returning_atcs'
    rig.advance(15)
    assert rig.control.state == 'fixed_time'
    assert rig.control.receipts[receipt.request_id][1].code == 'RELEASED'
    assert rig.engine.active_approach == 'S'


def test_new_sender_revokes_lease_and_rejects_old_process(rig):
    rig.activate()
    old = rig.sender
    rig.sender = uuid4()
    rig.send('observe')
    assert rig.control.fallback_code == 'SOURCE_RESTART'
    assert rig.send('observe', sender_id=old).code == 'SENDER_RETIRED'


def test_wall_clock_changes_do_not_extend_existing_watchdogs(rig):
    rig.activate()
    deadline = rig.control.heartbeat_deadline
    rig.clock.wall_offset -= 3600
    rig.advance(3, data=False, heartbeat=False)
    assert rig.control.session is None
    assert deadline <= rig.clock.monotonic()


def test_plan_replacement_and_maximum_green_are_enforced(rig):
    acquired, first = rig.activate()
    second = rig.send('plan', approach='B')
    assert rig.control.receipts[first.request_id][1].code == 'SUPERSEDED'
    rig.advance(2)
    assert rig.engine.active_approach == 'B'
    rig.send('plan', approach='B', green_seconds=60)
    rig.advance(10)
    assert rig.engine.phase == 'yellow'  # A new plan never extends the active green.
    rig.advance(5)
    assert rig.engine.phase == 'green' and rig.engine.active_approach == 'B'
    assert rig.control.receipts[second.request_id][1].outcome == 'applied'


def test_disabled_test_source_and_invalid_action_fields(rig):
    rig.control.settings.atcs_enable_test_source = False
    assert rig.send('observe').code == 'TEST_SOURCE_DISABLED'
    assert rig.send('activate').code == 'NOT_READY'
    with pytest.raises(ValidationError):
        ControlCommand.model_validate({**rig.command('observe').model_dump(mode='json', exclude_none=True), 'green_seconds': 10})
    with pytest.raises(ValidationError):
        rig.command('observe', observations={'U': dict(observed_at=rig.clock.utcnow(), usable=True)})
