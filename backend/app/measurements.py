"""Calibrated demand plus one schematic map pose per fresh tracked vehicle."""
from collections import deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import hypot
import json
import time
from uuid import uuid4

from contracts.adaptive import MeasurementBatch
from contracts.configuration import PROJECT_ROOT
from contracts.vehicles import VehicleView

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAP_GEOMETRY = json.loads((PROJECT_ROOT / 'configs/map-geometry.json').read_text(encoding='utf-8'))
MAP_BODY_LENGTH, MAP_CLEARANCE, MAP_PITCH = 26, 6, 36


def inside(x, y, polygon):
    crossing = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a.y > y) != (b.y > y) and x < (b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x:
            crossing = not crossing
    return crossing


def line_side(x, y, line):
    a, b = line
    return (b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x)


def map_poses(direction, generation, entries):
    """Keep every track visible on its camera's approach, including outside the ROI.

    Slots represent presence, not camera pixel coordinates or simulated motion.
    Keep IDs in a stable order; noisy boxes must not make vehicles overtake each
    other. The renderer scales crowded lanes to their actual slot spacing.
    """
    vehicles = []
    for lane in ('outer', 'middle', 'inner'):
        ordered = sorted((e for e in entries if e['lane'] == lane),
                         key=lambda e: e['track'].track_id)
        # Leave the complete body inside the road, behind the stop line/fork.
        clearance = MAP_BODY_LENGTH/2 + MAP_CLEARANCE
        front = (MAP_GEOMETRY['slip']['start'][1] if lane == 'outer'
                 else MAP_GEOMETRY['stop_line']) - clearance
        back = MAP_GEOMETRY['start'] + clearance
        gap = min(MAP_PITCH, (front-back)/max(1, len(ordered)-1))
        for i, entry in enumerate(ordered):
            px, py = MAP_GEOMETRY['lane_centers'][lane], front-i*gap
            for _ in range('UTSB'.index(direction)):
                px, py = 2*MAP_GEOMETRY['center']-py, px
            track = entry['track']
            identity = int.from_bytes(sha256(f'{direction}:{generation}:{track.track_id}'.encode()).digest()[:6], 'big') or 1
            heading = (90+'UTSB'.index(direction)*90+180) % 360-180
            vehicles.append(VehicleView(id=identity, origin=direction,
                movement=dict(outer='left', middle='straight', inner='right')[lane],
                kind={'ambulance':'ambulance', 'fire_truck':'fire_engine'}.get(track.class_name, 'car'),
                x=px, y=py, heading=heading, stopped=entry['stopped'], served=entry['passed'],
                distance_to_stop=max(0, entry['distance']), lane=lane, target_lane=lane, changing_to=None,
                stop_reason='stationary' if entry['stopped'] else None))
    return vehicles


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
                    vehicles.extend(previous[4])
                    if previous[5]:
                        issues[direction] = previous[5]
                    continue
                issues[direction] = 'Video atau tracking belum mutakhir.'
                continue
            calibration = channel.calibration
            if not calibration:
                issues[direction] = 'Tandai tiga lajur dan garis henti dahulu. Kendaraan tetap ditampilkan secara skematis.'
            generation = (channel.tracker_session, calibration.model_dump_json() if calibration else '')
            if self.samples.get(direction, (None,))[0] != generation:
                self.history[direction] = {}
                self.samples[direction] = (generation, None)
            histories = self.history[direction]
            fresh_sample = self.samples[direction][1] != channel.tracked_id
            ambiguous, entries = False, []
            for track in channel.tracks:
                x1, _, x2, y = track.bbox
                x = (x1+x2)/2
                lanes = [lane for lane, polygon in calibration.lanes.items() if inside(x, y, polygon)] if calibration else []
                if len(lanes) > 1:
                    ambiguous = True
                if lanes:
                    lane = lanes[0]
                elif calibration:
                    # An unmatched detection is still real; choose the nearest
                    # marked lane for display, without counting it as demand.
                    lane = min(calibration.lanes, key=lambda name: hypot(
                        x-sum(p.x for p in calibration.lanes[name])/len(calibration.lanes[name]),
                        y-sum(p.y for p in calibration.lanes[name])/len(calibration.lanes[name])))
                else:
                    lane = ('outer', 'middle', 'inner')[min(2, int(x*3))]
                distance, passed, measured = (1-y)*625, False, False
                if calibration and len(lanes) == 1:
                    polygon = calibration.lanes[lane]
                    cx, cy = sum(p.x for p in polygon)/len(polygon), sum(p.y for p in polygon)/len(polygon)
                    upstream = line_side(cx, cy, calibration.stop_line)
                    side = line_side(x, y, calibration.stop_line)
                    if abs(upstream) < .0001:
                        ambiguous = True
                    else:
                        passed = side*upstream < 0
                        measured = lane == 'outer' or not passed
                        extent = max(abs(line_side(p.x, p.y, calibration.stop_line)) for p in polygon)
                        distance = min(1, abs(side)/max(extent, .0001))*625
                history = histories.setdefault(track.track_id, dict(points=deque(), waiting=None, last=now))
                # Display hysteresis is deliberately separate from calibrated
                # demand: a box grazing a lane boundary must not flicker across
                # the map, but the control counts still use this exact sample.
                if 'display_lane' not in history:
                    history.update(display_lane=lane, lane_candidate=lane, lane_votes=0)
                if fresh_sample:
                    if lane == history['display_lane']:
                        history.update(lane_candidate=lane, lane_votes=0)
                    else:
                        history['lane_votes'] = history['lane_votes']+1 if history['lane_candidate'] == lane else 1
                        history['lane_candidate'] = lane
                        if history['lane_votes'] >= 3:
                            history.update(display_lane=lane, lane_votes=0)
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
                entries.append(dict(track=track, lane=history['display_lane'], distance=distance, stopped=stopped, passed=passed))
                if not measured:
                    continue
                if lane == 'outer':
                    value['slip_count'] += 1
                else:
                    value['controlled_count'] += 1
                    if stopped:
                        value['queue_count'] += 1
                        value['oldest_wait_seconds'] = max(value['oldest_wait_seconds'],
                            max(0, channel.tracked_at-history['waiting']))
            displayed = map_poses(direction, channel.tracker_session, entries)
            vehicles.extend(displayed)
            self.samples[direction] = (generation, channel.tracked_id)
            for identity in list(histories):
                if now-histories[identity]['last'] > 3:
                    del histories[identity]
            value['usable'] = calibration is not None and not ambiguous
            if ambiguous:
                issues[direction] = 'Lajur bertumpang tindih atau garis henti membelah area pengamatan.'
            self.previous[direction] = (channel.session, channel.tracker_session,
                calibration.model_copy(deep=True) if calibration else None, value.copy(), displayed, issues.get(direction))
        self.issues, self.vehicles = issues, vehicles
        self.source_sessions = {d:c.session for d,c in hub.channels.items()}
        source = 'cctv' if all(c.source == 'live' for c in hub.channels.values()) else 'recording'
        return MeasurementBatch(intersection_id=self.intersection, source=source, source_session=self.session,
                                sequence=self.sequence, approaches=approaches)
