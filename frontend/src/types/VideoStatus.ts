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
export type DetectionReady = false;
export type X = number;
export type Y = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type StopLine = [Point, Point];
export type Message = string;
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
  calibration: VideoCalibration | null;
  message: Message;
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
