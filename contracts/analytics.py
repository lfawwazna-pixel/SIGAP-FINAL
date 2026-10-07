"""Regional road observations and paired, explicitly simulated impact results."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, model_validator
from contracts.models import Contract, Direction
from contracts.adaptive import AdaptivePolicyConfig

Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]

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
    idle_liters_per_hour: float = Field(default=.8, ge=0, le=10, allow_inf_nan=False)
    co2_kg_per_liter: float = Field(default=2.35, ge=0, le=5, allow_inf_nan=False)
    fuel_rupiah_per_liter: float = Field(default=10000, ge=0, le=100000, allow_inf_nan=False)
    time_rupiah_per_vehicle_hour: float = Field(default=20000, ge=0, le=1000000, allow_inf_nan=False)
    queue_spacing_meters: float = Field(default=6.5, ge=1, le=20, allow_inf_nan=False)

class ComparisonInput(Contract):
    duration_seconds: int = Field(default=900, ge=300, le=1800, strict=True)
    seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    demand_per_minute: dict[Direction, Annotated[int, Field(ge=0, le=60, strict=True)]] = Field(default_factory=lambda:dict(U=18,T=32,S=14,B=24))
    # This is a simulation assumption, never an invented real detection count.
    detection_fraction: float = Field(default=.65, ge=.1, le=1, allow_inf_nan=False)
    discharge_headway_seconds: float = Field(default=2.2, ge=1, le=5, allow_inf_nan=False)
    factors: ImpactFactors = Field(default_factory=ImpactFactors)

    @model_validator(mode='after')
    def coverage(self):
        if set(self.demand_per_minute) != set('UTSB'):
            raise ValueError('Four explicit demands required')
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
            if a.queue_vehicles + a.completed_vehicles != a.arrivals or b.queue_vehicles + b.completed_vehicles != b.arrivals:
                raise ValueError('Vehicle conservation required')
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
