"""Image-space queue estimates. Never infer demand from uncalibrated/stale video."""
from collections import deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import hypot
import time
from uuid import uuid4

from contracts.adaptive import MeasurementBatch
from contracts.vehicles import VehicleView

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def inside(x, y, polygon):
    crossing = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a.y > y) != (b.y > y) and x < (b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x:
            crossing = not crossing
    return crossing


def line_side(x, y, line):
    a, b = line
    return (b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x)


class VideoMeasurements:
    def __init__(self, intersection):
        self.intersection = intersection
        self.session = uuid4()
        self.sequence = 0
        self.identities = None
        self.history = {}
        self.samples = {}
        self.issues = {}
        self.vehicles = []
        self.source_sessions = {}
        self.previous = {}
        self.stamps = {}

    def snapshot(self, hub):
        now, at = time.monotonic(), datetime.now(timezone.utc)
        identities = tuple((d, c.session, c.tracker_session, c.tracked_id, c.view().state, c.view().detection_ready,
                            c.calibration.model_dump_json() if c.calibration else '')
                           for d, c in hub.channels.items())
        if identities != self.identities:
            self.sequence += 1
            self.identities = identities
        approaches, vehicles, issues = {}, [], {}
        for direction, channel in hub.channels.items():
            view = channel.view()
            identity = (channel.session, channel.tracker_session, channel.tracked_id, channel.tracked_at)
            if self.stamps.get(direction, (None,))[0] != identity:
                # The same captured frame must always carry exactly the same UTC timestamp.
                stamp = at-timedelta(seconds=max(0, now-channel.tracked_at)) if channel.tracked_at is not None else EPOCH
                if channel.tracked_at is None and direction in self.previous:
                    stamp = self.previous[direction][3]['observed_at']
                self.stamps[direction] = (identity, stamp)
            stamp = self.stamps[direction][1]
            value = dict(observed_at=stamp, usable=False, controlled_count=0, queue_count=0,
                         oldest_wait_seconds=0, slip_count=0, exit_available=True)
            approaches[direction] = value
            if not view.detection_ready or view.state != 'playing':
                previous = self.previous.get(direction)
                # A loop boundary resets the tracker, not camera health. Bridge only the
                # original, still-fresh observation; never refresh its timestamp.
                if (view.state == 'playing' and channel.vision.enabled and previous
                        and previous[0] == channel.session and previous[1] != channel.tracker_session
                        and previous[2] == channel.calibration and (at-previous[3]['observed_at']).total_seconds() <= 3):
                    approaches[direction] = previous[3].copy()
                    continue
                issues[direction] = 'Video atau tracking belum mutakhir.'
                continue
            if not channel.calibration:
                issues[direction] = 'Tandai tiga lajur dan garis henti dahulu.'
                continue
            calibration = channel.calibration
            generation = (channel.tracker_session, calibration.model_dump_json())
            if self.samples.get(direction, (None,))[0] != generation:
                self.history[direction] = {}
                self.samples[direction] = (generation, None)
            histories = self.history[direction]
            fresh_sample = self.samples[direction][1] != channel.tracked_id
            ambiguous = False
            for track in channel.tracks:
                x1, _, x2, y = track.bbox
                x = (x1+x2)/2
                lanes = [lane for lane, polygon in calibration.lanes.items() if inside(x, y, polygon)]
                if len(lanes) > 1:
                    ambiguous = True
                if len(lanes) != 1:
                    continue
                lane = lanes[0]
                polygon = calibration.lanes[lane]
                cx, cy = sum(p.x for p in polygon)/len(polygon), sum(p.y for p in polygon)/len(polygon)
                upstream = line_side(cx, cy, calibration.stop_line)
                side = line_side(x, y, calibration.stop_line)
                if abs(upstream) < .0001:
                    ambiguous = True
                    continue
                if lane != 'outer' and side*upstream < 0:
                    continue  # Already across the stop line; no longer controlled demand.
                history = histories.setdefault(track.track_id, dict(points=deque(), waiting=None, last=now))
                if fresh_sample:
                    captured = channel.tracked_at
                    points = history['points']
                    points.append((captured, x, y))
                    while len(points) > 1 and captured-points[0][0] > 1.5:
                        points.popleft()
                    span = captured-points[0][0]
                    stable = span >= .8 and hypot(x-points[0][1], y-points[0][2])/span <= .015
                    history['waiting'] = (history['waiting'] if history['waiting'] is not None else points[0][0]) if stable else None
                    history['last'] = captured
                stopped = history['waiting'] is not None
                if lane == 'outer':
                    value['slip_count'] += 1
                else:
                    value['controlled_count'] += 1
                    if stopped:
                        value['queue_count'] += 1
                        value['oldest_wait_seconds'] = max(value['oldest_wait_seconds'],
                            max(0, channel.tracked_at-history['waiting']))
                extent = max(abs(line_side(p.x, p.y, calibration.stop_line)) for p in polygon)
                distance = min(1, abs(side)/max(extent, .0001))*665
                px, py = dict(outer=510, middle=470, inner=430)[lane], 265-distance
                for _ in range('UTSB'.index(direction)):
                    px, py = 800-py, px
                identity = int.from_bytes(sha256(f'{direction}:{channel.tracker_session}:{track.track_id}'.encode()).digest()[:6], 'big') or 1
                heading = (90+'UTSB'.index(direction)*90+180) % 360-180
                vehicles.append(VehicleView(id=identity, origin=direction,
                    movement=dict(outer='left', middle='straight', inner='right')[lane],
                    kind={'ambulance':'ambulance', 'fire_truck':'fire_engine'}.get(track.class_name, 'car'),
                    x=px, y=py, heading=heading, stopped=stopped, served=False, distance_to_stop=distance,
                    lane=lane, target_lane=lane, changing_to=None, stop_reason='stationary' if stopped else None))
            self.samples[direction] = (generation, channel.tracked_id)
            for identity in list(histories):
                if now-histories[identity]['last'] > 3:
                    del histories[identity]
            value['usable'] = not ambiguous
            self.previous[direction] = (channel.session, channel.tracker_session,
                                        calibration.model_copy(deep=True), value.copy())
            if ambiguous:
                issues[direction] = 'Lajur bertumpang tindih atau garis henti membelah area pengamatan.'
        self.issues, self.vehicles = issues, vehicles
        self.source_sessions = {d:c.session for d,c in hub.channels.items()}
        source = 'cctv' if all(c.source == 'live' for c in hub.channels.values()) else 'recording'
        return MeasurementBatch(intersection_id=self.intersection, source=source, source_session=self.session,
                                sequence=self.sequence, approaches=approaches)
