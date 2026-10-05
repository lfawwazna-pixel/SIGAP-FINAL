"""Measurements are independent of the video decoder and the phase controller."""
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from contracts.models import Contract, Direction
from contracts.vehicles import VehicleView


class ApproachMeasurement(Contract):
    observed_at: AwareDatetime
    usable: bool
    controlled_count: int = Field(ge=0, le=10000)
    queue_count: int = Field(ge=0, le=10000)
    oldest_wait_seconds: float = Field(ge=0, allow_inf_nan=False)
    slip_count: int = Field(ge=0, le=10000)
    exit_available: bool

    @model_validator(mode='after')
    def counts(self):
        if self.queue_count > self.controlled_count:
            raise ValueError('Queue exceeds controlled demand')
        return self


class MeasurementBatch(Contract):
    intersection_id: str
    source: Literal['synthetic', 'recording', 'cctv']
    source_session: UUID
    sequence: int = Field(ge=0)
    approaches: dict[Direction, ApproachMeasurement] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def coverage(self):
        if set(self.approaches) != set('UTSB'):
            raise ValueError('All four approaches must be explicit, including unusable ones')
        return self


class AdaptivePolicyConfig(Contract):
    minimum_green: float = Field(default=10, ge=1, le=60)
    maximum_green: float = Field(default=60, ge=1, le=180)
    queue_weight: float = Field(default=4, ge=0, le=100)
    wait_weight: float = Field(default=1, ge=0, le=100)
    age_weight: float = Field(default=.5, ge=0, le=100)
    service_age_target: float = Field(default=120, ge=10, le=1800)
    seconds_per_queued_vehicle: float = Field(default=2, ge=.1, le=10)
    data_timeout: float = Field(default=3, ge=.5, le=30)

    @model_validator(mode='after')
    def bounds(self):
        if self.minimum_green > self.maximum_green:
            raise ValueError('Invalid green bounds')
        return self


class AdaptiveDecision(Contract):
    decided_at: AwareDatetime
    measurement_sequence: int
    approach: Direction | None
    green_seconds: float | None
    reason: str
    scores: dict[Direction, float] = Field(min_length=4, max_length=4)
    inputs: dict[Direction, ApproachMeasurement] = Field(min_length=4, max_length=4)
    request_id: UUID | None = None
    outcome: Literal['preview', 'accepted', 'applied', 'rejected', 'cancelled'] = 'preview'


class AdaptiveStatus(Contract):
    enabled: bool
    source: Literal['synthetic', 'recording', 'cctv']
    fault: Literal['none', 'frozen_data', 'invalid_data', 'sender_stopped']
    status: Literal['disabled', 'ready', 'active', 'unavailable']
    message: str
    policy: AdaptivePolicyConfig
    measurements: MeasurementBatch | None
    decisions: list[AdaptiveDecision]
    auto_resume: bool = False
    source_sessions: dict[Direction, UUID] = Field(default_factory=dict)
    issues: dict[Direction, str] = Field(default_factory=dict)
    map_vehicles: list[VehicleView] = Field(default_factory=list)
