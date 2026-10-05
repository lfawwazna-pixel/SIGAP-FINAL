from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from contracts.models import Contract, Direction


class Point(Contract):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class VideoCalibration(Contract):
    lanes: dict[Literal['outer', 'middle', 'inner'], list[Point]] = Field(min_length=3, max_length=3)
    stop_line: list[Point] = Field(min_length=2, max_length=2)

    @model_validator(mode='after')
    def polygons(self):
        if set(self.lanes) != {'outer', 'middle', 'inner'}:
            raise ValueError('Three lanes required')
        for points in self.lanes.values():
            if not 3 <= len(points) <= 12:
                raise ValueError('Polygon requires 3-12 points')
            area = abs(sum(a.x*b.y-b.x*a.y for a,b in zip(points,points[1:]+points[:1])))/2
            if area < .001:
                raise ValueError('Lane polygon is too small')
        a,b = self.stop_line
        if (a.x-b.x)**2+(a.y-b.y)**2 < .0001:
            raise ValueError('Stop line is too short')
        return self


class TrackedVehicle(Contract):
    track_id: int = Field(ge=1)
    class_name: Literal['car', 'motorcycle', 'bus', 'truck', 'ambulance', 'fire_truck']
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    bbox: list[float] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def valid_box(self):
        x1, y1, x2, y2 = self.bbox
        if not all(0 <= x <= 1 for x in self.bbox) or x2 < x1 or y2 < y1:
            raise ValueError('Invalid normalized bounding box')
        return self


class TrackingView(Contract):
    state: Literal['disabled', 'warming', 'tracking', 'stale', 'error']
    source_session: UUID
    frame_id: int = Field(ge=0)
    age_seconds: float | None
    processing_fps: float | None
    observed_fps: float | None
    device: str | None
    tracks: list[TrackedVehicle]
    message: str


class VideoChannelView(Contract):
    direction: Direction
    source: Literal['none', 'recording', 'live']
    source_session: UUID
    state: Literal['empty', 'ready', 'connecting', 'playing', 'paused', 'ended', 'error', 'stale']
    label: str
    frame_id: int
    media_seconds: float | None
    frame_age_seconds: float | None
    live_configured: bool
    detection_ready: bool = False
    tracking: TrackingView | None = None
    calibration: VideoCalibration | None
    message: str


class VideoStatus(Contract):
    channels: list[VideoChannelView] = Field(min_length=4, max_length=4)
    preview_fps: Literal[5] = 5


class VideoCommand(Contract):
    expected_session: UUID
    action: Literal['play', 'pause', 'restart', 'use_live', 'calibrate']
    calibration: VideoCalibration | None = None

    @model_validator(mode='after')
    def parameters(self):
        if (self.action == 'calibrate') != (self.calibration is not None):
            raise ValueError('Calibration only belongs to calibrate action')
        return self
