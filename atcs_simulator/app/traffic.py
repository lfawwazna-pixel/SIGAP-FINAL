"""Synthetic traffic in shared SVG units. Lane changes happen upstream, never in turns."""
from dataclasses import dataclass
from bisect import bisect_right
import math
import random
import json
from contracts.configuration import PROJECT_ROOT

DIRECTIONS = ('U', 'T', 'S', 'B')
LANES = ('outer', 'middle', 'inner')
MOVEMENT_LANE = {'left': 'outer', 'straight': 'middle', 'right': 'inner'}
VEHICLE_LENGTH, GAP = 26.0, 8.0
MAP_GEOMETRY = json.loads((PROJECT_ROOT / 'configs/map-geometry.json').read_text(encoding='utf-8'))
START, END, CENTER = (MAP_GEOMETRY[k] for k in ('start', 'end', 'center'))
LANE_X = MAP_GEOMETRY['lane_centers']
CHANGE_START = MAP_GEOMETRY['lane_change']['start'] - START
CHANGE_END = MAP_GEOMETRY['lane_change']['end'] - START
CHANGE_LENGTH = MAP_GEOMETRY['lane_change']['length']
CHANGE_GAP = 24.0


def rotate(point, index):
    x, y = point[0] - CENTER, point[1] - CENTER
    for _ in range(index):
        x, y = -y, x
    return (round(x + CENTER, 4), round(y + CENTER, 4))


def bezier(a, b, c, d, count=60):
    return [tuple((1-t)**3*a[j] + 3*(1-t)**2*t*b[j] + 3*(1-t)*t*t*c[j] + t**3*d[j]
                  for j in range(2)) for t in (i/count for i in range(1, count+1))]


class Route:
    def __init__(self, origin, movement, lane):
        x, stop = LANE_X[lane], MAP_GEOMETRY['stop_line']
        points = [(x, START)]
        if movement == 'left':
            slip = MAP_GEOMETRY['slip']
            points += [tuple(slip['start'])] + bezier(slip['start'], slip['control1'], slip['control2'], slip['end']) + [(END, slip['end'][1])]
            destination = (DIRECTIONS.index(origin) + 1) % 4
            self.gate = math.dist(points[0], points[1]) + sum(math.dist(a, b) for a, b in zip(points[1:-2], points[2:-1])) - slip['yield_before_merge']
        elif movement == 'right':
            points += [(x, stop)] + bezier((x, stop), (x, CENTER), (CENTER, x), (stop, x)) + [(START, x)]
            destination = (DIRECTIONS.index(origin) + 3) % 4
            self.gate = stop - START
        else:
            points += [(x, END)]
            destination = (DIRECTIONS.index(origin) + 2) % 4
            self.gate = stop - START
        self.points = [rotate(point, DIRECTIONS.index(origin)) for point in points]
        self.lengths = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.lengths.append(self.lengths[-1] + math.dist(a, b))
        self.length = self.lengths[-1]
        self.origin, self.movement, self.lane = origin, movement, lane
        self.destination, self.exit_lane = DIRECTIONS[destination], lane
        self.exit_start = self.lengths[-2] if movement != 'straight' else MAP_GEOMETRY['exit_clear'] - START

    def position(self, distance):
        distance = min(self.length, max(0.0, distance))
        i = min(len(self.points)-2, bisect_right(self.lengths, distance)-1)
        a, b = self.points[i:i+2]
        ratio = (distance-self.lengths[i]) / (self.lengths[i+1]-self.lengths[i])
        return (a[0]+ratio*(b[0]-a[0]), a[1]+ratio*(b[1]-a[1]), math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])))


ROUTES = {f'{d}:{m}:{lane}': Route(d, m, lane) for d in DIRECTIONS for m, lane in MOVEMENT_LANE.items()}


@dataclass
class Vehicle:
    id: int
    route_id: str
    kind: str
    distance: float
    born: float
    lane: str
    speed: float = 48.0
    change_after: float = CHANGE_START
    changing_to: str | None = None
    change_start: float = 0.0
    changes: int = 0
    request_since: float | None = None
    velocity: float = 0.0
    stop_reason: str | None = None
    wait: float = 0.0
    stopped: bool = False
    committed: bool = False
    served: bool = False

    @property
    def route(self):
        return ROUTES[self.route_id]

    @property
    def changes_needed(self):
        return abs(LANES.index(self.lane) - LANES.index(self.route.lane))

    @property
    def latest_change_start(self):
        return CHANGE_END - self.changes_needed*CHANGE_LENGTH - max(0, self.changes_needed-1)*CHANGE_GAP

    @property
    def occupied_lanes(self):
        return {self.lane, self.changing_to} - {None}

    def position(self, distance=None):
        distance = self.distance if distance is None else distance
        if distance >= MAP_GEOMETRY['slip']['start'][1] - START:
            return self.route.position(distance)
        x, slope = LANE_X[self.lane], 0.0
        if self.changing_to:
            t = min(1.0, max(0.0, (distance-self.change_start)/CHANGE_LENGTH))
            delta = LANE_X[self.changing_to] - x
            x += delta*(10*t**3 - 15*t**4 + 6*t**5)
            slope = delta*30*t*t*(1-t)*(1-t)/CHANGE_LENGTH
        index = DIRECTIONS.index(self.route.origin)
        point = rotate((x, START+distance), index)
        heading = (math.degrees(math.atan2(1, slope)) + 90*index + 180) % 360 - 180
        return (*point, heading)


def swept_distance(a, b, point):
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = dx*dx+dy*dy
    t = max(0.0, min(1.0, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length)) if length else 0.0
    return math.hypot(a[0]+t*dx-point[0], a[1]+t*dy-point[1])


class TrafficWorld:
    source = 'provider'

    def __init__(self, seed=42, demand=10):
        self.random = random.Random(seed)
        self.vehicles: list[Vehicle] = []
        self.time, self.sequence, self.next_id = 0.0, 0, 1
        self.demand = dict.fromkeys(DIRECTIONS, demand)
        self.arrivals = {d: self.random.uniform(0, 5) for d in DIRECTIONS}
        self.blocked_exit = None
        self.completed, self.completed_wait, self.refused = 0, 0.0, 0
        self.events = []

    def record(self, message):
        self.events.append({'time': round(self.time, 2), 'message': message})
        self.events = self.events[-100:]

    def read(self):
        return 'occupied' if any(self.in_conflict(v) for v in self.vehicles) else 'clear'

    def in_conflict(self, vehicle):
        return vehicle.route.movement != 'left' and vehicle.committed and vehicle.distance < vehicle.route.exit_start + VEHICLE_LENGTH

    def spawn(self, direction, kind='car', distance=None, movement=None, lane=None):
        """API commands omit distance: all entries are at the rear boundary.

        Explicit distances are internal scenario fixtures, never exposed by the API.
        """
        if len(self.vehicles) >= 160:
            self.refused += 1
            return None
        explicit_movement = movement is not None
        movement = movement or (self.random.choices(['left', 'straight', 'right'], [25, 55, 20])[0] if kind == 'car' else 'straight')
        target_lane = MOVEMENT_LANE[movement]
        route_id = f'{direction}:{movement}:{target_lane}'
        route = ROUTES[route_id]
        progress = max(0.0, route.gate-distance) if distance is not None else 0.0
        initial_lanes = [lane] if lane else [target_lane] if explicit_movement or kind != 'car' else self.random.sample(list(LANES), len(LANES))
        for initial in initial_lanes:
            entry_lane = target_lane if progress >= CHANGE_END else initial
            entry = progress
            while entry >= 0:
                vehicle = Vehicle(self.next_id, route_id, kind, entry, self.time, entry_lane)
                point = vehicle.position()
                if all(math.dist(point[:2], v.position()[:2]) >= VEHICLE_LENGTH+GAP for v in self.vehicles):
                    vehicle.speed = self.random.uniform(44, 52)
                    vehicle.change_after = self.random.uniform(CHANGE_START, CHANGE_START+80)
                    self.next_id += 1
                    self.vehicles.append(vehicle)
                    if kind != 'car':
                        self.record(f'{"Ambulans" if kind == "ambulance" else "Pemadam"} #{vehicle.id} masuk dari belakang pendekat {direction}.')
                    return vehicle
                entry -= VEHICLE_LENGTH+GAP
        self.refused += 1
        return None

    def candidates(self):
        return sorted((v for v in self.vehicles if v.kind != 'car' and not v.served),
                      key=lambda v: (0 if v.kind == 'ambulance' else 1, max(0, v.route.gate-v.distance), v.born, v.id))

    def exit_available(self, vehicle):
        r = vehicle.route
        if self.blocked_exit == r.destination:
            return False
        reserved = sum(1 for other in self.vehicles if other.id != vehicle.id and other.committed
                       and other.route.destination == r.destination and other.route.exit_lane == r.exit_lane)
        return reserved < 16

    def prepare_changes(self):
        """Reserve a complete corridor, not just the gap at the starting point.

        Positions only advance. An empty corridor through the end of the change
        remains traversable even if the leader stops immediately. Both occupied
        lanes then protect the reservation from followers and other requests.
        """
        yielding = set()
        for direction in DIRECTIONS:
            incoming = [v for v in self.vehicles if v.route.origin == direction and not v.committed]
            requests = [v for v in incoming if not v.changing_to and v.changes_needed
                        and v.change_after <= v.distance <= v.latest_change_start+.00001]
            for v in requests:
                if v.request_since is None:
                    v.request_since = self.time
            # A request keeps its place while seeking a gap; mutual requests cannot
            # alternate priority each frame. Unrelated corridors can run together.
            protected = set()
            for requester in sorted(requests, key=lambda v: (v.request_since, v.id)):
                if requester.id in yielding:
                    continue
                step = 1 if LANES.index(requester.route.lane) > LANES.index(requester.lane) else -1
                target_lane = LANES[LANES.index(requester.lane)+step]
                lanes = {requester.lane, target_lane}
                end = requester.distance+CHANGE_LENGTH
                neighbors = [v for v in incoming if v.id != requester.id and lanes & v.occupied_lanes]
                reservations = [v for v in neighbors if v.changing_to
                    and v.distance-50 < end+VEHICLE_LENGTH+GAP
                    and v.change_start+CHANGE_LENGTH+VEHICLE_LENGTH+GAP > requester.distance-50]
                front_clear = not reservations and all(
                    v.distance-requester.distance >= CHANGE_LENGTH+VEHICLE_LENGTH+GAP+6
                    for v in neighbors if v.distance > requester.distance)
                rear = [v for v in neighbors if target_lane in v.occupied_lanes
                        and 0 <= requester.distance-v.distance < 50]
                if front_clear and not rear:
                    requester.changing_to = target_lane
                    requester.change_start = requester.distance
                    protected.add(requester.id)
                elif front_clear and requester.distance+60 <= requester.latest_change_start:
                    # Only create a gap when there is a usable corridor ahead.
                    # Never ask the higher-priority requester to yield in return.
                    if not any(v.id in protected or v.changing_to for v in rear):
                        yielding.update(v.id for v in rear)
                        protected.add(requester.id)
        return yielding

    def step(self, dt, signals):
        if not 0 < dt <= .100001:
            raise ValueError('Traffic must advance with bounded substeps')
        self.time += dt
        self.sequence += 1
        for direction in DIRECTIONS:
            if self.demand[direction] <= 0:
                continue
            self.arrivals[direction] -= dt
            if self.arrivals[direction] <= 0:
                self.spawn(direction)
                self.arrivals[direction] += max(.8, self.random.expovariate(self.demand[direction]/60))
        yielding = self.prepare_changes()
        ordered = sorted(self.vehicles, key=lambda v: (v.distance >= v.route.exit_start, v.committed, v.distance, -v.id), reverse=True)
        positions = {v.id: v.position()[:2] for v in self.vehicles}
        cells = {}
        def cell(p):
            return (math.floor(p[0]/68), math.floor(p[1]/68))
        for identity, position in positions.items():
            cells.setdefault(cell(position), set()).add(identity)
        for vehicle in ordered:
            r = vehicle.route
            turning = r.movement != 'straight' and r.gate-25 < vehicle.distance < r.exit_start
            desired = min(38, vehicle.speed) if turning else vehicle.speed
            reason = 'stationary' if desired == 0 else None
            if vehicle.id in yielding:
                desired = min(desired, 18)
                reason = 'yielding'
            vehicle.velocity = min(desired, vehicle.velocity+24*dt)
            target = min(r.length, vehicle.distance+vehicle.velocity*dt)
            if vehicle.changing_to:
                target = min(target, vehicle.change_start+CHANGE_LENGTH)
            # A changing vehicle reserves both lanes; a follower cannot pass its tail.
            if vehicle.distance < CHANGE_END+60:
                for other in ordered:
                    if other.id != vehicle.id and other.route.origin == r.origin and other.distance > vehicle.distance and other.distance < CHANGE_END+100 and vehicle.occupied_lanes & other.occupied_lanes:
                        gap = other.distance-vehicle.distance-VEHICLE_LENGTH-GAP
                        following_speed = max(0, gap*1.5)
                        following_target = max(vehicle.distance, other.distance-VEHICLE_LENGTH-GAP)
                        limited = min(target, following_target, vehicle.distance+following_speed*dt)
                        if limited < target:
                            reason = 'following'
                            target = limited
            # Missing a turn must never manufacture a stop in free road. Make the
            # legal route decision upstream, while still centred in the old lane.
            if not vehicle.changing_to and vehicle.changes_needed and vehicle.distance < vehicle.latest_change_start-.00001:
                # Land exactly on the last decision point so a second adjacent
                # change still gets a reservation attempt on the next substep.
                target = min(target, vehicle.latest_change_start)
            if not vehicle.changing_to and vehicle.changes_needed and target > vehicle.latest_change_start+.00001:
                movement = next(m for m, lane in MOVEMENT_LANE.items() if lane == vehicle.lane)
                vehicle.route_id = f'{r.origin}:{movement}:{vehicle.lane}'
                vehicle.request_since = None
                self.record(f'Kendaraan #{vehicle.id}: celah pindah lajur tidak tersedia; mengikuti gerakan sah lajur sebelum percabangan.')
                r = vehicle.route
            gate = r.gate - VEHICLE_LENGTH/2
            if not vehicle.committed and target >= gate:
                permitted = self.exit_available(vehicle)
                if r.movement != 'left':
                    permitted = permitted and signals.get(r.origin) == 'green'
                    permitted = permitted and not any(self.in_conflict(v) and v.route.origin != r.origin for v in self.vehicles)
                else:
                    merge = r.position(r.exit_start)
                    permitted = permitted and not any(v.id != vehicle.id and v.route.destination == r.destination
                        and v.route.exit_lane == r.exit_lane and v.route.movement != 'left' and v.committed
                        and math.dist(v.position()[:2], merge[:2]) < 200 for v in self.vehicles)
                if not permitted:
                    if not self.exit_available(vehicle):
                        reason = 'exit_blocked'
                    elif r.movement != 'left' and signals.get(r.origin) != 'green':
                        reason = 'signal'
                    else:
                        reason = 'conflict'
                    target = min(target, gate)
            if self.blocked_exit == r.destination:
                if target > r.length-30:
                    reason = 'exit_blocked'
                target = min(target, r.length-30)
            point = vehicle.position(target)
            cx, cy = cell(point)
            neighbors = (identity for dx in (-1, 0, 1) for dy in (-1, 0, 1) for identity in cells.get((cx+dx, cy+dy), ()))
            if any(identity != vehicle.id and swept_distance(positions[vehicle.id], point, positions[identity]) < VEHICLE_LENGTH+GAP-.00001 for identity in neighbors):
                reason = 'safety_gap'
                target = vehicle.distance
            vehicle.stopped = target - vehicle.distance < .01
            vehicle.stop_reason = (reason or 'following') if vehicle.stopped else None
            vehicle.velocity = max(0, (target-vehicle.distance)/dt)
            if vehicle.stopped:
                vehicle.wait += dt
            vehicle.distance = max(vehicle.distance, target)
            if vehicle.changing_to and vehicle.distance >= vehicle.change_start+CHANGE_LENGTH-.00001:
                vehicle.lane = vehicle.changing_to
                vehicle.changing_to = None
                vehicle.changes += 1
                vehicle.change_after = vehicle.distance+CHANGE_GAP
                vehicle.request_since = None
            cells[cell(positions[vehicle.id])].discard(vehicle.id)
            positions[vehicle.id] = vehicle.position()[:2]
            cells.setdefault(cell(positions[vehicle.id]), set()).add(vehicle.id)
            if vehicle.distance > r.gate - VEHICLE_LENGTH/2 + .01:
                vehicle.committed = True
            if vehicle.kind != 'car' and vehicle.committed and vehicle.distance >= r.exit_start + VEHICLE_LENGTH:
                if not vehicle.served:
                    self.record(f'EVP #{vehicle.id} sudah melewati area konflik.')
                vehicle.served = True
        finished = [v for v in self.vehicles if v.distance >= v.route.length]
        self.completed += len(finished)
        self.completed_wait += sum(v.wait for v in finished)
        self.vehicles = [v for v in self.vehicles if v.distance < v.route.length]

    def snapshot(self):
        vehicles = []
        for v in self.vehicles:
            x, y, heading = v.position()
            vehicles.append({'id': v.id, 'origin': v.route.origin, 'movement': v.route.movement, 'kind': v.kind,
                             'x': round(x, 2), 'y': round(y, 2), 'heading': round(heading, 2), 'stopped': v.stopped,
                             'distance_to_stop': round(max(0, v.route.gate-v.distance), 2), 'served': v.served,
                             'lane': v.lane, 'target_lane': v.route.lane, 'changing_to': v.changing_to})
            vehicles[-1]['stop_reason'] = v.stop_reason
        return {'vehicles': vehicles,
                'queues': {d: sum(v.stopped and v.route.origin == d and not v.committed for v in self.vehicles) for d in DIRECTIONS},
                'completed': self.completed, 'average_wait': round(self.completed_wait/self.completed, 2) if self.completed else 0,
                'waiting_seconds': round(sum(v.wait for v in self.vehicles), 2), 'refused_spawns': self.refused,
                'conflict': self.read(), 'traffic_sequence': self.sequence}
