/* Generated from contracts/control.py. Do not edit manually. */

export type IntersectionId = string;
export type AtcsRunId = string;
export type ObservedAt = string;
export type Available = boolean;
export type Configured = boolean;
export type AllowTestSource = boolean;
export type State = "fixed_time" | "activating" | "adaptive" | "returning_atcs";
export type Controller = "ATCS" | "SIGAP";
export type Revision = number;
export type SenderId = string | null;
export type Source = ("cctv" | "integration_test") | null;
export type Ready = boolean;
export type ReadinessReason = string;
export type ActivationRequired = boolean;
export type SessionId = string | null;
export type HeartbeatRemainingSeconds = number | null;
export type DataRemainingSeconds = number | null;
export type PendingRequestId = string | null;
export type ActiveRequestId = string | null;
export type FallbackCode = string | null;
export type Reason = string;
export type HeartbeatTimeoutSeconds = number;
export type DataTimeoutSeconds = number;
export type PlanWaitSeconds = number;
export type MinimumGreenSeconds = number;
export type MaximumGreenSeconds = number;
export type MaximumCommandTtlSeconds = number;
export type MaximumPlanHorizonSeconds = number;
export type ClockSkewSeconds = number;
export type Sequence = number;
export type OccurredAt = string;
export type Code = string;
export type Message = string;
export type RequestId = string | null;
/**
 * @maxItems 100
 */
export type Events = ControlEvent[];
export type EventId = string;
export type Direction = "U" | "T" | "S" | "B";
export type SourceSession = string;
export type TrackId = number;
export type Kind = "ambulance" | "fire_truck";
export type Confidence = number;
export type DistanceToStop = number;
export type ObservedAt1 = string;
export type EmergencyServing = boolean;

export interface ControlStatus {
  intersection_id: IntersectionId;
  atcs_run_id: AtcsRunId;
  observed_at: ObservedAt;
  available: Available;
  configured: Configured;
  allow_test_source: AllowTestSource;
  state: State;
  controller: Controller;
  revision: Revision;
  sender_id: SenderId;
  source: Source;
  ready: Ready;
  readiness_reason: ReadinessReason;
  activation_required: ActivationRequired;
  session_id: SessionId;
  heartbeat_remaining_seconds: HeartbeatRemainingSeconds;
  data_remaining_seconds: DataRemainingSeconds;
  pending_request_id: PendingRequestId;
  active_request_id: ActiveRequestId;
  fallback_code: FallbackCode;
  reason: Reason;
  policy: ControlPolicy;
  events: Events;
  emergency: EmergencyTarget | null;
  emergency_serving: EmergencyServing;
}
export interface ControlPolicy {
  heartbeat_timeout_seconds: HeartbeatTimeoutSeconds;
  data_timeout_seconds: DataTimeoutSeconds;
  plan_wait_seconds: PlanWaitSeconds;
  minimum_green_seconds: MinimumGreenSeconds;
  maximum_green_seconds: MaximumGreenSeconds;
  maximum_command_ttl_seconds: MaximumCommandTtlSeconds;
  maximum_plan_horizon_seconds: MaximumPlanHorizonSeconds;
  clock_skew_seconds: ClockSkewSeconds;
}
export interface ControlEvent {
  sequence: Sequence;
  occurred_at: OccurredAt;
  code: Code;
  message: Message;
  request_id: RequestId;
}
export interface EmergencyTarget {
  event_id: EventId;
  direction: Direction;
  source_session: SourceSession;
  track_id: TrackId;
  kind: Kind;
  confidence: Confidence;
  distance_to_stop: DistanceToStop;
  observed_at: ObservedAt1;
}
