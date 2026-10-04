/* Generated from contracts/control.py. Do not edit manually. */

export type RequestId = string;
export type Action = "activate" | "release";
export type ExpectedRunId = string;
export type ExpectedRevision = number;

export interface OperatorControl {
  request_id: RequestId;
  action: Action;
  expected_run_id: ExpectedRunId;
  expected_revision: ExpectedRevision;
}
