"""Deterministic fixed-time controller. Only the runtime ticks it; GET never does."""
from collections import deque
from datetime import datetime
import math
from uuid import UUID, uuid4

from contracts.models import AtcsStatus, ConflictArea, IntersectionConfig, TrafficEvent, TrafficEvents


class FixedTimeEngine:
    def __init__(self, config: IntersectionConfig, *, now: float, at: datetime,
                 conflict: ConflictArea, event_capacity: int = 1000):
        if not math.isfinite(now) or event_capacity < 1:
            raise ValueError("Invalid clock or journal capacity")
        self.config = config.model_copy(deep=True)
        self.run_id = uuid4()
        self.state = "running"
        self.phase = "all_red"
        self.active_approach = None
        self.next_index = 0
        self.clearance_state = "minimum"
        self.deadline = now + config.fixed_time.all_red_min_seconds
        self.started = self.last_tick = now
        self.updated_at = at
        self.conflict = conflict.model_copy(deep=True)
        self.sequence_number = 0
        self.reason = f"Startup: semua merah minimum sebelum pendekat {config.fixed_time.sequence[0]}."
        self._event_sequence = 0
        self._events: deque[TrafficEvent] = deque(maxlen=event_capacity)
        self._record("service_started", self.reason, None, None)

    def _record(self, event_type, reason, previous_phase, previous_approach):
        self._event_sequence += 1
        self._events.append(TrafficEvent(
            event_id=f"{self.run_id}:{self._event_sequence}", run_id=self.run_id,
            intersection_id=self.config.intersection_id, event_type=event_type, source="atcs",
            sequence_number=self._event_sequence, occurred_at=self.updated_at,
            simulation_time_seconds=self.last_tick - self.started, reason=reason,
            previous_phase=previous_phase, previous_approach=previous_approach,
            phase=self.phase, active_approach=self.active_approach,
        ))

    def _transition(self, phase, approach, duration, reason):
        previous = (self.phase, self.active_approach)
        self.phase, self.active_approach = phase, approach
        # Start a full interval at the actual transition. Never replay missed phases.
        self.deadline = self.last_tick + duration
        self.clearance_state = "minimum" if phase == "all_red" else None
        self.reason = reason
        self._record("phase_changed", reason, *previous)

    def tick(self, *, now: float, at: datetime, conflict: ConflictArea):
        if self.state != "running":
            return
        if not math.isfinite(now) or now < self.last_tick:
            raise ValueError("Clock must be finite and monotonic")
        self.last_tick, self.updated_at = now, at
        self.sequence_number += 1
        self.conflict = conflict.model_copy(deep=True)
        if now < self.deadline:
            return
        timing = self.config.fixed_time
        if self.phase == "green":
            self._transition("yellow", self.active_approach, timing.yellow_seconds,
                             f"Hijau {self.active_approach} selesai; transisi kuning.")
        elif self.phase == "yellow":
            self.next_index = (self.next_index + 1) % len(timing.sequence)
            self._transition("all_red", None, timing.all_red_min_seconds,
                             f"Kuning selesai; semua merah sebelum {timing.sequence[self.next_index]}.")
        elif conflict.state != "clear":
            self.reason = ("Semua merah diperpanjang: area konflik terisi." if conflict.state == "occupied"
                           else "Semua merah diperpanjang: keadaan area konflik tidak diketahui.")
            if self.clearance_state != "waiting_conflict":
                self.clearance_state = "waiting_conflict"
                self._record("clearance_held", self.reason, self.phase, self.active_approach)
        else:
            if self.clearance_state == "waiting_conflict":
                self._record("clearance_released", "Area konflik kosong; pendekat berikutnya dapat dimulai.",
                             self.phase, self.active_approach)
            approach = timing.sequence[self.next_index]
            self._transition("green", approach, timing.green_seconds[approach],
                             f"Fase hijau {approach} sesuai konfigurasi fixed-time.")

    def end(self, *, at: datetime, fault: bool = False):
        if self.state != "running":
            return
        previous = (self.phase, self.active_approach)
        self.state = "faulted" if fault else "stopped"
        self.phase, self.active_approach = "all_red", None
        self.clearance_state = None
        self.deadline = None
        self.updated_at = at
        self.sequence_number += 1
        self.reason = ("Mesin fase mengalami gangguan; sesi perlu dimulai ulang." if fault
                       else "Sesi simulasi dihentikan; restart akan memulai semua merah dan sesi baru.")
        self._record("fault" if fault else "service_stopped", self.reason, *previous)

    def snapshot(self, observed_at: datetime) -> AtcsStatus:
        signals = dict.fromkeys(self.config.fixed_time.sequence, "red")
        if self.active_approach is not None:
            signals[self.active_approach] = self.phase
        remaining = None
        if self.deadline is not None and self.clearance_state != "waiting_conflict":
            remaining = max(0.0, self.deadline - self.last_tick)
        return AtcsStatus(
            intersection_id=self.config.intersection_id, run_id=self.run_id,
            availability="available" if self.state == "running" else "unavailable",
            engine_state=self.state, controller="ATCS", mode="fixed_time",
            active_approach=self.active_approach, phase=self.phase, signals=signals,
            clearance_state=self.clearance_state, conflict_area=self.conflict.model_copy(deep=True),
            remaining_seconds=remaining, simulation_time_seconds=self.last_tick - self.started,
            sequence_number=self.sequence_number, updated_at=self.updated_at,
            observed_at=observed_at, reason=self.reason,
        )

    def events(self, *, at: datetime, after: int = 0, limit: int = 100,
               run_id: UUID | None = None) -> TrafficEvents:
        if after < 0 or not 1 <= limit <= 500:
            raise ValueError("Invalid event cursor or limit")
        changed = run_id is not None and run_id != self.run_id
        cursor = 0 if changed else after
        if cursor > self._event_sequence:
            raise ValueError("CURSOR_AHEAD")
        oldest = self._events[0].sequence_number
        items = [event.model_copy(deep=True) for event in self._events if event.sequence_number > cursor][:limit]
        next_after = items[-1].sequence_number if items else cursor
        return TrafficEvents(
            intersection_id=self.config.intersection_id, run_id=self.run_id, events=items,
            oldest_available_sequence=oldest, latest_sequence=self._event_sequence,
            next_after=next_after, has_more=next_after < self._event_sequence,
            history_truncated=cursor < oldest - 1, run_changed=changed, generated_at=at,
        )
