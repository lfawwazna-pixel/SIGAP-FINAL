/* Generated from contracts/history.py. Do not edit manually. */

export type IntersectionId = string;
export type EventId = string;
export type IntersectionId1 = string;
export type RunId = string;
export type EventType =
  | "service_started"
  | "service_stopped"
  | "phase_changed"
  | "clearance_held"
  | "clearance_released"
  | "control_changed"
  | "fault"
  | "recovered";
export type Source = "backend" | "atcs" | "adaptive_control";
export type SequenceNumber = number;
export type OccurredAt = string;
export type SimulationTimeSeconds = number | null;
export type Reason = string;
export type PreviousPhase = ("green" | "yellow" | "all_red") | null;
export type PreviousApproach = ("U" | "T" | "S" | "B") | null;
export type Phase = "green" | "yellow" | "all_red";
export type ActiveApproach = ("U" | "T" | "S" | "B") | null;
export type Events = TrafficEvent[];
export type NextBefore = number | null;
export type HasMore = boolean;
export type GeneratedAt = string;
export type Filter = "all" | "phase" | "incident";

export interface EventArchivePage {
  intersection_id: IntersectionId;
  events: Events;
  next_before: NextBefore;
  has_more: HasMore;
  generated_at: GeneratedAt;
  filter: Filter;
}
export interface TrafficEvent {
  event_id: EventId;
  intersection_id: IntersectionId1;
  run_id: RunId;
  event_type: EventType;
  source: Source;
  sequence_number: SequenceNumber;
  occurred_at: OccurredAt;
  simulation_time_seconds: SimulationTimeSeconds;
  reason: Reason;
  previous_phase: PreviousPhase;
  previous_approach: PreviousApproach;
  phase: Phase;
  active_approach: ActiveApproach;
}
