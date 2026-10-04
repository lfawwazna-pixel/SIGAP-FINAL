import asyncio

from atcs_simulator.app.runtime import AtcsRuntime
from contracts.configuration import load_config


def test_background_loop_ticks_without_any_http_requests(clock):
    async def scenario():
        runtime = AtcsRuntime(load_config(), clock=clock, tick_seconds=.01)
        await runtime.start()
        try:
            await asyncio.sleep(.02)
            clock.advance(2)
            # No call to status or HTTP is needed to move the controller.
            await asyncio.sleep(.03)
            assert runtime.engine.phase == "green"
            assert runtime.engine.active_approach == "U"
            clock.advance(85)
            await asyncio.sleep(.03)
            assert runtime.engine.phase == "yellow"
        finally:
            await runtime.stop()
        assert runtime.engine.state == "stopped" and runtime.task is None
    asyncio.run(scenario())


def test_stale_runtime_does_not_report_old_signal_as_current(clock):
    async def scenario():
        runtime = AtcsRuntime(load_config(), clock=clock, tick_seconds=.01)
        await runtime.start()
        try:
            await asyncio.sleep(.02)
            clock.advance(2)
            stale = runtime.status()
            assert stale.availability == "unavailable" and stale.engine_state == "stalled"
            assert stale.signals is None and stale.phase is None and stale.remaining_seconds is None
            assert runtime.engine.phase == "all_red"
            await asyncio.sleep(.03)
            assert runtime.status().availability == "available"
        finally:
            await runtime.stop()
    asyncio.run(scenario())


def test_failed_conflict_provider_holds_all_red(clock):
    class BrokenProvider:
        source = "provider"
        def read(self):
            raise OSError("unreadable input")

    async def scenario():
        runtime = AtcsRuntime(load_config(), clock=clock, conflict_provider=BrokenProvider(), tick_seconds=.01)
        await runtime.start()
        try:
            clock.advance(2)
            await asyncio.sleep(.03)
            report = runtime.status()
            assert report.phase == "all_red" and report.remaining_seconds is None
            assert report.conflict_area.state == "unknown"
            assert report.conflict_area.source == "provider"
        finally:
            await runtime.stop()
    asyncio.run(scenario())


def test_crashed_task_latches_fault_until_restart(clock):
    async def scenario():
        runtime = AtcsRuntime(load_config(), clock=clock, tick_seconds=.01)
        await runtime.start()
        def broken_tick(**kwargs):
            raise RuntimeError("controlled test fault")
        runtime.engine.tick = broken_tick
        try:
            await asyncio.sleep(.03)
            assert runtime.task.done()
            report = runtime.status()
            assert report.engine_state == "faulted" and report.availability == "unavailable"
            assert report.phase == "all_red" and report.remaining_seconds is None
            assert runtime.engine.events(at=clock.utcnow()).events[-1].event_type == "fault"
        finally:
            await runtime.stop()
    asyncio.run(scenario())
