/* Generated from contracts/traffic.py. Do not edit manually. */

export type IntersectionId = string;
export type Source = "atcs_synthetic" | "experiment";
export type RunId = string;
export type ObservedAt = string;
export type Available = boolean;
export type TimeSeconds = number;
export type Running = boolean;
export type Speed = 1 | 2 | 3;
export type Strategy = "fixed_time" | "adaptive";
export type Phase = ("green" | "yellow" | "all_red") | null;
export type ActiveApproach = ("U" | "T" | "S" | "B") | null;
export type Signals = {
  [k: string]: "red" | "yellow" | "green";
} | null;
export type RemainingSeconds = number | null;
export type Emergency = boolean;
export type TargetVehicle = number | null;
export type Reason = string;
export type BlockedExit = ("U" | "T" | "S" | "B") | null;
export type Time = number;
export type Message = string;
/**
 * @maxItems 100
 */
export type Events = ExperimentEvent[];
/**
 * @maxItems 160
 */
export type EvpQueue = number[];
export type Id = number;
export type Origin = "U" | "T" | "S" | "B";
export type Movement = "left" | "straight" | "right";
export type Kind = "car" | "ambulance" | "fire_engine";
export type X = number;
export type Y = number;
export type Heading = number;
export type Stopped = boolean;
export type Served = boolean;
export type DistanceToStop = number;
/**
 * @maxItems 160
 */
export type Vehicles = VehicleView[];
export type Completed = number;
export type AverageWait = number;
export type WaitingSeconds = number;
export type RefusedSpawns = number;
export type Conflict = "clear" | "occupied" | "unknown";
export type TrafficSequence = number;

export interface TrafficView {
  intersection_id: IntersectionId;
  source: Source;
  run_id: RunId;
  observed_at: ObservedAt;
  available: Available;
  time_seconds: TimeSeconds;
  running: Running;
  speed: Speed;
  strategy: Strategy;
  phase: Phase;
  active_approach: ActiveApproach;
  signals: Signals;
  remaining_seconds: RemainingSeconds;
  emergency: Emergency;
  target_vehicle: TargetVehicle;
  reason: Reason;
  demand: Demand;
  blocked_exit: BlockedExit;
  events: Events;
  evp_queue: EvpQueue;
  vehicles: Vehicles;
  queues: Queues;
  completed: Completed;
  average_wait: AverageWait;
  waiting_seconds: WaitingSeconds;
  refused_spawns: RefusedSpawns;
  conflict: Conflict;
  traffic_sequence: TrafficSequence;
}
export interface Demand {
  [k: string]: number;
}
export interface ExperimentEvent {
  time: Time;
  message: Message;
}
export interface VehicleView {
  id: Id;
  origin: Origin;
  movement: Movement;
  kind: Kind;
  x: X;
  y: Y;
  heading: Heading;
  stopped: Stopped;
  served: Served;
  distance_to_stop: DistanceToStop;
}
export interface Queues {
  [k: string]: number;
}
