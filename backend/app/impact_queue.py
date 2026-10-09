"""Queue experiment with exact event times, separate from operational control."""
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
from adaptive.policy import AdaptivePolicy
from atcs_simulator.app.control_settings import ControlSettings
from contracts.adaptive import MeasurementBatch
from contracts.analytics import ImpactPoint, ApproachImpact, PhaseInterval

DIRECTIONS, KINDS, MOVEMENTS = 'UTSB', ('motorcycle', 'car', 'bus', 'truck'), ('left', 'straight', 'right')
EPS = 1e-8
ANCHOR = datetime(2026, 1, 1, tzinfo=timezone.utc)
SESSION = UUID('00000000-0000-0000-0000-000000000001')


@dataclass(frozen=True)
class Arrival:
    identity: int
    at: float
    direction: str
    movement: str
    kind: str
    observation_mark: float


def queue_rows(queue, spec):
    """Only consecutive motorcycles can share a FIFO row; no overtaking."""
    row, remaining = [], 0
    for vehicle in queue:
        if row and (vehicle.kind != 'motorcycle' or row[0].kind != 'motorcycle' or not remaining):
            yield row
            row = []
        if not row:
            remaining = spec.vehicle_factors[vehicle.kind].parallel_slots
        row.append(vehicle)
        remaining -= 1
    if row:
        yield row


class QueueExperiment:
    def __init__(self, spec, config, arrivals, strategy, keep_series=True):
        self.spec, self.config, self.arrivals, self.strategy = spec, config, arrivals, strategy
        self.keep_series = keep_series
        self.queues = {(d, m): deque() for d in DIRECTIONS for m in MOVEMENTS}
        self.releases, self.rows = dict.fromkeys(self.queues), {}
        self.green_ready = dict.fromkeys(self.queues, 0.)
        self.now, self.cursor, self.fixed_next = 0., 0, 0
        self.phase, self.active = 'all_red', None
        self.deadline = config.fixed_time.all_red_min_seconds
        self.policy = AdaptivePolicy()
        self.policy.config.maximum_green = ControlSettings().atcs_maximum_green_seconds
        self.policy.baseline = config.fixed_time.green_seconds.copy()
        self.by_class, self.wait_by_approach = dict.fromkeys(KINDS, 0.), dict.fromkeys(DIRECTIONS, 0.)
        self.queued_by_class, self.queued_by_approach = Counter(), Counter()
        self.completed_wait, self.completed, self.measured_arrivals, self.initial = 0., 0, 0, 0
        self.completed_by_approach, self.participants_by_approach = Counter(), Counter()
        self.points, self.intervals = [], []

    def permitted(self, key):
        return key[1] == 'left' or (self.phase == 'green' and key[0] == self.active)

    def integrate(self, until):
        # Integrate the previous state, never the post-departure queue. Sampling
        # boundaries include warmup; no pre-window waiting enters the result.
        elapsed = until-self.now if self.now >= self.spec.warmup_seconds-EPS else 0.
        if elapsed > 0:
            for direction, count in self.queued_by_approach.items():
                self.wait_by_approach[direction] += count*elapsed
            for kind, count in self.queued_by_class.items():
                self.by_class[kind] += count*elapsed
        self.now = until

    def measurement(self):
        at = ANCHOR+timedelta(seconds=self.now)
        approaches = {}
        for d in DIRECTIONS:
            controlled = [v for m in ('straight', 'right') for v in self.queues[(d, m)]]
            seen = [v for v in controlled if v.observation_mark < self.spec.detection_fraction]
            # A missed identity cannot contribute an oracle oldest-wait value.
            approaches[d] = dict(observed_at=at, usable=True, controlled_count=len(seen),
                queue_count=len(seen), oldest_wait_seconds=max((self.now-v.at for v in seen), default=0),
                slip_count=len(self.queues[(d, 'left')]), exit_available=True,
                queue_visibility=self.spec.queue_visibility,
                queue_reaches_boundary=self.spec.queue_visibility == 'partial' and len(seen) >= 20)
        return MeasurementBatch(intersection_id=self.config.intersection_id, source='recording',
            source_session=SESSION, sequence=self.cursor, approaches=approaches)

    def transition(self):
        if self.phase == 'green':
            if self.strategy == 'ATCS':
                self.fixed_next = (self.fixed_next+1) % 4
            self.phase, self.deadline = 'yellow', self.now+self.config.fixed_time.yellow_seconds
        elif self.phase == 'yellow':
            self.phase, self.active, self.deadline = 'all_red', None, self.now+self.config.fixed_time.all_red_min_seconds
        else:
            if self.strategy == 'ATCS':
                self.active = self.config.fixed_time.sequence[self.fixed_next]
                duration = self.config.fixed_time.green_seconds[self.active]
            else:
                decision = self.policy.choose(self.measurement(), self.now, ANCHOR+timedelta(seconds=self.now))
                self.active, duration = decision.approach, decision.green_seconds
                self.policy.served(self.active, self.now, duration)
            self.phase, self.deadline = 'green', self.now+duration
            for movement in ('straight', 'right'):
                self.green_ready[(self.active, movement)] = self.now+self.spec.startup_lost_seconds
        for key in self.queues:
            if not self.permitted(key):
                self.releases[key] = None
                self.rows.pop(key, None)
        if self.now >= self.spec.warmup_seconds-EPS:
            self.intervals.append(PhaseInterval(time_seconds=self.now-self.spec.warmup_seconds,
                strategy=self.strategy, phase=self.phase, approach=self.active,
                duration_seconds=max(0, self.deadline-self.now)))

    def start_services(self):
        for key, queue in self.queues.items():
            if self.permitted(key) and queue and self.releases[key] is None:
                row = next(queue_rows(queue, self.spec))
                self.rows[key] = [v.identity for v in row]
                headway = max(self.spec.vehicle_factors[v.kind].discharge_multiplier for v in row)*self.spec.discharge_headway_seconds
                self.releases[key] = max(self.now, self.green_ready[key])+headway

    def point(self):
        queued, total_wait = sum(len(q) for q in self.queues.values()), sum(self.by_class.values())
        participants, f = self.initial+self.measured_arrivals, self.spec.factors
        fuel, co2, cost = 0., 0., 0.
        for kind, seconds in self.by_class.items():
            profile = self.spec.vehicle_factors[kind]
            liters = seconds/3600*f.idle_liters_per_hour*profile.idle_multiplier
            fuel += liters
            co2 += liters*(f.co2_kg_per_liter if profile.fuel == 'gasoline' else f.diesel_co2_kg_per_liter)
            cost += liters*(f.fuel_rupiah_per_liter if profile.fuel == 'gasoline' else f.diesel_fuel_rupiah_per_liter)
        lengths = [sum(max(self.spec.vehicle_factors[v.kind].queue_space_multiplier for v in row)
            *f.queue_spacing_meters for row in queue_rows(queue, self.spec)) for queue in self.queues.values()]
        return ImpactPoint(time_seconds=round(max(0, self.now-self.spec.warmup_seconds), 6), queue_vehicles=queued,
            initial_queue_vehicles=self.initial, queue_meters_estimate=round(sum(lengths), 5),
            maximum_lane_queue_meters=round(max(lengths, default=0), 5),
            average_wait_seconds=round(total_wait/participants, 6) if participants else 0,
            cumulative_wait_vehicle_seconds=round(total_wait, 6), completed_vehicles=self.completed,
            arrivals=self.measured_arrivals, idle_fuel_liters=round(fuel, 6), co2_kg=round(co2, 6),
            fuel_cost_rupiah=round(cost, 4), time_cost_rupiah=round(total_wait/3600*f.time_rupiah_per_vehicle_hour, 4),
            queue_vehicle_seconds_by_class={k:round(v, 6) for k, v in self.by_class.items()},
            completed_average_wait_seconds=round(self.completed_wait/self.completed, 6) if self.completed else 0,
            maximum_observed_wait_seconds=round(max((self.now-max(v.at, self.spec.warmup_seconds)
                for queue in self.queues.values() for v in queue), default=0), 6))

    def run(self):
        warmup, horizon = self.spec.warmup_seconds, self.spec.warmup_seconds+self.spec.duration_seconds
        samples = deque([warmup+t for t in range(0, self.spec.duration_seconds+1, 15)] if self.keep_series else [warmup,horizon])
        if samples[-1] != horizon:
            samples.append(horizon)
        initialized = False
        while True:
            if not initialized and self.now >= warmup-EPS:
                self.initial = sum(len(q) for q in self.queues.values())
                self.participants_by_approach.update(v.direction for q in self.queues.values() for v in q)
                initialized = True
            while self.cursor < len(self.arrivals) and self.arrivals[self.cursor].at <= self.now+EPS:
                vehicle = self.arrivals[self.cursor]
                self.queues[(vehicle.direction, vehicle.movement)].append(vehicle)
                self.queued_by_class[vehicle.kind] += 1
                self.queued_by_approach[vehicle.direction] += 1
                self.cursor += 1
                if initialized:
                    self.measured_arrivals += 1
                    self.participants_by_approach[vehicle.direction] += 1
            if self.now >= self.deadline-EPS:
                self.transition()
            for key, release in self.releases.items():
                if release is not None and release <= self.now+EPS and self.permitted(key):
                    for identity in self.rows.pop(key):
                        vehicle = self.queues[key].popleft()
                        self.queued_by_class[vehicle.kind] -= 1
                        self.queued_by_approach[vehicle.direction] -= 1
                        assert identity == vehicle.identity
                        if initialized:
                            self.completed += 1
                            self.completed_by_approach[vehicle.direction] += 1
                            self.completed_wait += self.now-max(vehicle.at, warmup)
                    self.releases[key] = None
            self.start_services()
            if samples and self.now >= samples[0]-EPS:
                self.points.append(self.point())
                samples.popleft()
            if self.now >= horizon-EPS:
                break
            arrival_at = self.arrivals[self.cursor].at if self.cursor < len(self.arrivals) else float('inf')
            next_event = min(arrival_at, self.deadline, *(v for v in self.releases.values() if v is not None),
                samples[0] if samples else horizon, horizon)
            if next_event <= self.now+EPS:
                raise RuntimeError('Queue event clock did not advance')
            self.integrate(next_event)
        approaches = {d:ApproachImpact(participants=self.participants_by_approach[d],
            completed_vehicles=self.completed_by_approach[d], queue_vehicles=sum(len(self.queues[(d,m)]) for m in MOVEMENTS),
            average_wait_seconds=self.wait_by_approach[d]/self.participants_by_approach[d] if self.participants_by_approach[d] else 0)
            for d in DIRECTIONS}
        return self.points, approaches
