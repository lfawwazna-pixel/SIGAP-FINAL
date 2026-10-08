/* Generated from contracts/control.py. Do not edit manually. */

export type RequestId = string;
export type AtcsRunId = string;
export type Action = "observe" | "activate" | "heartbeat" | "plan" | "release" | "priority";
export type Outcome = "accepted" | "applied" | "rejected" | "cancelled";
export type Code = string;
export type Message = string;
export type SessionId = string | null;
export type Revision = number;
export type ReceivedAt = string;
export type UpdatedAt = string;
export type Duplicate = boolean;

export interface CommandReceipt {
  request_id: RequestId;
  atcs_run_id: AtcsRunId;
  action: Action;
  outcome: Outcome;
  code: Code;
  message: Message;
  session_id: SessionId;
  revision: Revision;
  received_at: ReceivedAt;
  updated_at: UpdatedAt;
  duplicate: Duplicate;
}
