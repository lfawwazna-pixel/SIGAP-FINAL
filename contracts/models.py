from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Direction = Literal["U", "T", "S", "B"]
Phase = Literal["green", "yellow", "all_red"]
Signal = Literal["red", "yellow", "green"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Geometry(Contract):
    driving_side: Literal["left"]
    incoming_lanes_per_approach: Literal[2]
    outgoing_lanes_per_approach: Literal[2]
    median: Literal[True]
    left_turn_slip_roads: Literal[4]
    separating_islands: Literal[True]
    left_turn_signal_controlled: Literal[False]
    yield_at_merge: Literal[True]
    u_turn_allowed: Literal[False]
    lane_change_in_intersection: Literal[False]
    block_entry_when_exit_blocked: Literal[True]
    complete_committed_movement: Literal[True]
    slip_fork_before_stop_line: Literal[True]
    slip_merge_after_intersection: Literal[True]


class OuterLane(Contract):
    left: Direction
    straight: Direction


class InnerLane(Contract):
    straight: Direction
    right: Direction


class Approach(Contract):
    code: Direction
    road: str = Field(min_length=1)
    side: str = Field(min_length=1)
    outer: OuterLane
    inner: InnerLane


class FixedTime(Contract):
    sequence: list[Direction] = Field(min_length=4, max_length=4)
    green_seconds: dict[Direction, Annotated[int, Field(gt=0, strict=True)]]
    yellow_seconds: int = Field(gt=0, strict=True)
    all_red_min_seconds: int = Field(gt=0, strict=True)
    nominal_cycle_seconds: int = Field(gt=0, strict=True)
    extend_all_red_until_conflict_clear: Literal[True]

    @model_validator(mode="after")
    def valid_cycle(self):
        directions = {"U", "T", "S", "B"}
        if set(self.sequence) != directions or set(self.green_seconds) != directions:
            raise ValueError("Siklus harus memuat U, T, S, B tepat sekali.")
        if any(type(value) is not int or value <= 0 for value in self.green_seconds.values()):
            raise ValueError("Durasi hijau harus bilangan bulat positif.")
        total = sum(self.green_seconds.values()) + 4 * (self.yellow_seconds + self.all_red_min_seconds)
        if total != self.nominal_cycle_seconds:
            raise ValueError("Siklus nominal tidak sama dengan jumlah durasi fase.")
        return self


class Provenance(Contract):
    timing_source_url: str
    timing_source_year: int
    timing_basis: str
    sequence_basis: str
    geometry_basis: str
    current_field_configuration_verified: Literal[False]


class IntersectionConfig(Contract):
    schema_version: Literal["1.0"]
    intersection_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location: str
    timezone: Literal["Asia/Jakarta"]
    operating_context: Literal["simulation"]
    geometry: Geometry
    approaches: list[Approach] = Field(min_length=4, max_length=4)
    fixed_time: FixedTime
    provenance: Provenance

    @model_validator(mode="after")
    def valid_movements(self):
        ring = ["U", "T", "S", "B"]
        if {item.code for item in self.approaches} != set(ring):
            raise ValueError("Empat pendekat unik diperlukan.")
        for item in self.approaches:
            i = ring.index(item.code)
            if (item.outer.left, item.outer.straight, item.inner.straight, item.inner.right) != (
                ring[(i + 1) % 4], ring[(i + 2) % 4], ring[(i + 2) % 4], ring[(i + 3) % 4]
            ):
                raise ValueError(f"Gerakan pendekat {item.code} tidak sesuai lalu lintas sisi kiri.")
        return self


class Capabilities(Contract):
    phase_engine: Literal["not_implemented", "not_hosted", "running", "faulted", "stopped", "stalled"] = "not_hosted"
    authentication: Literal["not_implemented", "available", "unavailable"] = "not_implemented"
    override: Literal["not_implemented", "available", "unavailable"] = "not_implemented"
    ai: Literal["not_implemented"] = "not_implemented"
    cctv: Literal["not_configured"] = "not_configured"


class DatabaseCheck(Contract):
    status: Literal["not_configured", "unavailable", "reachable", "not_required"]
    schema_status: Literal["current", "missing_or_outdated", "unknown", "not_required"]


class Health(Contract):
    service: Literal["backend", "atcs"]
    stage: Literal["2A", "2B", "2D", "2F", "4"] = "2B"
    liveness: Literal["alive"] = "alive"
    foundation_ready: bool
    checked_at: AwareDatetime
    configuration: Literal["valid"] = "valid"
    database: DatabaseCheck
    capabilities: Capabilities = Field(default_factory=Capabilities)


class OperatorView(Contract):
    id: UUID
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    role: Literal["operator"] = "operator"
    permissions: list[Literal["monitor:read", "control:operate"]] = Field(default_factory=lambda: ["monitor:read", "control:operate"], min_length=1, max_length=2)


class SessionView(Contract):
    operator: OperatorView
    expires_at: AwareDatetime
    remaining_seconds: int = Field(gt=0, le=86400)
    csrf_token: str = Field(pattern=r"^[a-f0-9]{64}$")


class ConflictArea(Contract):
    state: Literal["clear", "occupied", "unknown"]
    source: Literal["assumed_clear", "provider"]
    checked_at: AwareDatetime


class AtcsStatus(Contract):
    schema_version: Literal["2.0"] = "2.0"
    intersection_id: str
    operating_context: Literal["simulation"] = "simulation"
    availability: Literal["not_implemented", "available", "unavailable"]
    run_id: UUID | None = None
    engine_state: Literal["not_started", "running", "faulted", "stopped", "stalled"] = "not_started"
    controller: Literal["ATCS", "SIGAP"] | None
    mode: Literal["fixed_time", "adaptive", "fallback"] | None
    active_approach: Direction | None
    phase: Phase | None
    signals: dict[Direction, Signal] | None = None
    clearance_state: Literal["minimum", "waiting_conflict", "waiting_command"] | None = None
    conflict_area: ConflictArea | None = None
    remaining_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    simulation_time_seconds: float | None = Field(ge=0, allow_inf_nan=False)
    sequence_number: int | None = Field(ge=0, strict=True)
    updated_at: AwareDatetime | None
    observed_at: AwareDatetime
    reason: str | None

    @model_validator(mode="after")
    def no_fake_phase(self):
        fields = [self.controller, self.mode, self.active_approach, self.phase, self.signals,
                  self.remaining_seconds, self.simulation_time_seconds, self.sequence_number, self.updated_at]
        if self.availability == "not_implemented" and any(v is not None for v in fields):
            raise ValueError("Mesin fase belum tersedia: nilai operasional harus null.")
        if self.phase is not None and (self.phase == "all_red") != (self.active_approach is None):
            raise ValueError("Pendekat aktif tidak sesuai fase.")
        if self.availability == "available":
            required = [self.run_id, self.controller, self.mode, self.phase, self.signals,
                        self.conflict_area, self.simulation_time_seconds, self.sequence_number, self.updated_at]
            if any(v is None for v in required):
                raise ValueError("Status operasional harus lengkap.")
            if self.engine_state != "running":
                raise ValueError("Status tersedia memerlukan mesin berjalan.")
            waiting = self.phase == "all_red" and self.clearance_state == "waiting_conflict"
            if (self.remaining_seconds is None) != waiting:
                raise ValueError("Durasi hanya tidak diketahui ketika semua merah menunggu konflik.")
            if (self.phase == "all_red") != (self.clearance_state is not None):
                raise ValueError("Status clearance hanya berlaku pada semua merah.")
        if self.signals is not None:
            expected = dict.fromkeys(["U", "T", "S", "B"], "red")
            if self.phase in ("green", "yellow") and self.active_approach is not None:
                expected[self.active_approach] = self.phase
            elif self.phase != "all_red":
                raise ValueError("Sinyal memerlukan fase yang valid.")
            if self.signals != expected:
                raise ValueError("Sinyal tidak sesuai fase atau memiliki gerakan bersamaan.")
        return self


class TrafficEvent(Contract):
    event_id: str
    intersection_id: str
    run_id: UUID
    event_type: Literal["service_started", "service_stopped", "phase_changed", "clearance_held", "clearance_released", "control_changed", "fault", "recovered"]
    source: Literal["backend", "atcs", "adaptive_control"]
    sequence_number: int = Field(ge=0)
    occurred_at: AwareDatetime
    simulation_time_seconds: float | None = Field(ge=0)
    reason: str = Field(min_length=1)
    previous_phase: Phase | None
    previous_approach: Direction | None
    phase: Phase
    active_approach: Direction | None


class TrafficEvents(Contract):
    intersection_id: str
    run_id: UUID
    events: list[TrafficEvent]
    oldest_available_sequence: int = Field(ge=1)
    latest_sequence: int = Field(ge=1)
    next_after: int = Field(ge=0)
    has_more: bool
    history_truncated: bool
    run_changed: bool
    generated_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_events(self):
        previous = 0
        for event in self.events:
            if event.intersection_id != self.intersection_id or event.run_id != self.run_id:
                raise ValueError("Kejadian berasal dari simpang atau sesi berbeda.")
            if not self.oldest_available_sequence <= event.sequence_number <= self.latest_sequence:
                raise ValueError("Urutan kejadian di luar rentang riwayat.")
            if event.sequence_number <= previous:
                raise ValueError("Kejadian harus berurutan dan tidak duplikat.")
            previous = event.sequence_number
        if self.events and self.next_after != self.events[-1].sequence_number:
            raise ValueError("Cursor tidak sesuai kejadian terakhir.")
        return self
