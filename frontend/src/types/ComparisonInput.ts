/* Generated from contracts/analytics.py. Do not edit manually. */

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

export interface ComparisonInput {
  duration_seconds?: DurationSeconds;
  seed?: Seed;
  demand_per_minute?: DemandPerMinute;
  detection_fraction?: DetectionFraction;
  discharge_headway_seconds?: DischargeHeadwaySeconds;
  factors?: ImpactFactors;
  warmup_seconds?: WarmupSeconds;
  replications?: Replications;
  startup_lost_seconds?: StartupLostSeconds;
  demand_source?: DemandSource;
  observation_fingerprint?: ObservationFingerprint;
  queue_visibility?: QueueVisibility;
  class_mix?: ClassMix;
  turn_mix?: TurnMix;
  vehicle_factors?: VehicleFactors;
  approach_composition?: ApproachComposition;
}
export interface DemandPerMinute {
  [k: string]: number;
}
export interface ImpactFactors {
  idle_liters_per_hour?: IdleLitersPerHour;
  co2_kg_per_liter?: Co2KgPerLiter;
  fuel_rupiah_per_liter?: FuelRupiahPerLiter;
  time_rupiah_per_vehicle_hour?: TimeRupiahPerVehicleHour;
  queue_spacing_meters?: QueueSpacingMeters;
  diesel_co2_kg_per_liter?: DieselCo2KgPerLiter;
  diesel_fuel_rupiah_per_liter?: DieselFuelRupiahPerLiter;
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
  parallel_slots?: ParallelSlots;
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
