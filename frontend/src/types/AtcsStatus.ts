/* Generated from contracts/models.py. Do not edit manually. */

export type SchemaVersion = "2.0";
export type IntersectionId = string;
export type OperatingContext = "simulation";
export type Availability = "not_implemented" | "available" | "unavailable";
export type RunId = string | null;
export type EngineState = "not_started" | "running" | "faulted" | "stopped" | "stalled";
export type Controller = ("ATCS" | "SIGAP") | null;
export type Mode = ("fixed_time" | "adaptive" | "fallback") | null;
export type ActiveApproach = ("U" | "T" | "S" | "B") | null;
export type Phase = ("green" | "yellow" | "all_red") | null;
export type Signals = {
  [k: string]: "red" | "yellow" | "green";
} | null;
export type ClearanceState = ("minimum" | "waiting_conflict" | "waiting_command") | null;
export type State = "clear" | "occupied" | "unknown";
export type Source = "assumed_clear" | "provider";
export type CheckedAt = string;
export type RemainingSeconds = number | null;
export type SimulationTimeSeconds = number | null;
export type SequenceNumber = number | null;
export type UpdatedAt = string | null;
export type ObservedAt = string;
export type Reason = string | null;

export interface AtcsStatus {
  schema_version: SchemaVersion;
  intersection_id: IntersectionId;
  operating_context: OperatingContext;
  availability: Availability;
  run_id: RunId;
  engine_state: EngineState;
  controller: Controller;
  mode: Mode;
  active_approach: ActiveApproach;
  phase: Phase;
  signals: Signals;
  clearance_state: ClearanceState;
  conflict_area: ConflictArea | null;
  remaining_seconds: RemainingSeconds;
  simulation_time_seconds: SimulationTimeSeconds;
  sequence_number: SequenceNumber;
  updated_at: UpdatedAt;
  observed_at: ObservedAt;
  reason: Reason;
}
export interface ConflictArea {
  state: State;
  source: Source;
  checked_at: CheckedAt;
}
