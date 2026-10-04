import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import logging
import time
from typing import Literal, Protocol

from atcs_simulator.app.control import ManagedEngine
from atcs_simulator.app.control_settings import ControlSettings
from atcs_simulator.app.traffic import TrafficWorld
from contracts.models import AtcsStatus, ConflictArea, IntersectionConfig

logger = logging.getLogger(__name__)


class Clock(Protocol):
    def monotonic(self) -> float: ...
    def utcnow(self) -> datetime: ...


class SystemClock:
    def monotonic(self):
        return time.monotonic()

    def utcnow(self):
        return datetime.now(timezone.utc)


class ConflictProvider(Protocol):
    """Read the current local simulation state; must not block or perform network I/O."""
    source: Literal["assumed_clear", "provider"]

    def read(self) -> Literal["clear", "occupied", "unknown"]: ...


class AssumedClear:
    source = "assumed_clear"

    def read(self):
        return "clear"


class AtcsRuntime:
    def __init__(self, config: IntersectionConfig, *, clock: Clock | None = None,
                 conflict_provider: ConflictProvider | None = None, tick_seconds: float = 0.1,
                 event_capacity: int = 1000, control_settings=None, control_policy=None):
        if not 0.01 <= tick_seconds <= 0.5:
            raise ValueError("Tick interval must be 0.01–0.5 seconds")
        self.config = config
        self.clock = clock or SystemClock()
        self.traffic = TrafficWorld()
        self.provider = conflict_provider or self.traffic
        self.tick_seconds = tick_seconds
        self.event_capacity = event_capacity
        self.control_settings = control_settings or ControlSettings()
        self.control_policy = control_policy
        self.engine: ManagedEngine | None = None
        self.task: asyncio.Task | None = None
        self.traffic_at = self.clock.monotonic()

    def _conflict(self, at):
        try:
            return ConflictArea(state=self.provider.read(), source=self.provider.source, checked_at=at)
        except Exception:
            # Unreadable input is unknown, never assumed clear.
            return ConflictArea(state="unknown", source="provider", checked_at=at)

    async def start(self):
        if self.task is not None:
            raise RuntimeError("Runtime already started")
        at = self.clock.utcnow()
        self.engine = ManagedEngine(self.config, now=self.clock.monotonic(), at=at,
                                      control_settings=self.control_settings, policy=self.control_policy,
                                      conflict=self._conflict(at), event_capacity=self.event_capacity)
        self.task = asyncio.create_task(self._run(), name="atcs-fixed-time")

    async def _run(self):
        try:
            while self.engine.state == "running":
                at = self.clock.utcnow()
                now = self.clock.monotonic()
                elapsed = min(.5, max(0, now-self.traffic_at))
                signals = self.engine.snapshot(at).signals
                while elapsed > .000001:
                    dt = min(.05, elapsed)
                    self.traffic.step(dt, signals)
                    elapsed -= dt
                self.traffic_at = now
                self.engine.tick(now=self.clock.monotonic(), at=at, conflict=self._conflict(at))
                delay = self.tick_seconds
                if self.engine.deadline is not None:
                    until_transition = self.engine.deadline - self.clock.monotonic()
                    if until_transition > 0:
                        delay = min(delay, until_transition)
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            # Cancellation outside normal shutdown is still an unavailable engine.
            self.engine.end(at=self.clock.utcnow())
            raise
        except Exception:
            self.engine.end(at=self.clock.utcnow(), fault=True)
            logger.exception("ATCS phase engine stopped after an internal error")

    async def stop(self):
        if self.task is None:
            return
        self.engine.end(at=self.clock.utcnow())
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task
        self.task = None

    def status(self) -> AtcsStatus:
        if self.engine is None:
            raise RuntimeError("ATCS lifespan has not started")
        report = self.engine.snapshot(self.clock.utcnow())
        if self.engine.state == "running" and (
            self.task is None or self.task.done()
            or self.clock.monotonic() - self.engine.last_tick > max(1.0, 5 * self.tick_seconds)
        ):
            # Reads do not advance or revive a stalled control loop.
            return AtcsStatus.model_validate({**report.model_dump(),
                "availability": "unavailable", "engine_state": "stalled", "phase": None,
                "signals": None, "active_approach": None, "remaining_seconds": None,
                "clearance_state": None, "reason": "Pembaruan mesin fase terhenti; keadaan lampu tidak dapat dipastikan."})
        return report

    def traffic_view(self):
        status = self.status()
        available = status.availability == 'available'
        return {
            'intersection_id': self.config.intersection_id, 'source': 'atcs_synthetic',
            'run_id': status.run_id, 'observed_at': status.observed_at, 'available': available,
            'time_seconds': self.traffic.time, 'running': available, 'speed': 1,
            'strategy': 'adaptive' if status.mode == 'adaptive' else 'fixed_time',
            'phase': status.phase, 'active_approach': status.active_approach, 'signals': status.signals,
            'remaining_seconds': status.remaining_seconds, 'emergency': False, 'target_vehicle': None,
            'reason': 'Kendaraan sintetis mengikuti ATCS; bukan hasil pengamatan CCTV.',
            'demand': dict(self.traffic.demand), 'blocked_exit': None, 'events': [], 'evp_queue': [],
            **self.traffic.snapshot(),
        }

    def control_status(self):
        return self.engine.control.snapshot(self.clock.monotonic(), self.clock.utcnow(),
                                            self.status().availability == 'available')
