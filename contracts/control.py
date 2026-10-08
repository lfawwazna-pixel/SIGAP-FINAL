"""Protocol between an authenticated decision service and the ATCS arbiter."""
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from contracts.models import Contract, Direction
from contracts.emergency import EmergencyTarget


class ControlPolicy(Contract):
    heartbeat_timeout_seconds: float = Field(default=3, ge=1, le=30, allow_inf_nan=False)
    data_timeout_seconds: float = Field(default=3, ge=1, le=30, allow_inf_nan=False)
    plan_wait_seconds: float = Field(default=8, ge=1, le=30, allow_inf_nan=False)
    minimum_green_seconds: float = Field(default=10, ge=1, le=60, allow_inf_nan=False)
    maximum_green_seconds: float = Field(default=60, ge=1, le=180, allow_inf_nan=False)
    maximum_command_ttl_seconds: float = Field(default=5, ge=1, le=10, allow_inf_nan=False)
    maximum_plan_horizon_seconds: float = Field(default=180, ge=10, le=300, allow_inf_nan=False)
    clock_skew_seconds: float = Field(default=1, ge=0, le=2, allow_inf_nan=False)

    @model_validator(mode='after')
    def green_bounds(self):
        if self.maximum_green_seconds < self.minimum_green_seconds:
            raise ValueError('Invalid green limits')
        return self


class Observation(Contract):
    observed_at: AwareDatetime
    usable: bool


class ControlCommand(Contract):
    request_id: UUID
    atcs_run_id: UUID
    sender_id: UUID
    action: Literal['observe', 'activate', 'heartbeat', 'plan', 'release', 'priority']
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    session_id: UUID | None = None
    sequence: int | None = Field(default=None, ge=1, strict=True)
    expected_revision: int | None = Field(default=None, ge=0, strict=True)
    source: Literal['cctv', 'integration_test'] | None = None
    observations: dict[Direction, Observation] | None = None
    approach: Direction | None = None
    green_seconds: float | None = Field(default=None, gt=0, le=180, allow_inf_nan=False)
    plan_valid_until: AwareDatetime | None = None
    priority_target: EmergencyTarget | None = None

    @model_validator(mode='after')
    def fields_for_action(self):
        if self.expires_at <= self.issued_at:
            raise ValueError('Invalid command lifetime')
        common = {'request_id', 'atcs_run_id', 'sender_id', 'action', 'issued_at', 'expires_at'}
        fields = {
            'observe': {'sequence', 'source', 'observations'},
            'activate': {'expected_revision'},
            'heartbeat': {'session_id', 'sequence'},
            'plan': {'session_id', 'sequence', 'approach', 'green_seconds', 'plan_valid_until'},
            'release': {'session_id', 'expected_revision'},
            'priority': {'session_id', 'sequence', 'priority_target'},
        }[self.action]
        if self.model_fields_set - common != fields or any(getattr(self, f) is None for f in fields if f != 'priority_target'):
            raise ValueError('Fields do not match command action')
        if self.action == 'observe' and set(self.observations) != {'U', 'T', 'S', 'B'}:
            raise ValueError('Four observations are required')
        return self


class CommandReceipt(Contract):
    request_id: UUID
    atcs_run_id: UUID
    action: Literal['observe', 'activate', 'heartbeat', 'plan', 'release', 'priority']
    outcome: Literal['accepted', 'applied', 'rejected', 'cancelled']
    code: str
    message: str
    session_id: UUID | None
    revision: int = Field(ge=0)
    received_at: AwareDatetime
    updated_at: AwareDatetime
    duplicate: bool = False


class ControlEvent(Contract):
    sequence: int = Field(ge=1)
    occurred_at: AwareDatetime
    code: str
    message: str
    request_id: UUID | None = None


class ControlStatus(Contract):
    intersection_id: str
    atcs_run_id: UUID
    observed_at: AwareDatetime
    available: bool
    configured: bool
    allow_test_source: bool
    state: Literal['fixed_time', 'activating', 'adaptive', 'returning_atcs']
    controller: Literal['ATCS', 'SIGAP']
    revision: int = Field(ge=0)
    sender_id: UUID | None
    source: Literal['cctv', 'integration_test'] | None
    ready: bool
    readiness_reason: str
    activation_required: bool
    session_id: UUID | None
    heartbeat_remaining_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    data_remaining_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    pending_request_id: UUID | None
    active_request_id: UUID | None
    fallback_code: str | None
    reason: str
    policy: ControlPolicy
    events: list[ControlEvent] = Field(max_length=100)
    emergency: EmergencyTarget | None = None
    emergency_serving: bool = False


class OperatorControl(Contract):
    request_id: UUID
    action: Literal['activate', 'release']
    expected_run_id: UUID
    expected_revision: int = Field(ge=0, strict=True)
