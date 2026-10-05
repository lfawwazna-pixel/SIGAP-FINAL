from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, model_validator
from contracts.models import Contract, Direction, Phase, Signal
from contracts.adaptive import AdaptiveDecision
from contracts.vehicles import VehicleView

Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ExperimentEvent(Contract):
    time: Nonnegative
    message: str


class TrafficView(Contract):
    decision: AdaptiveDecision | None = None
    intersection_id: str
    source: Literal['atcs_synthetic', 'experiment']
    run_id: UUID
    observed_at: AwareDatetime
    available: bool
    time_seconds: Nonnegative
    running: bool
    speed: Literal[1, 2, 3]
    strategy: Literal['fixed_time', 'adaptive']
    phase: Phase | None
    active_approach: Direction | None
    signals: dict[Direction, Signal] | None
    remaining_seconds: Nonnegative | None
    emergency: bool
    target_vehicle: int | None
    reason: str
    demand: dict[Direction, Annotated[int, Field(ge=0, le=60)]]
    blocked_exit: Direction | None
    events: list[ExperimentEvent] = Field(max_length=100)
    evp_queue: list[int] = Field(max_length=160)
    vehicles: list[VehicleView] = Field(max_length=160)
    queues: dict[Direction, Annotated[int, Field(ge=0)]]
    completed: int = Field(ge=0)
    average_wait: Nonnegative
    waiting_seconds: Nonnegative
    refused_spawns: int = Field(ge=0)
    conflict: Literal['clear', 'occupied', 'unknown']
    traffic_sequence: int = Field(ge=0)

    @model_validator(mode='after')
    def consistent(self):
        directions = {'U', 'T', 'S', 'B'}
        if set(self.queues) != directions or set(self.demand) != directions:
            raise ValueError('Four approaches required')
        if self.signals is not None:
            expected = {d: self.phase if d == self.active_approach else 'red' for d in directions}
            if self.signals != expected or (self.phase == 'all_red') != (self.active_approach is None):
                raise ValueError('Conflicting signals')
        if self.available and (self.signals is None or self.phase is None):
            raise ValueError('Available traffic requires controller signals')
        if self.source == 'atcs_synthetic' and (self.speed != 1 or self.emergency):
            raise ValueError('Main ATCS cannot use sandbox speed or emergency controls')
        return self


class SimulationCommand(Contract):
    action: Literal['start', 'pause', 'reset', 'configure', 'spawn']
    expected_run_id: UUID
    speed: Literal[1, 2, 3] | None = None
    strategy: Literal['fixed_time', 'adaptive'] | None = None
    demand: dict[Direction, Annotated[int, Field(ge=0, le=60, strict=True)]] | None = None
    blocked_exit: Direction | Literal['none'] | None = None
    direction: Direction | None = None
    kind: Literal['ambulance', 'fire_engine'] | None = None

    @model_validator(mode='after')
    def valid_action(self):
        extra = self.model_fields_set - {'action', 'expected_run_id'}
        if self.action in ('start', 'pause', 'reset') and extra:
            raise ValueError('Unexpected action fields')
        if self.action == 'configure' and (not extra or extra - {'speed', 'strategy', 'demand', 'blocked_exit'}):
            raise ValueError('Invalid configuration')
        if self.action == 'configure' and any(getattr(self, f) is None for f in extra):
            raise ValueError('Missing configuration value')
        if self.demand is not None and set(self.demand) != {'U', 'T', 'S', 'B'}:
            raise ValueError('Four arrival rates required')
        if self.action == 'spawn' and (extra != {'direction', 'kind'} or None in (self.direction, self.kind)):
            raise ValueError('Spawn requires direction and kind; entry is always upstream')
        return self
