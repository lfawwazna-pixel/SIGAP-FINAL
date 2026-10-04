import math

import pytest
from pydantic import ValidationError

from atcs_simulator.app.engine import FixedTimeEngine
from contracts.configuration import load_config
from contracts.models import AtcsStatus, ConflictArea, IntersectionConfig


def observation(clock, state="clear"):
    return ConflictArea(state=state, source="provider", checked_at=clock.utcnow())


def make_engine(clock, **kwargs):
    return FixedTimeEngine(load_config(), now=clock.monotonic(), at=clock.utcnow(),
                           conflict=observation(clock), **kwargs)


def tick(engine, clock, seconds, state="clear"):
    clock.advance(seconds)
    engine.tick(now=clock.monotonic(), at=clock.utcnow(), conflict=observation(clock, state))
    return engine.snapshot(clock.utcnow())


def test_full_baseline_cycle_and_exclusive_signals(clock):
    engine = make_engine(clock)
    initial = engine.snapshot(clock.utcnow())
    assert initial.phase == "all_red" and initial.remaining_seconds == 2
    assert initial.simulation_time_seconds == 0
    expected = [
        (2, "green", "U", 85), (87, "yellow", "U", 3), (90, "all_red", None, 2),
        (92, "green", "T", 150), (242, "yellow", "T", 3), (245, "all_red", None, 2),
        (247, "green", "S", 95), (342, "yellow", "S", 3), (345, "all_red", None, 2),
        (347, "green", "B", 100), (447, "yellow", "B", 3), (450, "all_red", None, 2),
        (452, "green", "U", 85),
    ]
    for elapsed, phase, approach, remaining in expected:
        report = tick(engine, clock, elapsed - clock.elapsed)
        assert (report.phase, report.active_approach, report.remaining_seconds) == (phase, approach, remaining)
        assert report.controller == "ATCS" and report.mode == "fixed_time"
        assert sum(value != "red" for value in report.signals.values()) == (approach is not None)
        if approach:
            assert report.signals[approach] == phase
    events = engine.events(at=clock.utcnow()).events
    assert [e.simulation_time_seconds for e in events if e.phase == "green" and e.active_approach == "U"] == [2, 452]
    assert all(e.reason and e.run_id == engine.run_id for e in events)
    assert [e.sequence_number for e in events] == list(range(1, len(events) + 1))


def test_config_is_only_source_of_timing(clock):
    data = load_config().model_dump()
    data["fixed_time"]["green_seconds"]["U"] = 7
    data["fixed_time"]["nominal_cycle_seconds"] = 372
    config = IntersectionConfig.model_validate(data)
    engine = FixedTimeEngine(config, now=clock.monotonic(), at=clock.utcnow(), conflict=observation(clock))
    assert tick(engine, clock, 2).remaining_seconds == 7
    assert tick(engine, clock, 7).phase == "yellow"


@pytest.mark.parametrize("state", ["occupied", "unknown"])
def test_all_red_waits_for_clearance_without_invented_countdown(clock, state):
    engine = make_engine(clock)
    held = tick(engine, clock, 2, state)
    assert held.phase == "all_red" and held.clearance_state == "waiting_conflict"
    assert held.remaining_seconds is None
    assert set(held.signals.values()) == {"red"}
    for _ in range(5):
        assert tick(engine, clock, 20, state).phase == "all_red"
    records = engine.events(at=clock.utcnow()).events
    assert sum(e.event_type == "clearance_held" for e in records) == 1
    released = tick(engine, clock, 1, "clear")
    assert released.phase == "green" and released.active_approach == "U"
    assert released.remaining_seconds == 85
    assert any(e.event_type == "clearance_released" for e in engine.events(at=clock.utcnow()).events)


def test_conflict_after_yellow_delays_next_approach_not_cycle_order(clock):
    engine = make_engine(clock)
    tick(engine, clock, 2)
    tick(engine, clock, 85)
    tick(engine, clock, 3, "occupied")
    assert tick(engine, clock, 1, "clear").phase == "all_red"
    assert tick(engine, clock, 1, "occupied").remaining_seconds is None
    assert tick(engine, clock, 10, "clear").active_approach == "T"


def test_delayed_tick_does_not_skip_yellow_or_all_red(clock):
    engine = make_engine(clock)
    tick(engine, clock, 2)
    report = tick(engine, clock, 1000)
    assert report.phase == "yellow" and report.remaining_seconds == 3
    assert tick(engine, clock, 2.99).phase == "yellow"
    assert tick(engine, clock, .01).phase == "all_red"
    assert tick(engine, clock, 1.99).phase == "all_red"
    assert tick(engine, clock, .01).active_approach == "T"


def test_reading_status_does_not_tick_or_generate_events(clock):
    engine = make_engine(clock)
    before = engine.snapshot(clock.utcnow())
    clock.advance(100)
    for _ in range(5):
        report = engine.snapshot(clock.utcnow())
        assert report.phase == before.phase and report.sequence_number == before.sequence_number
        assert report.updated_at == before.updated_at
    assert engine.events(at=clock.utcnow()).latest_sequence == 1


def test_wall_clock_correction_does_not_change_phase_duration(clock):
    engine = make_engine(clock)
    tick(engine, clock, 2)
    clock.wall_offset -= 3600
    assert tick(engine, clock, 1).remaining_seconds == 84
    clock.wall_offset += 7200
    assert tick(engine, clock, 1).remaining_seconds == 83


@pytest.mark.parametrize("invalid", [-1, math.nan, math.inf])
def test_invalid_monotonic_clock_is_rejected(clock, invalid):
    engine = make_engine(clock)
    with pytest.raises(ValueError):
        engine.tick(now=invalid, at=clock.utcnow(), conflict=observation(clock))


def test_bounded_history_cursor_and_new_session(clock):
    engine = make_engine(clock, event_capacity=3)
    tick(engine, clock, 2)
    tick(engine, clock, 85)
    tick(engine, clock, 3)
    first = engine.events(at=clock.utcnow(), limit=2)
    assert first.history_truncated and first.has_more
    assert [e.sequence_number for e in first.events] == [2, 3]
    second = engine.events(at=clock.utcnow(), after=first.next_after, run_id=first.run_id)
    assert [e.sequence_number for e in second.events] == [4] and not second.has_more
    assert not second.history_truncated
    assert engine.events(at=clock.utcnow(), after=4).events == []
    with pytest.raises(ValueError, match="CURSOR_AHEAD"):
        engine.events(at=clock.utcnow(), after=5)
    restarted = make_engine(clock)
    page = restarted.events(at=clock.utcnow(), after=4, run_id=engine.run_id)
    assert page.run_changed and page.next_after == 1
    assert restarted.snapshot(clock.utcnow()).phase == "all_red"
    assert restarted.snapshot(clock.utcnow()).simulation_time_seconds == 0


@pytest.mark.parametrize("fault", [False, True])
def test_end_is_terminal_and_reports_unavailable(clock, fault):
    engine = make_engine(clock)
    tick(engine, clock, 2)
    engine.end(at=clock.utcnow(), fault=fault)
    report = tick(engine, clock, 1000)
    assert report.availability == "unavailable" and report.remaining_seconds is None
    assert report.engine_state == ("faulted" if fault else "stopped")
    assert set(report.signals.values()) == {"red"}


@pytest.mark.parametrize("mutation", [
    lambda d: d["signals"].update(U="green", T="green"),
    lambda d: d.update(remaining_seconds=None),
    lambda d: d.update(remaining_seconds=-1),
    lambda d: d.update(remaining_seconds=float("inf")),
    lambda d: d.update(active_approach=None),
])
def test_contract_rejects_conflicting_or_incomplete_running_status(clock, mutation):
    engine = make_engine(clock)
    data = tick(engine, clock, 2).model_dump()
    mutation(data)
    with pytest.raises(ValidationError):
        AtcsStatus.model_validate(data)
