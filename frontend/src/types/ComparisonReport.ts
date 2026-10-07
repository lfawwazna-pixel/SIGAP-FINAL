/* Generated from contracts/analytics.py. Do not edit manually. */

export type Id = string;
export type IntersectionId = string;
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

export interface ComparisonReport {
  id: Id;
  intersection_id: IntersectionId;
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
