/* Generated from contracts/adaptive.py. Do not edit manually. */

export type Enabled = boolean;
export type Source = "synthetic";
export type Fault = "none" | "frozen_data" | "invalid_data" | "sender_stopped";
export type Status = "disabled" | "ready" | "active" | "unavailable";
export type Message = string;
export type MinimumGreen = number;
export type MaximumGreen = number;
export type QueueWeight = number;
export type WaitWeight = number;
export type AgeWeight = number;
export type ServiceAgeTarget = number;
export type SecondsPerQueuedVehicle = number;
export type DataTimeout = number;
export type IntersectionId = string;
export type Source1 = "synthetic" | "recording" | "cctv";
export type SourceSession = string;
export type Sequence = number;
export type ObservedAt = string;
export type Usable = boolean;
export type ControlledCount = number;
export type QueueCount = number;
export type OldestWaitSeconds = number;
export type SlipCount = number;
export type ExitAvailable = boolean;
export type DecidedAt = string;
export type MeasurementSequence = number;
export type Approach = ("U" | "T" | "S" | "B") | null;
export type GreenSeconds = number | null;
export type Reason = string;
export type RequestId = string | null;
export type Outcome = "preview" | "accepted" | "applied" | "rejected" | "cancelled";
export type Decisions = AdaptiveDecision[];

export interface AdaptiveStatus {
  enabled: Enabled;
  source: Source;
  fault: Fault;
  status: Status;
  message: Message;
  policy: AdaptivePolicyConfig;
  measurements: MeasurementBatch | null;
  decisions: Decisions;
}
export interface AdaptivePolicyConfig {
  minimum_green: MinimumGreen;
  maximum_green: MaximumGreen;
  queue_weight: QueueWeight;
  wait_weight: WaitWeight;
  age_weight: AgeWeight;
  service_age_target: ServiceAgeTarget;
  seconds_per_queued_vehicle: SecondsPerQueuedVehicle;
  data_timeout: DataTimeout;
}
export interface MeasurementBatch {
  intersection_id: IntersectionId;
  source: Source1;
  source_session: SourceSession;
  sequence: Sequence;
  approaches: Approaches;
}
export interface Approaches {
  [k: string]: ApproachMeasurement;
}
export interface ApproachMeasurement {
  observed_at: ObservedAt;
  usable: Usable;
  controlled_count: ControlledCount;
  queue_count: QueueCount;
  oldest_wait_seconds: OldestWaitSeconds;
  slip_count: SlipCount;
  exit_available: ExitAvailable;
}
export interface AdaptiveDecision {
  decided_at: DecidedAt;
  measurement_sequence: MeasurementSequence;
  approach: Approach;
  green_seconds: GreenSeconds;
  reason: Reason;
  scores: Scores;
  inputs: Inputs;
  request_id: RequestId;
  outcome: Outcome;
}
export interface Scores {
  [k: string]: number;
}
export interface Inputs {
  [k: string]: ApproachMeasurement;
}
