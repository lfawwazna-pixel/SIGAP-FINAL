"""Regressions from the operator's three screenshots, checked for liveness too."""
import math
from itertools import combinations

import pytest
from atcs_simulator.app.traffic import TrafficWorld, DIRECTIONS, CHANGE_START, CHANGE_END

RED = dict.fromkeys(DIRECTIONS, 'red')


def advance(world, seconds, direction='U'):
    for _ in range(round(seconds/.05)):
        world.step(.05, {**RED, direction: 'green'})
        for a, b in combinations(world.vehicles, 2):
            assert math.dist(a.position()[:2], b.position()[:2]) >= 33.999


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_side_by_side_opposite_requests_do_not_freeze(direction):
    world = TrafficWorld(demand=0)
    a = world.spawn(direction, movement='straight', lane='outer')
    b = world.spawn(direction, movement='left', lane='middle')
    for car in (a, b):
        car.distance = CHANGE_START
        car.change_after = CHANGE_START
        car.speed = 48
    advance(world, 12, direction)
    assert a.distance > CHANGE_END and b.distance > CHANGE_END
    assert not a.changing_to and not b.changing_to
    assert a.changes + b.changes >= 1
    advance(world, 35, direction)
    assert world.completed == 2


@pytest.mark.parametrize('blocker_lane', ['outer', 'middle'])
def test_does_not_start_diagonal_into_a_stopped_queue(blocker_lane):
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='left', lane='middle')
    car.distance, car.change_after = 120, CHANGE_START
    blocker = world.spawn('U', movement='left' if blocker_lane == 'outer' else 'straight')
    blocker.distance, blocker.speed = 205, 0
    for _ in range(120):
        world.step(.05, RED)
        # The old 55-unit check started a turn into this 85-unit dead end.
        if car.distance < blocker.distance+50:
            assert car.changing_to is None
        assert math.dist(car.position()[:2], blocker.position()[:2]) >= 33.999
    blocker.speed = 48
    advance(world, 50)
    assert world.completed == 2


def test_started_change_can_finish_even_when_its_leader_stops():
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='left', lane='middle')
    car.distance = car.change_after = 100
    leader = world.spawn('U', movement='left')
    leader.distance, leader.speed = 270, 0
    world.step(.05, RED)
    assert car.changing_to == 'outer'
    advance(world, 12)
    assert car.lane == 'outer' and car.changes == 1 and car.changing_to is None
    assert car.distance <= leader.distance-34+.001


def test_missing_gap_never_makes_a_free_lane_stop_at_the_deadline():
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='left', lane='middle')
    blocker = world.spawn('U', movement='left')
    car.distance = car.change_after = car.latest_change_start
    blocker.distance, blocker.speed = car.distance+15, 0
    advance(world, 2)
    assert car.distance > 340
    assert car.route.movement == 'straight' and not car.stopped
    assert not car.changing_to
    assert len(world.events) == 1


def test_nonoverlapping_changes_on_one_approach_can_proceed_together():
    world = TrafficWorld(demand=0)
    front = world.spawn('U', movement='left', lane='middle')
    front.distance = front.change_after = 315
    rear = world.spawn('U', movement='left', lane='middle')
    rear.distance = rear.change_after = 70
    world.step(.05, RED)
    assert front.changing_to == rear.changing_to == 'outer'
    advance(world, 12)
    assert front.changes == rear.changes == 1


def test_stopped_vehicle_reports_actionable_reason_and_clears_when_moving():
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='straight')
    car.distance = car.route.gate-13
    world.step(.05, RED)
    assert world.snapshot()['vehicles'][0]['stop_reason'] == 'signal'
    advance(world, 1)
    assert not car.stopped and car.stop_reason is None
