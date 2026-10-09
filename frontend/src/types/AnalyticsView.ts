/* Generated from contracts/analytics.py. Do not edit manually. */

export type IntersectionId = string;
export type GeneratedAt = string;
export type Provider = "TomTom Traffic Flow";
export type ProviderStatus = "connected" | "partial" | "not_configured" | "unavailable";
export type ProviderMessage = string;
export type PollSeconds = number;
export type Attribution = string;
export type HistorySince = string | null;
export type Direction = "U" | "T" | "S" | "B";
export type Label = string;
export type Latitude = number;
export type Longitude = number;
export type State = "ready" | "stale" | "no_data" | "low_confidence" | "closed" | "error";
export type Message = string;
export type ObservedAt = string;
export type Direction1 = "U" | "T" | "S" | "B";
export type CurrentSpeedKmh = number;
export type FreeFlowSpeedKmh = number;
export type CurrentTravelSeconds = number;
export type FreeFlowTravelSeconds = number;
export type Confidence = number;
export type RoadClosed = boolean;
export type CongestionPercent = number;
export type DelaySeconds = number;
export type SegmentLatitude = number;
export type SegmentLongitude = number;
export type PointDistanceM = number;
export type History = TrafficSample[];
export type State1 = "ready" | "collecting" | "stale" | "unavailable";
export type Method = "ridge_ar2" | "persistence" | "none";
export type TrainingSamples = number;
export type ValidationMae = number | null;
export type BaselineMae = number | null;
export type Message1 = string;
export type At = string;
export type CongestionPercent1 = number;
export type Lower = number;
export type Upper = number;
export type Points = ForecastPoint[];
export type Roads = RoadAnalytics[];
export type Id = string;
export type IntersectionId1 = string;
export type CreatedAt = string;
export type Source = "paired_queue_simulation";
export type Title = string;
export type Assumptions = string[];
export type DurationSeconds = number;
export type Seed = number;
export type DetectionFraction = number;
export type DischargeHeadwaySeconds = number;
export type IdleLitersPerHour = number;
export type Co2KgPerLiter = number;
export type FuelRupiahPerLiter = number;
export type TimeRupiahPerVehicleHour = number;
export type QueueSpacingMeters = number;
export type DieselCo2KgPerLiter = number;
export type DieselFuelRupiahPerLiter = number;
export type WarmupSeconds = number;
export type Replications = number;
export type StartupLostSeconds = number;
export type DemandSource = "manual_scenario" | "zone_observation";
export type ObservationFingerprint = string | null;
export type QueueVisibility = "full" | "partial";
export type QueueSpaceMultiplier = number;
export type DischargeMultiplier = number;
export type IdleMultiplier = number;
export type Fuel = "gasoline" | "diesel";
export type ParallelSlots = number;
export type ArrivalScheduleSha256 = string;
export type TotalScheduledArrivals = number;
export type YellowSeconds = number;
export type AllRedSeconds = number;
export type VideoBaselineFloorRatio = number;
export type VideoMaximumDropRatio = number;
export type MinimumGreen = number;
export type MaximumGreen = number;
export type QueueWeight = number;
export type WaitWeight = number;
export type AgeWeight = number;
export type ServiceAgeTarget = number;
export type SecondsPerQueuedVehicle = number;
export type DataTimeout = number;
/**
 * @minItems 2
 */
export type Atcs = [ImpactPoint, ImpactPoint, ...ImpactPoint[]];
export type TimeSeconds = number;
export type QueueVehicles = number;
export type QueueMetersEstimate = number;
export type AverageWaitSeconds = number;
export type CumulativeWaitVehicleSeconds = number;
export type CompletedVehicles = number;
export type Arrivals = number;
export type IdleFuelLiters = number;
export type Co2Kg = number;
export type FuelCostRupiah = number;
export type TimeCostRupiah = number;
export type InitialQueueVehicles = number;
export type MaximumLaneQueueMeters = number;
export type CompletedAverageWaitSeconds = number;
export type MaximumObservedWaitSeconds = number;
/**
 * @minItems 2
 */
export type Sigap = [ImpactPoint, ImpactPoint, ...ImpactPoint[]];
export type EmergencyStatus = "not_evaluated";
export type MethodVersion = "queue-v2" | null;
export type Seed1 = number;
export type ArrivalScheduleSha2561 = string;
export type Participants = number;
export type CompletedVehicles1 = number;
export type QueueVehicles1 = number;
export type AverageWaitSeconds1 = number;
export type Runs = PairedRun[];
export type Key =
  | "average_wait_seconds"
  | "queue_vehicles"
  | "queue_meters_estimate"
  | "maximum_lane_queue_meters"
  | "co2_kg"
  | "idle_fuel_liters"
  | "fuel_cost_rupiah"
  | "time_cost_rupiah"
  | "completed_vehicles"
  | "cost";
export type AtcsMean = number;
export type SigapMean = number;
export type ImprovementMean = number;
export type ImprovementPercent = number | null;
export type Lower95 = number;
export type Upper95 = number;
export type Result = "better" | "worse" | "inconclusive" | "equal";
export type Metrics = PairedMetric[];
export type Title1 = string;
export type Url = string;
export type Use = string;
export type References = Reference[];
export type Source1 = "manual_scenario" | "zone_observation";
export type CapturedAt = string | null;
export type Fingerprint = string | null;
export type Direction2 = "U" | "T" | "S" | "B";
export type State2 = "ready" | "collecting" | "unavailable";
export type Message2 = string;
export type Source2 = "recording" | "live" | "none";
export type ObservedSeconds = number;
export type Entries = number;
export type DemandPerMinute1 = number;
export type QueueVisibility1 = "full" | "partial";
export type LoopCount = number;
export type Approaches = ZoneApproachDemand[];
export type TimeSeconds1 = number;
export type Strategy = "ATCS" | "SIGAP";
export type Phase = "green" | "yellow" | "all_red";
export type Approach = ("U" | "T" | "S" | "B") | null;
export type DurationSeconds1 = number;
export type PhaseIntervals = PhaseInterval[];
export type BaselineBasis = string;
export type BaselineFieldVerified = boolean;
export type Ready = boolean;
export type Message3 = string;
export type GeneratedAt1 = string;
export type Approaches1 = ZoneApproachDemand[];
export type Fingerprint1 = string | null;

export interface AnalyticsView {
  intersection_id: IntersectionId;
  generated_at: GeneratedAt;
  provider: Provider;
  provider_status: ProviderStatus;
  provider_message: ProviderMessage;
  poll_seconds: PollSeconds;
  attribution: Attribution;
  history_since: HistorySince;
  roads: Roads;
  latest_comparison: ComparisonReport | null;
  zone_demand: ZoneDemand | null;
}
export interface RoadAnalytics {
  direction: Direction;
  point: RoadPoint;
  state: State;
  message: Message;
  latest: TrafficSample | null;
  history: History;
  forecast: TrafficForecast;
}
export interface RoadPoint {
  label: Label;
  latitude: Latitude;
  longitude: Longitude;
}
export interface TrafficSample {
  observed_at: ObservedAt;
  direction: Direction1;
  current_speed_kmh: CurrentSpeedKmh;
  free_flow_speed_kmh: FreeFlowSpeedKmh;
  current_travel_seconds: CurrentTravelSeconds;
  free_flow_travel_seconds: FreeFlowTravelSeconds;
  confidence: Confidence;
  road_closed: RoadClosed;
  congestion_percent: CongestionPercent;
  delay_seconds: DelaySeconds;
  segment_latitude: SegmentLatitude;
  segment_longitude: SegmentLongitude;
  point_distance_m: PointDistanceM;
}
export interface TrafficForecast {
  state: State1;
  method: Method;
  training_samples: TrainingSamples;
  validation_mae: ValidationMae;
  baseline_mae: BaselineMae;
  message: Message1;
  points: Points;
}
export interface ForecastPoint {
  at: At;
  congestion_percent: CongestionPercent1;
  lower: Lower;
  upper: Upper;
}
export interface ComparisonReport {
  id: Id;
  intersection_id: IntersectionId1;
  created_at: CreatedAt;
  source: Source;
  title: Title;
  assumptions: Assumptions;
  input: ComparisonInput;
  arrival_schedule_sha256: ArrivalScheduleSha256;
  total_scheduled_arrivals: TotalScheduledArrivals;
  baseline_green_seconds: BaselineGreenSeconds;
  yellow_seconds: YellowSeconds;
  all_red_seconds: AllRedSeconds;
  adaptive_policy: AdaptivePolicyConfig;
  atcs: Atcs;
  sigap: Sigap;
  emergency_status: EmergencyStatus;
  method_version: MethodVersion;
  runs: Runs;
  metrics: Metrics;
  references: References;
  demand_provenance: DemandProvenance | null;
  phase_intervals: PhaseIntervals;
  baseline_basis: BaselineBasis;
  baseline_field_verified: BaselineFieldVerified;
}
export interface ComparisonInput {
  duration_seconds: DurationSeconds;
  seed: Seed;
  demand_per_minute: DemandPerMinute;
  detection_fraction: DetectionFraction;
  discharge_headway_seconds: DischargeHeadwaySeconds;
  factors: ImpactFactors;
  warmup_seconds: WarmupSeconds;
  replications: Replications;
  startup_lost_seconds: StartupLostSeconds;
  demand_source: DemandSource;
  observation_fingerprint: ObservationFingerprint;
  queue_visibility: QueueVisibility;
  class_mix: ClassMix;
  turn_mix: TurnMix;
  vehicle_factors: VehicleFactors;
  approach_composition: ApproachComposition;
}
export interface DemandPerMinute {
  [k: string]: number;
}
export interface ImpactFactors {
  idle_liters_per_hour: IdleLitersPerHour;
  co2_kg_per_liter: Co2KgPerLiter;
  fuel_rupiah_per_liter: FuelRupiahPerLiter;
  time_rupiah_per_vehicle_hour: TimeRupiahPerVehicleHour;
  queue_spacing_meters: QueueSpacingMeters;
  diesel_co2_kg_per_liter: DieselCo2KgPerLiter;
  diesel_fuel_rupiah_per_liter: DieselFuelRupiahPerLiter;
}
export interface ClassMix {
  [k: string]: number;
}
export interface TurnMix {
  [k: string]: number;
}
export interface VehicleFactors {
  [k: string]: VehicleFactors1;
}
export interface VehicleFactors1 {
  queue_space_multiplier: QueueSpaceMultiplier;
  discharge_multiplier: DischargeMultiplier;
  idle_multiplier: IdleMultiplier;
  fuel: Fuel;
  parallel_slots: ParallelSlots;
}
export interface ApproachComposition {
  [k: string]: TrafficComposition;
}
export interface TrafficComposition {
  class_mix: ClassMix1;
  turn_mix: TurnMix1;
}
export interface ClassMix1 {
  [k: string]: number;
}
export interface TurnMix1 {
  [k: string]: number;
}
export interface BaselineGreenSeconds {
  [k: string]: number;
}
export interface AdaptivePolicyConfig {
  video_baseline_floor_ratio: VideoBaselineFloorRatio;
  video_maximum_drop_ratio: VideoMaximumDropRatio;
  minimum_green: MinimumGreen;
  maximum_green: MaximumGreen;
  queue_weight: QueueWeight;
  wait_weight: WaitWeight;
  age_weight: AgeWeight;
  service_age_target: ServiceAgeTarget;
  seconds_per_queued_vehicle: SecondsPerQueuedVehicle;
  data_timeout: DataTimeout;
}
export interface ImpactPoint {
  time_seconds: TimeSeconds;
  queue_vehicles: QueueVehicles;
  queue_meters_estimate: QueueMetersEstimate;
  average_wait_seconds: AverageWaitSeconds;
  cumulative_wait_vehicle_seconds: CumulativeWaitVehicleSeconds;
  completed_vehicles: CompletedVehicles;
  arrivals: Arrivals;
  idle_fuel_liters: IdleFuelLiters;
  co2_kg: Co2Kg;
  fuel_cost_rupiah: FuelCostRupiah;
  time_cost_rupiah: TimeCostRupiah;
  initial_queue_vehicles: InitialQueueVehicles;
  queue_vehicle_seconds_by_class: QueueVehicleSecondsByClass;
  maximum_lane_queue_meters: MaximumLaneQueueMeters;
  completed_average_wait_seconds: CompletedAverageWaitSeconds;
  maximum_observed_wait_seconds: MaximumObservedWaitSeconds;
}
export interface QueueVehicleSecondsByClass {
  [k: string]: number;
}
export interface PairedRun {
  seed: Seed1;
  arrival_schedule_sha256: ArrivalScheduleSha2561;
  atcs: ImpactPoint;
  sigap: ImpactPoint;
  atcs_by_approach: AtcsByApproach;
  sigap_by_approach: SigapByApproach;
}
export interface AtcsByApproach {
  [k: string]: ApproachImpact;
}
export interface ApproachImpact {
  participants: Participants;
  completed_vehicles: CompletedVehicles1;
  queue_vehicles: QueueVehicles1;
  average_wait_seconds: AverageWaitSeconds1;
}
export interface SigapByApproach {
  [k: string]: ApproachImpact;
}
export interface PairedMetric {
  key: Key;
  atcs_mean: AtcsMean;
  sigap_mean: SigapMean;
  improvement_mean: ImprovementMean;
  improvement_percent: ImprovementPercent;
  lower_95: Lower95;
  upper_95: Upper95;
  result: Result;
}
export interface Reference {
  title: Title1;
  url: Url;
  use: Use;
}
export interface DemandProvenance {
  source: Source1;
  captured_at: CapturedAt;
  fingerprint: Fingerprint;
  approaches: Approaches;
}
export interface ZoneApproachDemand {
  direction: Direction2;
  state: State2;
  message: Message2;
  source: Source2;
  observed_seconds: ObservedSeconds;
  entries: Entries;
  demand_per_minute: DemandPerMinute1;
  by_class: ByClass;
  by_movement: ByMovement;
  queue_visibility: QueueVisibility1;
  loop_count: LoopCount;
}
export interface ByClass {
  [k: string]: number;
}
export interface ByMovement {
  [k: string]: number;
}
export interface PhaseInterval {
  time_seconds: TimeSeconds1;
  strategy: Strategy;
  phase: Phase;
  approach: Approach;
  duration_seconds: DurationSeconds1;
}
export interface ZoneDemand {
  ready: Ready;
  message: Message3;
  generated_at: GeneratedAt1;
  approaches: Approaches1;
  fingerprint: Fingerprint1;
}
