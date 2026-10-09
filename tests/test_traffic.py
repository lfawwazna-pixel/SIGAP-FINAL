import math
from itertools import combinations
import pytest
from atcs_simulator.app.traffic import DIRECTIONS, ROUTES, TrafficWorld, VEHICLE_LENGTH, GAP, bodies_overlap
from atcs_simulator.app.experiment import Experiment
from contracts.configuration import load_config
from contracts.traffic import TrafficView

RED = dict.fromkeys(DIRECTIONS, 'red')


def advance(world, seconds, signals=RED):
    for _ in range(round(seconds/.05)):
        world.step(.05, signals)


def run(experiment, seconds):
    for _ in range(round(seconds/.05)):
        experiment.tick(.05)


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_routes_start_upstream_and_left_destination_is_rotational(direction):
    i = DIRECTIONS.index(direction)
    routes = [r for r in ROUTES.values() if r.origin == direction]
    assert len(routes) == 3
    assert all(r.length > 900 for r in routes)
    assert next(r for r in routes if r.movement == 'left').destination == DIRECTIONS[(i+1)%4]
    assert all(math.dist(r.position(0)[:2], (400,400)) > 600 for r in routes)


def test_red_and_yellow_stop_at_front_bumper_then_green_releases():
    world = TrafficWorld(demand=0)
    car = world.spawn('U', movement='straight', lane='inner')
    advance(world, 20)
    assert car.distance == pytest.approx(car.route.gate-VEHICLE_LENGTH/2)
    assert not car.committed and world.read() == 'clear'
    advance(world, 2, {**RED, 'U': 'yellow'})
    assert not car.committed
    advance(world, 1, {**RED, 'U': 'green'})
    assert car.committed and world.read() == 'occupied'
    advance(world, 20)
    assert world.completed == 1 and world.read() == 'clear'


def test_left_turn_finishes_while_all_signals_red():
    world = TrafficWorld(demand=0)
    world.spawn('U', movement='left')
    advance(world, 40)
    assert world.completed == 1


@pytest.mark.parametrize('direction', DIRECTIONS)
def test_left_queue_does_not_yield_to_its_own_followers(direction):
    world = TrafficWorld(demand=0)
    cars = []
    for index in range(5):
        car = world.spawn(direction, movement='left')
        car.distance = car.route.gate-VEHICLE_LENGTH/2-index*40
        cars.append(car)
    # Previously the first and second cars waited for each other forever.
    for _ in range(800):
        world.step(.05, RED)
        for one, two in combinations(world.vehicles, 2):
            assert math.dist(one.position()[:2], two.position()[:2]) >= VEHICLE_LENGTH+GAP-.001
    assert world.completed == len(cars)
    assert not world.vehicles


def test_slip_queue_uses_separate_exit_lane_and_drains_beside_main_traffic():
    world = TrafficWorld(demand=0)
    leader = world.spawn('U', movement='left')
    leader.distance = leader.route.gate-VEHICLE_LENGTH/2
    follower = world.spawn('U', movement='left')
    follower.distance = leader.distance-40
    main = world.spawn('B', movement='straight', lane='middle')
    main.distance, main.committed = 1080, True
    before = leader.distance
    world.step(.05, RED)
    assert leader.distance > before
    assert leader.route.exit_lane != main.route.exit_lane
    advance(world, 40)
    assert world.completed == 3


def test_four_slip_queues_keep_spacing_and_recover_from_a_blocked_exit():
    world = TrafficWorld(demand=0)
    world.blocked_exit = 'T'
    for direction in DIRECTIONS:
        for index in range(4):
            car = world.spawn(direction, movement='left')
            car.distance = car.route.gate-VEHICLE_LENGTH/2-index*40
    advance(world, 35)
    assert world.completed == 12
    assert len(world.vehicles) == 4 and all(v.route.origin == 'U' for v in world.vehicles)
    world.blocked_exit = None
    advance(world, 35)
    assert world.completed == 16


def test_left_slip_cannot_run_into_a_stopped_outgoing_leader():
    world = TrafficWorld(demand=0)
    slip = world.spawn('U', movement='left')
    slip.distance = slip.route.exit_start+100
    slip.committed = True
    other = world.spawn('U', movement='left')
    other.distance = slip.distance+VEHICLE_LENGTH+GAP
    other.committed = True
    other.speed = 0
    before = slip.distance
    world.step(.05, RED)
    assert slip.distance == before
    other.speed = 48
    advance(world, 25)
    assert world.completed == 2


def test_blocked_exit_prevents_new_entry_then_unblocking_releases():
    world = TrafficWorld(demand=0)
    world.blocked_exit = 'S'
    car = world.spawn('U', movement='straight', lane='inner')
    advance(world, 20, {**RED, 'U': 'green'})
    assert not car.committed
    world.blocked_exit = None
    advance(world, 23, {**RED, 'U': 'green'})
    assert world.completed == 1


def test_spawn_refuses_or_moves_upstream_instead_of_overlapping():
    world = TrafficWorld(demand=0)
    first = world.spawn('U', 'ambulance', 60, lane='inner')
    second = world.spawn('U', 'ambulance', 60, lane='inner')
    assert first.distance-second.distance >= VEHICLE_LENGTH+GAP
    for _ in range(30): world.spawn('U', 'ambulance', 60, lane='inner')
    assert world.refused > 0


def test_ambulance_rank_precedes_closer_fire_engine_and_same_type_distance():
    world = TrafficWorld(demand=0)
    fire = world.spawn('U', 'fire_engine', 45, lane='inner')
    far = world.spawn('T', 'ambulance', 350, lane='inner')
    near = world.spawn('S', 'ambulance', 60, lane='inner')
    assert [v.id for v in world.candidates()] == [near.id, far.id, fire.id]


def test_ties_use_creation_order_and_served_requests_leave_queue():
    world = TrafficWorld(demand=0)
    first = world.spawn('U', 'ambulance', 100, lane='inner')
    second = world.spawn('T', 'ambulance', 100, lane='inner')
    assert world.candidates() == [first, second]
    first.served = True
    assert world.candidates() == [second]


def test_emergency_service_then_adaptive_recovery_with_full_clearance():
    experiment = Experiment(load_config())
    experiment.world.demand = dict.fromkeys(DIRECTIONS, 0)
    fire = experiment.world.spawn('T', 'fire_engine', 60, lane='inner')
    ambulance = experiment.world.spawn('U', 'ambulance', 100, lane='inner')
    run(experiment, 2.1)
    assert experiment.target == ambulance.id and experiment.active == 'U'
    assert experiment.emergency
    run(experiment, 45)
    assert not experiment.emergency and experiment.target is None
    assert experiment.world.completed == 2
    events = experiment.world.events
    assert next(i for i,e in enumerate(events) if f'EVP #{ambulance.id}:' in e['message']) < next(i for i,e in enumerate(events) if f'EVP #{fire.id}:' in e['message'])
    assert any('kembali ke strategi adaptive' in e['message'] for e in events)
    TrafficView.model_validate(experiment.snapshot('SIGAP-KIRCON-01'))


def test_new_ambulance_does_not_interrupt_target_already_granted_green():
    experiment = Experiment(load_config())
    experiment.world.demand = dict.fromkeys(DIRECTIONS, 0)
    fire = experiment.world.spawn('U', 'fire_engine', 350, lane='inner')
    run(experiment, 2.1)
    assert experiment.target == fire.id
    experiment.world.spawn('T', 'ambulance', 60, lane='inner')
    run(experiment, 1)
    assert experiment.target == fire.id and experiment.active == 'U'


def test_two_ambulances_select_the_closer_one_and_fixed_time_recovers():
    experiment = Experiment(load_config())
    experiment.strategy = 'fixed_time'
    experiment.world.demand = dict.fromkeys(DIRECTIONS, 0)
    far = experiment.world.spawn('U', 'ambulance', 350, lane='inner')
    near = experiment.world.spawn('T', 'ambulance', 60, lane='inner')
    run(experiment, 2.1)
    assert experiment.target == near.id and experiment.target != far.id
    run(experiment, 45)
    assert not experiment.emergency
    assert any('kembali ke strategi fixed_time' in e['message'] for e in experiment.world.events)


def test_preemption_keeps_yellow_and_all_red_minimum():
    experiment = Experiment(load_config())
    experiment.world.demand = dict.fromkeys(DIRECTIONS, 0)
    run(experiment, 2.1)
    assert experiment.phase == 'green'
    experiment.world.spawn('T', 'ambulance', 60, lane='inner')
    run(experiment, .05)
    assert experiment.phase == 'yellow'
    run(experiment, 2.9)
    assert experiment.phase == 'yellow'
    run(experiment, .2)
    assert experiment.phase == 'all_red'
    run(experiment, 1.8)
    assert experiment.phase == 'all_red'


def test_pause_speed_and_separate_worlds():
    a, b = Experiment(load_config()), Experiment(load_config())
    a.advance(.1)
    assert a.world.time == 0
    a.running, a.speed = True, 3
    a.advance(.1)
    assert a.world.time == pytest.approx(.3) and b.world.time == 0


def test_seed_replay_and_mixed_flow_has_spacing_and_progress():
    a, b = Experiment(load_config()), Experiment(load_config())
    completed = []
    for i in range(2400):
        a.tick(.05)
        b.tick(.05)
        if i % 20 == 0:
            for one, two in combinations(a.world.vehicles, 2):
                assert not bodies_overlap(one, one.position(), two, two.position(), safety=False)
            assert a.world.snapshot() == b.world.snapshot()
        if (i+1) % 600 == 0:
            completed.append(a.world.completed)
    assert completed[-1] > completed[-2] > completed[-3] > 0
    assert a.world.read() in ('clear', 'occupied')


def test_conflicting_approach_cannot_enter_occupied_center():
    world = TrafficWorld(demand=0)
    committed = world.spawn('U', movement='straight', lane='inner')
    committed.distance, committed.committed = 600, True
    car = world.spawn('T', 'ambulance', 14, lane='inner')
    advance(world, .05, {**RED, 'T': 'green'})
    assert not car.committed
