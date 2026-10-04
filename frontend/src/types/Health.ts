/* Generated from contracts/models.py. Do not edit manually. */

export type Service = "backend" | "atcs";
export type Stage = "2A" | "2B" | "2D" | "2F" | "4" | "5";
export type Liveness = "alive";
export type FoundationReady = boolean;
export type CheckedAt = string;
export type Configuration = "valid";
export type Status = "not_configured" | "unavailable" | "reachable" | "not_required";
export type SchemaStatus = "current" | "missing_or_outdated" | "unknown" | "not_required";
export type PhaseEngine = "not_implemented" | "not_hosted" | "running" | "faulted" | "stopped" | "stalled";
export type Authentication = "not_implemented" | "available" | "unavailable";
export type Override = "not_implemented" | "available" | "unavailable";
export type Ai = "not_implemented";
export type Cctv = "not_configured" | "configured";

export interface Health {
  service: Service;
  stage: Stage;
  liveness: Liveness;
  foundation_ready: FoundationReady;
  checked_at: CheckedAt;
  configuration: Configuration;
  database: DatabaseCheck;
  capabilities: Capabilities;
}
export interface DatabaseCheck {
  status: Status;
  schema_status: SchemaStatus;
}
export interface Capabilities {
  phase_engine: PhaseEngine;
  authentication: Authentication;
  override: Override;
  ai: Ai;
  cctv: Cctv;
}
