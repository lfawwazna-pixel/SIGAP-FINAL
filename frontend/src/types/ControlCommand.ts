/* Generated from contracts/control.py. Do not edit manually. */

export type RequestId = string;
export type AtcsRunId = string;
export type SenderId = string;
export type Action = "observe" | "activate" | "heartbeat" | "plan" | "release";
export type IssuedAt = string;
export type ExpiresAt = string;
export type SessionId = string | null;
export type Sequence = number | null;
export type ExpectedRevision = number | null;
export type Source = ("cctv" | "integration_test") | null;
export type Observations = {
  [k: string]: Observation;
} | null;
export type ObservedAt = string;
export type Usable = boolean;
export type Approach = ("U" | "T" | "S" | "B") | null;
export type GreenSeconds = number | null;
export type PlanValidUntil = string | null;

export interface ControlCommand {
  request_id: RequestId;
  atcs_run_id: AtcsRunId;
  sender_id: SenderId;
  action: Action;
  issued_at: IssuedAt;
  expires_at: ExpiresAt;
  session_id?: SessionId;
  sequence?: Sequence;
  expected_revision?: ExpectedRevision;
  source?: Source;
  observations?: Observations;
  approach?: Approach;
  green_seconds?: GreenSeconds;
  plan_valid_until?: PlanValidUntil;
}
export interface Observation {
  observed_at: ObservedAt;
  usable: Usable;
}
