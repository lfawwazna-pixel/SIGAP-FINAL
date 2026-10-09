"""Bounded, account-scoped experiments; mutation never contacts the ATCS service."""
import asyncio
from contextlib import suppress
import hmac
import re
import time
from fastapi import APIRouter, Depends, Request
from atcs_simulator.app.experiment import Experiment
from backend.app.auth import COOKIE_NAME, Principal, csrf_token, error, require_operator, require_origin
from contracts.traffic import SimulationCommand, TrafficView


class Experiments:
    def __init__(self, config):
        self.config = config
        self.items = {}
        self.task = None
        self.failure = None

    def get(self, key):
        if self.failure:
            raise error(503, 'SIMULATION_UNAVAILABLE', 'Mesin percobaan berhenti; layanan perlu diperiksa.')
        now = time.monotonic()
        self.items = {k: v for k, v in self.items.items() if now-v[1] < 3600}
        if key not in self.items:
            if len(self.items) >= 4:
                raise error(429, 'SIMULATION_CAPACITY', 'Empat ruang percobaan sedang digunakan. Coba lagi nanti.')
            self.items[key] = [Experiment(self.config), now]
        self.items[key][1] = now
        return self.items[key][0]

    async def start(self):
        self.task = asyncio.create_task(self.run(), name='isolated-experiments')

    async def stop(self):
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task

    async def advance_responsively(self, experiment, seconds):
        """Keep polling and operator commands responsive during dense catch-up.

        Every tick stays atomic on the event loop. Yield only between complete
        physics/controller ticks, so a pause/reset never cuts a safety check.
        """
        remaining = min(max(0, seconds), .5)*experiment.speed
        while remaining > .000001 and experiment.running:
            dt = min(.05, remaining)
            experiment.tick(dt)
            remaining -= dt
            await asyncio.sleep(0)

    async def run(self):
        last = time.monotonic()
        try:
            while True:
                now = time.monotonic()
                self.items = {k: v for k, v in self.items.items() if now-v[1] < 3600}
                for experiment, _ in list(self.items.values()):
                    await self.advance_responsively(experiment, now-last)
                last = now
                await asyncio.sleep(.05)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = type(exc).__name__
            for experiment, _ in self.items.values():
                experiment.running = False

    def command(self, key, command):
        experiment = self.get(key)
        if str(command.expected_run_id) != experiment.run_id:
            raise error(409, 'SIMULATION_CHANGED', 'Percobaan sudah direset. Muat keadaan terbaru sebelum memberi perintah.')
        if command.action == 'reset':
            # A responsive catch-up may still hold this old instance. Stop it
            # before replacing the account's world with the fresh paused one.
            experiment.running = False
            fresh = Experiment(self.config, experiment.seed)
            fresh.speed, fresh.strategy = experiment.speed, experiment.strategy
            fresh.world.demand = dict(experiment.world.demand)
            fresh.world.blocked_exit = experiment.world.blocked_exit
            self.items[key][0] = experiment = fresh
        elif command.action == 'start':
            experiment.running = True
        elif command.action == 'pause':
            experiment.running = False
        elif command.action == 'configure':
            if command.speed is not None:
                experiment.speed = command.speed
            if command.strategy is not None:
                experiment.strategy = command.strategy
                experiment.world.record('Strategi percobaan dipilih: '+command.strategy+'; berlaku pada pemilihan fase berikutnya.')
            if command.demand is not None:
                experiment.world.demand = dict(command.demand)
            if command.blocked_exit is not None:
                experiment.world.blocked_exit = None if command.blocked_exit == 'none' else command.blocked_exit
        elif command.action == 'spawn':
            vehicle = experiment.world.spawn(command.direction, command.kind)
            if vehicle is None:
                raise error(409, 'SPAWN_BLOCKED', 'Ujung masuk pendekat sedang penuh. Tunggu ruang aman lalu coba kembali.')
        return experiment


router = APIRouter(prefix='/api/simulation', tags=['Percobaan terpisah'])


@router.get('', response_model=TrafficView)
async def snapshot(request: Request, principal: Principal = Depends(require_operator)):
    manager = request.app.state.experiments
    return manager.get(principal.operator.id).snapshot(manager.config.intersection_id)


@router.post('/commands', response_model=TrafficView, dependencies=[Depends(require_origin)])
async def command(payload: SimulationCommand, request: Request, principal: Principal = Depends(require_operator)):
    supplied = request.headers.get('x-csrf-token', '')
    expected = csrf_token(request.cookies.get(COOKIE_NAME, ''))
    if not re.fullmatch(r'[a-f0-9]{64}', supplied) or not hmac.compare_digest(expected, supplied):
        raise error(403, 'CSRF_REJECTED', 'Sesi halaman berubah. Muat ulang sebelum memberi perintah.')
    manager = request.app.state.experiments
    experiment = manager.command(principal.operator.id, payload)
    return experiment.snapshot(manager.config.intersection_id)
