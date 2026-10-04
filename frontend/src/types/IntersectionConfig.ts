/* Generated from contracts/models.py. Do not edit manually. */

export type SchemaVersion = "2.0";
export type IntersectionId = string;
export type Name = string;
export type Location = string;
export type Timezone = "Asia/Jakarta";
export type OperatingContext = "simulation";
export type DrivingSide = "left";
export type IncomingLanesPerApproach = 3;
export type OutgoingLanesPerApproach = 3;
export type Median = true;
export type LeftTurnSlipRoads = 4;
export type SeparatingIslands = true;
export type LeftTurnSignalControlled = false;
export type YieldAtMerge = true;
export type UTurnAllowed = false;
export type LaneChangeInIntersection = false;
export type BlockEntryWhenExitBlocked = true;
export type CompleteCommittedMovement = true;
export type SlipForkBeforeStopLine = true;
export type SlipMergeAfterIntersection = true;
/**
 * @minItems 4
 * @maxItems 4
 */
export type Approaches = [Approach, Approach, Approach, Approach];
export type Code = "U" | "T" | "S" | "B";
export type Road = string;
export type Side = string;
export type Left = "U" | "T" | "S" | "B";
export type Straight = "U" | "T" | "S" | "B";
export type Right = "U" | "T" | "S" | "B";
/**
 * @minItems 4
 * @maxItems 4
 */
export type Sequence = ["U" | "T" | "S" | "B", "U" | "T" | "S" | "B", "U" | "T" | "S" | "B", "U" | "T" | "S" | "B"];
export type YellowSeconds = number;
export type AllRedMinSeconds = number;
export type NominalCycleSeconds = number;
export type ExtendAllRedUntilConflictClear = true;
export type TimingSourceUrl = string;
export type TimingSourceYear = number;
export type TimingBasis = string;
export type SequenceBasis = string;
export type GeometryBasis = string;
export type CurrentFieldConfigurationVerified = false;

export interface IntersectionConfig {
  schema_version: SchemaVersion;
  intersection_id: IntersectionId;
  name: Name;
  location: Location;
  timezone: Timezone;
  operating_context: OperatingContext;
  geometry: Geometry;
  approaches: Approaches;
  fixed_time: FixedTime;
  provenance: Provenance;
}
export interface Geometry {
  driving_side: DrivingSide;
  incoming_lanes_per_approach: IncomingLanesPerApproach;
  outgoing_lanes_per_approach: OutgoingLanesPerApproach;
  median: Median;
  left_turn_slip_roads: LeftTurnSlipRoads;
  separating_islands: SeparatingIslands;
  left_turn_signal_controlled: LeftTurnSignalControlled;
  yield_at_merge: YieldAtMerge;
  u_turn_allowed: UTurnAllowed;
  lane_change_in_intersection: LaneChangeInIntersection;
  block_entry_when_exit_blocked: BlockEntryWhenExitBlocked;
  complete_committed_movement: CompleteCommittedMovement;
  slip_fork_before_stop_line: SlipForkBeforeStopLine;
  slip_merge_after_intersection: SlipMergeAfterIntersection;
}
export interface Approach {
  code: Code;
  road: Road;
  side: Side;
  outer: OuterLane;
  middle: MiddleLane;
  inner: InnerLane;
}
export interface OuterLane {
  left: Left;
}
export interface MiddleLane {
  straight: Straight;
}
export interface InnerLane {
  right: Right;
}
export interface FixedTime {
  sequence: Sequence;
  green_seconds: GreenSeconds;
  yellow_seconds: YellowSeconds;
  all_red_min_seconds: AllRedMinSeconds;
  nominal_cycle_seconds: NominalCycleSeconds;
  extend_all_red_until_conflict_clear: ExtendAllRedUntilConflictClear;
}
export interface GreenSeconds {
  [k: string]: number;
}
export interface Provenance {
  timing_source_url: TimingSourceUrl;
  timing_source_year: TimingSourceYear;
  timing_basis: TimingBasis;
  sequence_basis: SequenceBasis;
  geometry_basis: GeometryBasis;
  current_field_configuration_verified: CurrentFieldConfigurationVerified;
}
