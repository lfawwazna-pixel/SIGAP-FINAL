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

export interface ComparisonInput {
  duration_seconds?: DurationSeconds;
  seed?: Seed;
  demand_per_minute?: DemandPerMinute;
  detection_fraction?: DetectionFraction;
  discharge_headway_seconds?: DischargeHeadwaySeconds;
  factors?: ImpactFactors;
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
}
