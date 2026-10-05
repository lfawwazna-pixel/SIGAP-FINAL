/* Generated from contracts/video.py. Do not edit manually. */

/**
 * @minItems 4
 * @maxItems 4
 */
export type Channels = [VideoChannelView, VideoChannelView, VideoChannelView, VideoChannelView];
export type Direction = "U" | "T" | "S" | "B";
export type Source = "none" | "recording" | "live";
export type SourceSession = string;
export type State = "empty" | "ready" | "connecting" | "playing" | "paused" | "ended" | "error" | "stale";
export type Label = string;
export type FrameId = number;
export type MediaSeconds = number | null;
export type FrameAgeSeconds = number | null;
export type LiveConfigured = boolean;
export type DetectionReady = boolean;
export type State1 = "disabled" | "warming" | "tracking" | "stale" | "error";
export type SourceSession1 = string;
export type FrameId1 = number;
export type AgeSeconds = number | null;
export type ProcessingFps = number | null;
export type ObservedFps = number | null;
export type Device = string | null;
export type TrackId = number;
export type ClassName = "car" | "motorcycle" | "bus" | "truck" | "ambulance" | "fire_truck";
export type Confidence = number;
/**
 * @minItems 4
 * @maxItems 4
 */
export type Bbox = [number, number, number, number];
export type Tracks = TrackedVehicle[];
export type Message = string;
export type X = number;
export type Y = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type StopLine = [Point, Point];
export type Message1 = string;
export type PreviewFps = 5;

export interface VideoStatus {
  channels: Channels;
  preview_fps: PreviewFps;
}
export interface VideoChannelView {
  direction: Direction;
  source: Source;
  source_session: SourceSession;
  state: State;
  label: Label;
  frame_id: FrameId;
  media_seconds: MediaSeconds;
  frame_age_seconds: FrameAgeSeconds;
  live_configured: LiveConfigured;
  detection_ready: DetectionReady;
  tracking: TrackingView | null;
  calibration: VideoCalibration | null;
  message: Message1;
}
export interface TrackingView {
  state: State1;
  source_session: SourceSession1;
  frame_id: FrameId1;
  age_seconds: AgeSeconds;
  processing_fps: ProcessingFps;
  observed_fps: ObservedFps;
  device: Device;
  tracks: Tracks;
  message: Message;
}
export interface TrackedVehicle {
  track_id: TrackId;
  class_name: ClassName;
  confidence: Confidence;
  bbox: Bbox;
}
export interface VideoCalibration {
  lanes: Lanes;
  stop_line: StopLine;
}
export interface Lanes {
  [k: string]: Point[];
}
export interface Point {
  x: X;
  y: Y;
}
