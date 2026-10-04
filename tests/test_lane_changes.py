"""Behaviour regressions: changing lanes, queue bypass, and rear-entry EVP."""
import math
from itertools import combinations

import pytest

from atcs_simulator.app.traffic import (
    TrafficWorld, DIRECTIONS, LANES, MOVEMENT_LANE, START, CHANGE_END,
    CHANGE_START, VEHICLE_LENGTH, GAP, rotate,
)
from atcs_simulator.app.experiment import Experiment
from contracts.configuration import load_config
from contracts.traffic import TrafficView

RED = dict.fromkeys(DIRECTIONS, 'red')


def assert_spacing(world):
    for one, two in combinations(world.vehicles, 2):
        assert math.dist(one.position()[:2], two.position()[:2]) >= VEHICLE_LENGTH+GAP-.001


@pytest.mark.parametrize('direction', DIRECTIONS)
@pytest.mark.parametrize('initial,movement', [(lane, move) for lane in LANES for move in MOVEMENT_LANE])
def test_any_initial_lane_reaches_its_destination_in_adjacent_smooth_changes(direction, initial, movement):
    world = TrafficWorld(demand=0)
    car = world.spawn(direction, movement=movement, lane=initial)
    previous = car.position()
    observed_changes = []
    last_target = None
    for _ in range(500):
        world.step(.05, {**RED, direction: 'green'})
        position = car.position()
        assert math.dist(previous[:2], position[:2]) <= car.speed*.05*1.3
        if car.changing_to:
            assert car.distance < CHANGE_END+3
            assert abs(LANES.index(car.lane)-LANES.index(car.changing_to)) == 1
            if car.changing_to != last_target:
                observed_changes.append(car.changing_to)
        last_target = car.changing_to
        previous = position
    expected = abs(LANES.index(initial)-LANES.index(MOVEMENT_LANE[movement]))
    assert car.changes == expected == len(observed_changes)
    assert car.lane == MOVEMENT_LANE[movement]
    assert car.changing_to is None and car.route.movement == movement
    assert car.distance > CHANGE_END


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_dedicated_slip_passes_a_red_signal_queue(direction):
    world = TrafficWorld(demand=0)
    for index in range(12):
        car = world.spawn(direction, movement='straight')
        car.distance = car.route.gate-VEHICLE_LENGTH/2-index*36
    for tick in range(1400):
        if tick < 500 and tick % 100 == 0:
            assert world.spawn(direction, movement='left')
        world.step(.05, RED)
        if tick % 20 == 0:
            assert_spacing(world)
    assert world.completed == 5
    assert len(world.vehicles) == 12
    assert all(v.route.movement == 'straight' and not v.committed for v in world.vehicles)


def test_blocked_adjacent_gap_does_not_trigger_a_cut_or_lane_jump():
    world = TrafficWorld(demand=0)
    blocker = world.spawn('U', movement='left')
    car = world.spawn('U', movement='left', lane='middle')
    car.distance, car.change_after = car.latest_change_start, CHANGE_START
    blocker.distance, blocker.speed = car.distance+15, 0
    for _ in range(80):
        world.step(.05, RED)
        assert car.changing_to is None
        assert car.lane == 'middle'
        assert_spacing(world)


def test_opposite_lane_requests_resolve_without_swapping_through_each_other():
    world = TrafficWorld(demand=0)
    one = world.spawn('U', movement='right', lane='outer')
    two = world.spawn('U', movement='left', lane='inner')
    middle = world.spawn('U', movement='left', lane='middle')
    for car in (one, two, middle):
        car.change_after, car.speed = CHANGE_START, 48
    for _ in range(1800):
        world.step(.05, {**RED, 'U': 'green'})
        assert_spacing(world)
        assert all(not v.changing_to or v.distance <= CHANGE_END+3 for v in world.vehicles)
    assert world.completed == 3


def test_two_changes_starting_at_last_preparation_point_still_finish_before_fork():
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='right', lane='outer')
    car.distance = car.change_after = car.latest_change_start
    for _ in range(400):
        world.step(.05, RED)
    assert car.changes == 2 and car.route.movement == 'right'
    assert car.lane == 'inner' and not car.changing_to
    assert not car.committed


def test_missed_gap_resolves_upstream_without_teleporting_or_cutting_in():
    world = TrafficWorld(demand=0)
    blocker = world.spawn('U', movement='left')
    car = world.spawn('U', movement='left', lane='middle')
    car.distance = car.change_after = car.latest_change_start
    blocker.distance, blocker.speed = car.distance+15, 0
    old = car.position()
    for _ in range(410):
        world.step(.05, RED)
        assert_spacing(world)
        assert math.dist(car.position()[:2], old[:2]) <= 3
        old = car.position()
    assert car.route.movement == 'straight'
    assert car.lane == 'middle' and car.changes == 0
    assert car.distance == pytest.approx(car.route.gate-VEHICLE_LENGTH/2)
    assert car.stop_reason == 'signal'


@pytest.mark.parametrize('direction', DIRECTIONS)
@pytest.mark.parametrize('kind', ['ambulance', 'fire_engine'])
def test_emergency_enters_at_rear_and_waits_for_space(direction, kind):
    world = TrafficWorld(demand=0)
    evp = world.spawn(direction, kind)
    assert evp.distance == 0
    assert evp.position()[:2] == rotate((470, START), DIRECTIONS.index(direction))
    assert evp.route.gate-evp.distance == 657
    assert world.spawn(direction, kind) is None
    for _ in range(40):
        world.step(.05, RED)
    assert world.spawn(direction, kind)
    assert_spacing(world)


def test_rear_entries_still_rank_ambulance_then_live_distance_and_recover():
    experiment = Experiment(load_config())
    experiment.world.demand = dict.fromkeys(DIRECTIONS, 0)
    first = experiment.world.spawn('U', 'ambulance')
    fire = experiment.world.spawn('B', 'fire_engine')
    for _ in range(50):
        experiment.tick(.1)
    later = experiment.world.spawn('T', 'ambulance')
    assert [v.id for v in experiment.world.candidates()] == [first.id, later.id, fire.id]
    for _ in range(1300):
        experiment.tick(.1)
        assert_spacing(experiment.world)
    assert experiment.world.completed == 3
    assert not experiment.emergency
    TrafficView.model_validate(experiment.snapshot('SIGAP-KIRCON-01'))


@pytest.mark.parametrize('seed', [7, 42, 913])
def test_random_flow_is_collision_free_varied_and_drains(seed):
    exp = Experiment(load_config(), seed=seed)
    exp.world.demand = dict.fromkeys(DIRECTIONS, 18)
    lanes, turns, changing = set(), set(), set()
    for tick in range(4200):
        if tick == 1800:
            exp.world.demand = dict.fromkeys(DIRECTIONS, 0)
        exp.tick(.1)
        for car in exp.world.vehicles:
            lanes.add(car.lane)
            turns.add(car.route.movement)
            if car.changing_to:
                changing.add((car.lane, car.changing_to))
                assert car.distance <= CHANGE_END+5
        if tick % 10 == 0:
            assert_spacing(exp.world)
    assert lanes == set(LANES) and turns == set(MOVEMENT_LANE)
    assert {('outer', 'middle'), ('middle', 'inner'), ('inner', 'middle'), ('middle', 'outer')} <= changing
    assert exp.world.completed > 80
    assert not exp.world.vehicles
