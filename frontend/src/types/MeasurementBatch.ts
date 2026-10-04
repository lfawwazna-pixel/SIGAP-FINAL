/* Generated from contracts/adaptive.py. Do not edit manually. */

export type IntersectionId = string;
export type Source = "synthetic" | "recording" | "cctv";
export type SourceSession = string;
export type Sequence = number;
export type ObservedAt = string;
export type Usable = boolean;
export type ControlledCount = number;
export type QueueCount = number;
export type OldestWaitSeconds = number;
export type SlipCount = number;
export type ExitAvailable = boolean;

export interface MeasurementBatch {
  intersection_id: IntersectionId;
  source: Source;
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
