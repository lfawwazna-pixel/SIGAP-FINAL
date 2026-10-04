"""Deterministic synthetic traffic. Coordinates are schematic map units, not metres."""
from dataclasses import dataclass
from bisect import bisect_right
import math
import random
import json
from contracts.configuration import PROJECT_ROOT

DIRECTIONS = ('U', 'T', 'S', 'B')
VEHICLE_LENGTH = 26.0
GAP = 8.0
START, END, CENTER = -200.0, 1000.0, 400.0
MAP_GEOMETRY = json.loads((PROJECT_ROOT / 'configs/map-geometry.json').read_text(encoding='utf-8'))


def rotate(point, index):
    x, y = point[0] - CENTER, point[1] - CENTER
    for _ in range(index):
        x, y = -y, x
    return (round(x + CENTER, 4), round(y + CENTER, 4))


def bezier(a, b, c, d, count=40):
    return [tuple((1-t)**3*a[j] + 3*(1-t)**2*t*b[j] + 3*(1-t)*t*t*c[j] + t**3*d[j]
                  for j in range(2)) for t in (i/count for i in range(1, count+1))]


class Route:
    def __init__(self, origin, movement, lane):
        x = 470 if lane == 'outer' else 430
        points = [(x, START)]
        if movement == 'left':
            slip = MAP_GEOMETRY['slip']
            points += [tuple(slip['start'])] + bezier(slip['start'], slip['control1'], slip['control2'], slip['end']) + [(END, 330)]
            destination = (DIRECTIONS.index(origin) + 1) % 4
            # Stop/yield before the shared outgoing lane, not at the signal.
            self.gate = math.dist(points[0], points[1]) + sum(math.dist(a, b) for a, b in zip(points[1:-2], points[2:-1])) - slip['yield_before_merge']
        elif movement == 'right':
            points += [(430, 297)] + bezier((430, 297), (430, 400), (400, 430), (297, 430)) + [(START, 430)]
            destination = (DIRECTIONS.index(origin) + 3) % 4
            self.gate = 497
        else:
            points += [(x, END)]
            destination = (DIRECTIONS.index(origin) + 2) % 4
            self.gate = 497
        self.points = [rotate(point, DIRECTIONS.index(origin)) for point in points]
        self.lengths = [0.0]
        for a, b in zip(self.points, self.points[1:]):
            self.lengths.append(self.lengths[-1] + math.dist(a, b))
        self.length = self.lengths[-1]
        self.origin, self.movement, self.lane = origin, movement, lane
        self.destination = DIRECTIONS[destination]
        self.exit_lane = 'outer' if movement == 'left' else lane
        self.exit_start = self.lengths[-2] if movement != 'straight' else 697

    def position(self, distance):
        distance = min(self.length, max(0.0, distance))
        i = min(len(self.points)-2, bisect_right(self.lengths, distance)-1)
        a, b = self.points[i:i+2]
        ratio = (distance-self.lengths[i]) / (self.lengths[i+1]-self.lengths[i])
        return (a[0]+ratio*(b[0]-a[0]), a[1]+ratio*(b[1]-a[1]), math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])))


ROUTES = {f'{d}:{m}:{lane}': Route(d, m, lane) for d in DIRECTIONS
          for m, lane in [('left', 'outer'), ('straight', 'outer'), ('straight', 'inner'), ('right', 'inner')]}


@dataclass
class Vehicle:
    id: int
    route_id: str
    kind: str
    distance: float
    born: float
    wait: float = 0
    stopped: bool = False
    committed: bool = False
    served: bool = False

    @property
    def route(self):
        return ROUTES[self.route_id]


class TrafficWorld:
    source = 'provider'

    def __init__(self, seed=42, demand=10):
        self.random = random.Random(seed)
        self.vehicles: list[Vehicle] = []
        self.time = 0.0
        self.sequence = 0
        self.next_id = 1
        self.demand = dict.fromkeys(DIRECTIONS, demand)
        self.arrivals = {d: self.random.uniform(0, 5) for d in DIRECTIONS}
        self.blocked_exit = None
        self.completed = 0
        self.completed_wait = 0.0
        self.refused = 0
        self.events = []

    def record(self, message):
        self.events.append({'time': round(self.time, 2), 'message': message})
        self.events = self.events[-100:]

    def read(self):
        return 'occupied' if any(self.in_conflict(v) for v in self.vehicles) else 'clear'

    def in_conflict(self, vehicle):
        return (vehicle.route.movement != 'left' and vehicle.committed
                and vehicle.distance < vehicle.route.exit_start + VEHICLE_LENGTH)

    def spawn(self, direction, kind='car', distance=None, movement=None, lane=None):
        if len(self.vehicles) >= 160:
            self.refused += 1
            return None
        movement = movement or (self.random.choices(['left', 'straight', 'right'], [25, 55, 20])[0] if kind == 'car' else 'straight')
        lane = lane or ('outer' if movement == 'left' else 'inner' if movement == 'right' else self.random.choice(['inner', 'outer']))
        route_id = f'{direction}:{movement}:{lane}'
        route = ROUTES[route_id]
        progress = max(0.0, route.gate - (distance if distance is not None else route.gate))
        # Never insert a vehicle on top of another one. Try upstream positions.
        while progress >= 0:
            p = route.position(progress)
            if all(math.dist(p[:2], v.route.position(v.distance)[:2]) >= VEHICLE_LENGTH+GAP for v in self.vehicles):
                vehicle = Vehicle(self.next_id, route_id, kind, progress, self.time)
                self.next_id += 1
                self.vehicles.append(vehicle)
                if kind != 'car':
                    self.record(f'{"Ambulans" if kind == "ambulance" else "Pemadam"} #{vehicle.id} muncul dari {direction}.')
                return vehicle
            progress -= VEHICLE_LENGTH+GAP
        self.refused += 1
        return None

    def candidates(self):
        return sorted((v for v in self.vehicles if v.kind != 'car' and not v.served),
                      key=lambda v: (0 if v.kind == 'ambulance' else 1,
                                     max(0, v.route.gate-v.distance), v.born, v.id))

    def exit_available(self, vehicle):
        r = vehicle.route
        if self.blocked_exit == r.destination:
            return False
        reserved = sum(1 for other in self.vehicles if other.id != vehicle.id
                       and other.committed and other.route.destination == r.destination
                       and other.route.exit_lane == r.exit_lane)
        return reserved < 12

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
                self.arrivals[direction] += 60/self.demand[direction]
        # Existing outgoing traffic moves first and has priority over merging slips.
        ordered = sorted(self.vehicles, key=lambda v: (v.distance >= v.route.exit_start, v.committed, v.distance), reverse=True)
        positions = {v.id: v.route.position(v.distance)[:2] for v in self.vehicles}
        cells = {}
        def cell(p):
            return (math.floor(p[0]/68), math.floor(p[1]/68))
        for identity, position in positions.items():
            cells.setdefault(cell(position), set()).add(identity)
        for vehicle in ordered:
            r = vehicle.route
            advance = (38 if r.movement != 'straight' and r.gate-25 < vehicle.distance < r.exit_start else 48) * dt
            target = min(r.length, vehicle.distance + advance)
            gate = r.gate - VEHICLE_LENGTH/2
            if not vehicle.committed and target >= gate:
                permitted = self.exit_available(vehicle)
                if r.movement != 'left':
                    permitted = permitted and signals.get(r.origin) == 'green'
                    permitted = permitted and not any(self.in_conflict(v) and v.route.origin != r.origin for v in self.vehicles)
                else:
                    merge = r.position(r.exit_start)
                    permitted = permitted and not any(
                        v.id != vehicle.id and v.route.destination == r.destination and v.route.exit_lane == r.exit_lane
                        # A slip queue follows its leader via the spacing rule below. It must
                        # never yield to its own followers and create a circular wait.
                        and v.route.movement != 'left' and v.committed
                        and math.dist(v.route.position(v.distance)[:2], merge[:2]) < 200
                        for v in self.vehicles)
                if not permitted:
                    target = min(target, gate)
            if self.blocked_exit == r.destination:
                target = min(target, r.length-30)
            p = r.position(target)
            # Conservative circle envelope includes nose/tail, merges, and shared lanes.
            cx, cy = cell(p)
            neighbors = (identity for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                         for identity in cells.get((cx+dx, cy+dy), ()))
            if any(identity != vehicle.id and math.dist(p[:2], positions[identity]) < VEHICLE_LENGTH+GAP
                   for identity in neighbors):
                target = vehicle.distance
            vehicle.stopped = target - vehicle.distance < .01
            if vehicle.stopped:
                vehicle.wait += dt
            vehicle.distance = max(vehicle.distance, target)
            cells[cell(positions[vehicle.id])].discard(vehicle.id)
            positions[vehicle.id] = r.position(vehicle.distance)[:2]
            cells.setdefault(cell(positions[vehicle.id]), set()).add(vehicle.id)
            if vehicle.distance > gate + .01:
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
        return {
            'vehicles': [{'id': v.id, 'origin': v.route.origin, 'movement': v.route.movement, 'kind': v.kind,
                          'x': round(v.route.position(v.distance)[0], 2), 'y': round(v.route.position(v.distance)[1], 2),
                          'heading': round(v.route.position(v.distance)[2], 2), 'stopped': v.stopped,
                          'distance_to_stop': round(max(0, v.route.gate-v.distance), 2), 'served': v.served}
                         for v in self.vehicles],
            'queues': {d: sum(v.stopped and v.route.origin == d and not v.committed for v in self.vehicles) for d in DIRECTIONS},
            'completed': self.completed, 'average_wait': round(self.completed_wait/self.completed, 2) if self.completed else 0,
            'waiting_seconds': round(sum(v.wait for v in self.vehicles), 2), 'refused_spawns': self.refused,
            'conflict': self.read(), 'traffic_sequence': self.sequence,
        }
