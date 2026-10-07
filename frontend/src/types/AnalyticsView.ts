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
/**
 * @minItems 2
 */
export type Sigap = [ImpactPoint, ImpactPoint, ...ImpactPoint[]];
export type EmergencyStatus = "not_evaluated";

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
}
export interface ComparisonInput {
  duration_seconds: DurationSeconds;
  seed: Seed;
  demand_per_minute: DemandPerMinute;
  detection_fraction: DetectionFraction;
  discharge_headway_seconds: DischargeHeadwaySeconds;
  factors: ImpactFactors;
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
}
