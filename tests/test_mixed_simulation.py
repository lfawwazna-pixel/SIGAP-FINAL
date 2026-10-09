"""Vehicle mix, physical queue space, and lane sharing in the isolated sandbox."""
from collections import Counter
from itertools import combinations
import pytest

from atcs_simulator.app.traffic import DIRECTIONS, TrafficWorld, GAP, bodies_overlap
from atcs_simulator.app.experiment import Experiment
from contracts.configuration import load_config
from contracts.traffic import TrafficView

RED = dict.fromkeys(DIRECTIONS, 'red')


def advance(world, seconds, signals=RED):
    for _ in range(round(seconds/.05)):
        world.step(.05, signals)


@pytest.mark.parametrize('kind,length', [('motorcycle',22), ('car',26), ('bus',52), ('truck',52), ('ambulance',30), ('fire_engine',26)])
@pytest.mark.parametrize('direction', DIRECTIONS)
def test_front_bumper_stays_behind_red_and_yellow_for_every_size(kind, length, direction):
    world = TrafficWorld(demand=0, mixed_traffic=True)
    vehicle = world.spawn(direction, kind, distance=50, movement='straight')
    advance(world, 5)
    assert vehicle.distance == pytest.approx(vehicle.route.gate-length/2)
    assert not vehicle.committed and world.read() == 'clear'
    advance(world, 1, {**RED, direction:'yellow'})
    assert not vehicle.committed
    advance(world, 1, {**RED, direction:'green'})
    assert vehicle.committed


@pytest.mark.parametrize('kind', ['bus', 'truck'])
def test_long_vehicle_occupies_more_queue_space_and_keeps_actual_tail_gap(kind):
    world = TrafficWorld(demand=0, mixed_traffic=True)
    front = world.spawn('U', 'car', distance=50, movement='straight')
    long = world.spawn('U', kind, distance=110, movement='straight')
    rear = world.spawn('U', 'car', distance=175, movement='straight')
    advance(world, 16)
    assert front.stopped and long.stopped and rear.stopped
    assert long.length == 2*front.length
    for leader, follower in ((front, long), (long, rear)):
        tail_gap = leader.distance-leader.length/2-(follower.distance+follower.length/2)
        assert GAP-.001 <= tail_gap < GAP+1
    assert front.distance-rear.distance > 2*(26+GAP)+25
    advance(world, 25, {**RED, 'U':'green'})
    assert world.completed == 3 and not world.vehicles


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_three_motorcycles_share_lane_width_and_fourth_queues_behind(direction):
    world = TrafficWorld(demand=0, mixed_traffic=True)
    bikes = [world.spawn(direction, 'motorcycle', distance=100, movement='straight') for _ in range(4)]
    assert all(bikes)
    assert len({v.lateral_offset for v in bikes[:3]}) == 3
    assert len({v.distance for v in bikes[:3]}) == 1
    assert bikes[3].distance < bikes[0].distance
    advance(world, 12)
    assert all(v.stopped and not v.committed for v in bikes)
    assert all(v.lane == 'middle' for v in bikes)
    assert len({round(v.distance, 2) for v in bikes[:3]}) == 1
    assert bikes[0].distance-bikes[3].distance >= 22+GAP-.001
    assert max(v.lateral_offset+v.width/2 for v in bikes)-min(v.lateral_offset-v.width/2 for v in bikes) <= 40
    for a, b in combinations(bikes, 2):
        assert not bodies_overlap(a, a.position(), b, b.position())
    advance(world, 26, {**RED, direction:'green'})
    assert world.completed == 4


def test_motorcycles_behind_bus_cannot_use_side_slots_to_cross_its_tail():
    world = TrafficWorld(demand=0, mixed_traffic=True)
    bus = world.spawn('U', 'bus', distance=50, movement='straight')
    bikes = [world.spawn('U', 'motorcycle', distance=120, movement='straight') for _ in range(3)]
    advance(world, 14)
    for bike in bikes:
        assert bike.distance+bike.length/2 <= bus.distance-bus.length/2-GAP+.001
    advance(world, 28, {**RED, 'U':'green'})
    assert world.completed == 4


@pytest.mark.parametrize('direction', DIRECTIONS)
@pytest.mark.parametrize('movement', ['left', 'straight', 'right'])
def test_parallel_motorcycles_can_rotate_through_each_turn_without_deadlock(direction, movement):
    world = TrafficWorld(demand=0, mixed_traffic=True)
    bikes = [world.spawn(direction, 'motorcycle', distance=100, movement=movement) for _ in range(4)]
    assert all(bikes)
    for _ in range(720):
        world.step(.05, {**RED, direction:'green'})
        for a, b in combinations(world.vehicles, 2):
            assert not bodies_overlap(a, a.position(), b, b.position(), safety=False)
    assert world.completed == 4 and not world.vehicles


def test_ordinary_classes_never_become_evp_candidates_or_served_notifications():
    world = TrafficWorld(demand=0, mixed_traffic=True)
    normal = [world.spawn(d, kind, distance=60, movement='straight')
              for d, kind in zip(DIRECTIONS, ('motorcycle','car','bus','truck'))]
    assert world.candidates() == []
    assert not world.events
    for direction in DIRECTIONS:
        advance(world, 30, {**RED, direction:'green'})
    assert world.completed == 4
    assert not any(v.served for v in normal)
    assert not any('EVP' in event['message'] for event in world.events)
    fire = world.spawn('U', 'fire_engine')
    ambulance = world.spawn('T', 'ambulance')
    assert world.candidates() == [ambulance, fire]


def test_random_mix_has_all_ordinary_classes_origins_turns_and_arrival_times_but_no_automatic_evp():
    world = TrafficWorld(seed=42, demand=20, mixed_traffic=True)
    born = []
    original = world.spawn
    def capture(*args, **kwargs):
        vehicle = original(*args, **kwargs)
        if vehicle:
            born.append((vehicle.kind, vehicle.route.origin, vehicle.route.movement, vehicle.born))
        return vehicle
    world.spawn = capture
    advance(world, 100)
    counts = Counter(v[0] for v in born)
    assert set(counts) == {'motorcycle','car','bus','truck'}
    assert counts['motorcycle'] > counts['bus']+counts['truck']
    assert counts['car'] > counts['bus']+counts['truck']
    assert {v[1] for v in born} == set(DIRECTIONS)
    assert {v[2] for v in born} == {'left','straight','right'}
    assert len({round(v[3],2) for v in born}) > 30
    assert not world.candidates()


def test_long_bodies_hold_conflict_until_their_tail_is_clear():
    world = TrafficWorld(demand=0, mixed_traffic=True)
    bus = world.spawn('U', 'bus', distance=20, movement='straight')
    bus.committed = True
    bus.distance = bus.route.exit_start+40
    assert world.read() == 'occupied'
    bus.distance = bus.route.exit_start+bus.length+.01
    assert world.read() == 'clear'


def test_outgoing_capacity_counts_body_space_not_only_vehicle_count():
    world = TrafficWorld(demand=0, mixed_traffic=True)
    queued = world.spawn('U', 'truck', movement='straight')
    for index in range(9):
        bus = world.spawn('U', 'bus', distance=-400-index*60, movement='straight')
        assert bus
        bus.committed = True
    assert len(world.vehicles) == 10
    assert not world.exit_available(queued)


def test_experiment_start_pause_and_snapshot_use_mixed_world_without_evp():
    experiment = Experiment(load_config())
    assert experiment.world.mixed_traffic
    experiment.advance(.5)
    assert experiment.world.time == 0 and not experiment.world.vehicles
    experiment.running = True
    for _ in range(80):
        experiment.advance(.5)
    snapshot = TrafficView.model_validate(experiment.snapshot(load_config().intersection_id))
    assert snapshot.vehicles and not snapshot.emergency and not snapshot.evp_queue
    assert {v.kind for v in snapshot.vehicles} <= {'motorcycle','car','bus','truck'}
    experiment.running = False
    before = experiment.world.snapshot()
    experiment.advance(.5)
    assert experiment.world.snapshot() == before
