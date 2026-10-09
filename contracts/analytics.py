"""Regional road observations and paired, explicitly simulated impact results."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, model_validator
from contracts.models import Contract, Direction
from contracts.adaptive import AdaptivePolicyConfig

Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
VehicleKind = Literal['motorcycle', 'car', 'bus', 'truck']
Movement = Literal['left', 'straight', 'right']


class VehicleFactors(Contract):
    queue_space_multiplier: float = Field(ge=.1, le=5, allow_inf_nan=False)
    discharge_multiplier: float = Field(ge=.2, le=5, allow_inf_nan=False)
    idle_multiplier: float = Field(ge=0, le=10, allow_inf_nan=False)
    fuel: Literal['gasoline', 'diesel']
    parallel_slots: int = Field(default=1, ge=1, le=3, strict=True)


def default_vehicle_factors():
    # Space/discharge/motorcycle idle are scenario assumptions. Car idle uses
    # AFDC LD gasoline .23 US gal/h; bus/truck use its HD diesel .8 US gal/h.
    return dict(motorcycle=VehicleFactors(queue_space_multiplier=3/6.5, discharge_multiplier=1,
                idle_multiplier=.2/(.23*3.785411784), fuel='gasoline', parallel_slots=3),
        car=VehicleFactors(queue_space_multiplier=1, discharge_multiplier=1, idle_multiplier=1, fuel='gasoline'),
        bus=VehicleFactors(queue_space_multiplier=2, discharge_multiplier=2, idle_multiplier=.8/.23, fuel='diesel'),
        truck=VehicleFactors(queue_space_multiplier=2, discharge_multiplier=2, idle_multiplier=.8/.23, fuel='diesel'))


class ZoneApproachDemand(Contract):
    direction: Direction
    state: Literal['ready', 'collecting', 'unavailable']
    message: str
    source: Literal['recording', 'live', 'none']
    observed_seconds: Nonnegative
    entries: int = Field(ge=0)
    demand_per_minute: Nonnegative
    by_class: dict[VehicleKind, Annotated[int, Field(ge=0)]]
    by_movement: dict[Movement, Annotated[int, Field(ge=0)]]
    queue_visibility: Literal['full', 'partial']
    loop_count: int = Field(ge=0)


class ZoneDemand(Contract):
    ready: bool
    message: str
    generated_at: AwareDatetime
    approaches: list[ZoneApproachDemand]
    fingerprint: str | None = None


class DemandProvenance(Contract):
    source: Literal['manual_scenario', 'zone_observation']
    captured_at: AwareDatetime | None = None
    fingerprint: str | None = None
    approaches: list[ZoneApproachDemand] = Field(default_factory=list)


class Reference(Contract):
    title: str
    url: str
    use: str


class TrafficComposition(Contract):
    class_mix: dict[VehicleKind, Nonnegative]
    turn_mix: dict[Movement, Nonnegative]

    @model_validator(mode='after')
    def complete(self):
        if set(self.class_mix) != {'motorcycle', 'car', 'bus', 'truck'} or sum(self.class_mix.values()) <= 0:
            raise ValueError('Four class weights required')
        if set(self.turn_mix) != {'left', 'straight', 'right'} or sum(self.turn_mix.values()) <= 0:
            raise ValueError('Three movement weights required')
        return self

class RoadPoint(Contract):
    label: str
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)

class TrafficSample(Contract):
    observed_at: AwareDatetime
    direction: Direction
    current_speed_kmh: Nonnegative
    free_flow_speed_kmh: float = Field(gt=0, allow_inf_nan=False)
    current_travel_seconds: Nonnegative
    free_flow_travel_seconds: Nonnegative
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    road_closed: bool
    congestion_percent: float = Field(ge=0, le=100, allow_inf_nan=False)
    delay_seconds: Nonnegative
    # Public coordinates of the road returned by the provider, not user location.
    segment_latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    segment_longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    point_distance_m: Nonnegative

class ForecastPoint(Contract):
    at: AwareDatetime
    congestion_percent: float = Field(ge=0, le=100)
    lower: float = Field(ge=0, le=100)
    upper: float = Field(ge=0, le=100)

class TrafficForecast(Contract):
    state: Literal['ready','collecting','stale','unavailable']
    method: Literal['ridge_ar2','persistence','none']
    training_samples: int = Field(ge=0)
    validation_mae: Nonnegative | None
    baseline_mae: Nonnegative | None
    message: str
    points: list[ForecastPoint]

class RoadAnalytics(Contract):
    direction: Direction
    point: RoadPoint
    state: Literal['ready','stale','no_data','low_confidence','closed','error']
    message: str
    latest: TrafficSample | None
    history: list[TrafficSample]
    forecast: TrafficForecast

class ImpactFactors(Contract):
    idle_liters_per_hour: float = Field(default=.23*3.785411784, ge=0, le=10, allow_inf_nan=False)
    co2_kg_per_liter: float = Field(default=2.35, ge=0, le=5, allow_inf_nan=False)
    fuel_rupiah_per_liter: float = Field(default=10000, ge=0, le=100000, allow_inf_nan=False)
    time_rupiah_per_vehicle_hour: float = Field(default=20000, ge=0, le=1000000, allow_inf_nan=False)
    queue_spacing_meters: float = Field(default=6.5, ge=1, le=20, allow_inf_nan=False)
    diesel_co2_kg_per_liter: float = Field(default=2.69, ge=0, le=5, allow_inf_nan=False)
    diesel_fuel_rupiah_per_liter: float = Field(default=10000, ge=0, le=100000, allow_inf_nan=False)

class ComparisonInput(Contract):
    duration_seconds: int = Field(default=900, ge=300, le=1800, strict=True)
    seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    demand_per_minute: dict[Direction, Annotated[float, Field(ge=0, le=180, allow_inf_nan=False)]] = Field(default_factory=lambda:dict(U=18,T=32,S=14,B=24))
    # This is a simulation assumption, never an invented real detection count.
    detection_fraction: float = Field(default=1, ge=.1, le=1, allow_inf_nan=False)
    discharge_headway_seconds: float = Field(default=2.2, ge=1, le=5, allow_inf_nan=False)
    factors: ImpactFactors = Field(default_factory=ImpactFactors)
    warmup_seconds: int = Field(default=300, ge=0, le=900, strict=True)
    replications: int = Field(default=10, ge=5, le=30, strict=True)
    startup_lost_seconds: float = Field(default=2, ge=0, le=5, allow_inf_nan=False)
    demand_source: Literal['manual_scenario', 'zone_observation'] = 'manual_scenario'
    observation_fingerprint: str | None = None
    queue_visibility: Literal['full', 'partial'] = 'partial'
    class_mix: dict[VehicleKind, Nonnegative] = Field(default_factory=lambda:dict(motorcycle=45, car=45, bus=5, truck=5))
    turn_mix: dict[Movement, Nonnegative] = Field(default_factory=lambda:dict(left=25, straight=55, right=20))
    vehicle_factors: dict[VehicleKind, VehicleFactors] = Field(default_factory=default_vehicle_factors)
    approach_composition: dict[Direction, TrafficComposition] = Field(default_factory=dict)

    @model_validator(mode='after')
    def coverage(self):
        if set(self.demand_per_minute) != set('UTSB'):
            raise ValueError('Four explicit demands required')
        if set(self.class_mix) != {'motorcycle', 'car', 'bus', 'truck'} or sum(self.class_mix.values()) <= 0:
            raise ValueError('Four nonempty ordinary class weights required')
        if set(self.turn_mix) != {'left', 'straight', 'right'} or sum(self.turn_mix.values()) <= 0:
            raise ValueError('Three nonempty movement weights required')
        if set(self.vehicle_factors) != set(self.class_mix):
            raise ValueError('Four class factors required')
        if any(v.parallel_slots != 1 for k, v in self.vehicle_factors.items() if k != 'motorcycle'):
            raise ValueError('Only motorcycles can share lane width')
        if self.demand_source == 'zone_observation' and not self.observation_fingerprint:
            raise ValueError('An observed scenario must reference a captured profile')
        if self.approach_composition and set(self.approach_composition) != set('UTSB'):
            raise ValueError('Composition must cover all four approaches')
        return self

class ImpactPoint(Contract):
    time_seconds: Nonnegative
    queue_vehicles: int = Field(ge=0)
    queue_meters_estimate: Nonnegative
    average_wait_seconds: Nonnegative
    cumulative_wait_vehicle_seconds: Nonnegative
    completed_vehicles: int = Field(ge=0)
    arrivals: int = Field(ge=0)
    idle_fuel_liters: Nonnegative
    co2_kg: Nonnegative
    fuel_cost_rupiah: Nonnegative
    time_cost_rupiah: Nonnegative
    initial_queue_vehicles: int = Field(default=0, ge=0)
    queue_vehicle_seconds_by_class: dict[VehicleKind, Nonnegative] = Field(default_factory=dict)
    maximum_lane_queue_meters: Nonnegative = 0
    completed_average_wait_seconds: Nonnegative = 0
    maximum_observed_wait_seconds: Nonnegative = 0


class ApproachImpact(Contract):
    participants: int = Field(ge=0)
    completed_vehicles: int = Field(ge=0)
    queue_vehicles: int = Field(ge=0)
    average_wait_seconds: Nonnegative

    @model_validator(mode='after')
    def conserved(self):
        if self.participants != self.completed_vehicles+self.queue_vehicles:
            raise ValueError('Per-approach vehicle conservation required')
        return self


class PairedRun(Contract):
    seed: int
    arrival_schedule_sha256: str
    atcs: ImpactPoint
    sigap: ImpactPoint
    atcs_by_approach: dict[Direction, ApproachImpact]
    sigap_by_approach: dict[Direction, ApproachImpact]


MetricKey = Literal['average_wait_seconds', 'queue_vehicles', 'queue_meters_estimate', 'maximum_lane_queue_meters',
    'co2_kg', 'idle_fuel_liters', 'fuel_cost_rupiah', 'time_cost_rupiah', 'completed_vehicles', 'cost']


class PairedMetric(Contract):
    key: MetricKey
    atcs_mean: Nonnegative
    sigap_mean: Nonnegative
    # Positive means a benefit; throughput uses SIGAP - ATCS, other metrics ATCS - SIGAP.
    improvement_mean: float = Field(allow_inf_nan=False)
    improvement_percent: float | None = Field(default=None, allow_inf_nan=False)
    lower_95: float = Field(allow_inf_nan=False)
    upper_95: float = Field(allow_inf_nan=False)
    result: Literal['better', 'worse', 'inconclusive', 'equal']


class PhaseInterval(Contract):
    time_seconds: Nonnegative
    strategy: Literal['ATCS', 'SIGAP']
    phase: Literal['green', 'yellow', 'all_red']
    approach: Direction | None
    duration_seconds: Nonnegative

class ComparisonReport(Contract):
    id: str
    intersection_id: str
    created_at: AwareDatetime
    source: Literal['paired_queue_simulation'] = 'paired_queue_simulation'
    title: str
    assumptions: list[str]
    input: ComparisonInput
    arrival_schedule_sha256: str
    total_scheduled_arrivals: int = Field(ge=0)
    baseline_green_seconds: dict[Direction, Nonnegative]
    yellow_seconds: Nonnegative
    all_red_seconds: Nonnegative
    adaptive_policy: AdaptivePolicyConfig
    atcs: list[ImpactPoint] = Field(min_length=2)
    sigap: list[ImpactPoint] = Field(min_length=2)
    emergency_status: Literal['not_evaluated'] = 'not_evaluated'
    method_version: Literal['queue-v2'] | None = None
    runs: list[PairedRun] = Field(default_factory=list)
    metrics: list[PairedMetric] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    demand_provenance: DemandProvenance | None = None
    phase_intervals: list[PhaseInterval] = Field(default_factory=list)
    baseline_basis: str = ''
    baseline_field_verified: bool = False

    @model_validator(mode='after')
    def paired(self):
        if len(self.atcs) != len(self.sigap):
            raise ValueError('Paired series must align')
        if self.atcs[0].time_seconds != 0 or self.atcs[-1].time_seconds != self.input.duration_seconds or self.atcs[-1].arrivals != self.total_scheduled_arrivals:
            raise ValueError('Experiment window and scheduled arrivals must match')
        for i, (a, b) in enumerate(zip(self.atcs, self.sigap)):
            if a.time_seconds != b.time_seconds or a.arrivals != b.arrivals:
                raise ValueError('Paired samples must share arrivals and clock')
            if i and (a.time_seconds <= self.atcs[i-1].time_seconds or a.arrivals < self.atcs[i-1].arrivals):
                raise ValueError('Time and arrivals must advance consistently')
            if a.queue_vehicles + a.completed_vehicles != a.arrivals+a.initial_queue_vehicles or b.queue_vehicles + b.completed_vehicles != b.arrivals+b.initial_queue_vehicles:
                raise ValueError('Vehicle conservation required')
        if self.method_version:
            if len(self.runs) != self.input.replications or not self.metrics or not self.demand_provenance:
                raise ValueError('Repeated experiment evidence required')
            if self.runs[0].arrival_schedule_sha256 != self.arrival_schedule_sha256 or self.runs[0].atcs != self.atcs[-1] or self.runs[0].sigap != self.sigap[-1]:
                raise ValueError('Graph must represent the first paired run')
            if len({r.seed for r in self.runs}) != len(self.runs):
                raise ValueError('Distinct replicated seeds required')
            expected_metrics = {'average_wait_seconds','queue_vehicles','queue_meters_estimate','maximum_lane_queue_meters',
                'co2_kg','idle_fuel_liters','fuel_cost_rupiah','time_cost_rupiah','completed_vehicles','cost'}
            if len(self.metrics) != len(expected_metrics) or {m.key for m in self.metrics} != expected_metrics:
                raise ValueError('Complete repeated metric summaries required')
            if any(not m.lower_95-1e-8 <= m.improvement_mean <= m.upper_95+1e-8 for m in self.metrics):
                raise ValueError('Paired interval must contain the mean')
            for run in self.runs:
                if run.atcs.arrivals != run.sigap.arrivals:
                    raise ValueError('Each replication must use identical arrivals')
                for point, approaches in ((run.atcs,run.atcs_by_approach),(run.sigap,run.sigap_by_approach)):
                    if point.queue_vehicles+point.completed_vehicles != point.arrivals+point.initial_queue_vehicles:
                        raise ValueError('Replication vehicle conservation required')
                    if set(approaches) != set('UTSB') or sum(a.participants for a in approaches.values()) != point.arrivals+point.initial_queue_vehicles:
                        raise ValueError('Complete approach population required')
                    if sum(a.completed_vehicles for a in approaches.values()) != point.completed_vehicles or sum(a.queue_vehicles for a in approaches.values()) != point.queue_vehicles:
                        raise ValueError('Per-approach totals must match replication')
            if self.atcs[0].initial_queue_vehicles != self.atcs[-1].initial_queue_vehicles or self.sigap[0].initial_queue_vehicles != self.sigap[-1].initial_queue_vehicles:
                raise ValueError('Initial queues must remain consistent')
        return self

class AnalyticsView(Contract):
    intersection_id: str
    generated_at: AwareDatetime
    provider: Literal['TomTom Traffic Flow'] = 'TomTom Traffic Flow'
    provider_status: Literal['connected','partial','not_configured','unavailable']
    provider_message: str
    poll_seconds: int
    attribution: str
    history_since: AwareDatetime | None
    roads: list[RoadAnalytics]
    latest_comparison: ComparisonReport | None
    zone_demand: ZoneDemand | None = None
