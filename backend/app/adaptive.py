"""Autonomous decision sender; observing a page never starts/stops control."""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from typing import Literal
from adaptive.policy import AdaptivePolicy
from backend.app.auth import require_operator, error
from backend.app.mutations import require_mutation
from contracts.adaptive import AdaptiveStatus, MeasurementBatch
from contracts.control import ControlCommand, CommandReceipt, ControlStatus
from contracts.models import Contract


class AdaptiveSender:
    def __init__(self, settings, intersection):
        self.enabled = settings.sigap_adaptive_synthetic
        self.headers = {'Authorization': 'Bearer '+settings.sigap_control_api_key.get_secret_value()}
        self.intersection = intersection
        self.sender = uuid4()
        self.run_id = None
        self.policy = AdaptivePolicy()
        self.started = time.monotonic()
        self.sequences = dict(observe=0, heartbeat=0, plan=0)
        self.batch = self.frozen = self.preview = None
        self.last_measurement = None
        self.fault = 'none'
        self.message = 'Data buatan belum diaktifkan pada layanan ini.'
        self.state = 'disabled'
        self.decisions = []
        self.applied = None
        self.task = None

    async def start(self, client):
        self.client = client
        if self.enabled:
            self.task = asyncio.create_task(self.run(), name='sigap-adaptive-synthetic')

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def command(self, status, action, **fields):
        at = datetime.now(timezone.utc)
        self.sequences[action] += 1
        cmd = ControlCommand(request_id=uuid4(), atcs_run_id=status.atcs_run_id, sender_id=self.sender,
            action=action, sequence=self.sequences[action], issued_at=at, expires_at=at+timedelta(seconds=3), **fields)
        r = await self.client.post('/control/commands', headers=self.headers, json=cmd.model_dump(mode='json', exclude_none=True))
        if r.status_code not in (200, 409):
            r.raise_for_status()
        receipt = CommandReceipt.model_validate(r.json())
        if receipt.request_id != cmd.request_id or receipt.atcs_run_id != status.atcs_run_id:
            raise ValueError('Tanda terima tidak cocok.')
        return receipt

    async def cycle(self):
        if self.fault == 'sender_stopped':
            self.state, self.message = 'unavailable', 'Uji pengirim berhenti: heartbeat dan pengamatan dihentikan.'
            self.batch = self.preview = None
            return
        r = await self.client.get('/control'); r.raise_for_status()
        status = ControlStatus.model_validate(r.json())
        if not status.available or not status.allow_test_source or status.intersection_id != self.intersection:
            raise ValueError('ATCS belum mengizinkan data buatan atau statusnya tidak tersedia.')
        if status.atcs_run_id != self.run_id:
            self.run_id = status.atcs_run_id
            self.policy = AdaptivePolicy()
            self.policy.config.minimum_green = status.policy.minimum_green_seconds
            self.policy.config.maximum_green = status.policy.maximum_green_seconds
            self.policy.config.data_timeout = status.policy.data_timeout_seconds
            self.started = time.monotonic()
            self.applied = None
            self.frozen = None
            self.last_measurement = None
            self.decisions = []
        r = await self.client.get('/measurements', headers=self.headers); r.raise_for_status()
        batch = MeasurementBatch.model_validate(r.json())
        if batch.source != 'synthetic' or batch.source_session != self.run_id or batch.intersection_id != self.intersection:
            raise ValueError('Identitas sumber pengukuran tidak cocok.')
        if self.last_measurement is not None:
            if batch.sequence < self.last_measurement.sequence:
                raise ValueError('Urutan pengukuran mundur.')
            if batch.sequence == self.last_measurement.sequence:
                # A repeated frame cannot become fresh merely by changing its timestamp.
                batch = self.last_measurement.model_copy(deep=True)
        self.last_measurement = batch.model_copy(deep=True)
        if self.fault == 'frozen_data':
            self.frozen = self.frozen or batch
            batch = self.frozen.model_copy(deep=True)
        else:
            self.frozen = None
        if self.fault == 'invalid_data':
            batch.approaches['U'].usable = False
        self.batch = batch
        receipt = await self.command(status, 'observe', source='integration_test', observations={d: dict(
            observed_at=v.observed_at, usable=v.usable) for d,v in batch.approaches.items()})
        if receipt.outcome == 'rejected':
            raise ValueError(receipt.message)
        r = await self.client.get('/control'); r.raise_for_status()
        status = ControlStatus.model_validate(r.json())
        now, at = time.monotonic()-self.started, datetime.now(timezone.utc)
        if status.active_request_id and status.active_request_id != self.applied:
            decision = next((d for d in self.decisions if d.request_id == status.active_request_id), None)
            if decision:
                decision.outcome = 'applied'
                self.policy.served(decision.approach, now)
            self.applied = status.active_request_id
        for decision in self.decisions:
            if decision.outcome == 'accepted' and decision.request_id not in (status.active_request_id, status.pending_request_id):
                decision.outcome = 'cancelled'
        self.preview = self.policy.choose(batch, now, at)
        self.state = 'active' if status.state == 'adaptive' and status.sender_id == self.sender else 'ready' if status.ready else 'unavailable'
        self.message = 'Adaptif menggunakan data buatan; bukan deteksi video.' if status.ready else status.readiness_reason
        if status.sender_id != self.sender or not status.session_id:
            return  # Acquisition always requires an explicit operator action.
        await self.command(status, 'heartbeat', session_id=status.session_id)
        if not status.ready or self.preview.approach is None or status.pending_request_id:
            return
        r = await self.client.get('/status'); r.raise_for_status()
        phase = r.json()
        # Decide near the next boundary, not a whole green phase in advance.
        if status.state == 'adaptive' and phase['phase'] == 'green' and phase['remaining_seconds'] > 1:
            return
        decision = self.preview.model_copy(deep=True)
        receipt = await self.command(status, 'plan', session_id=status.session_id, approach=decision.approach,
            green_seconds=decision.green_seconds,
            plan_valid_until=at+timedelta(seconds=status.policy.maximum_plan_horizon_seconds))
        decision.request_id, decision.outcome = receipt.request_id, receipt.outcome
        self.decisions.append(decision)
        self.decisions = self.decisions[-100:]

    async def run(self):
        while True:
            try:
                await self.cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Do not manufacture fresh measurements on errors. ATCS owns the timeout.
                self.state, self.message = 'unavailable', 'Pengukuran atau komunikasi adaptif terputus. ATCS memantau fallback.'
                self.batch = self.preview = None
            await asyncio.sleep(.5)

    def snapshot(self):
        return AdaptiveStatus(enabled=self.enabled, source='synthetic', fault=self.fault, status=self.state,
            message=self.message, policy=self.policy.config, measurements=self.batch,
            decisions=([self.preview] if self.preview else [])+list(reversed(self.decisions)))


class FaultInput(Contract):
    fault: Literal['none', 'frozen_data', 'invalid_data', 'sender_stopped']


router = APIRouter(prefix='/api/adaptive', tags=['Adaptif data buatan'])

@router.get('', response_model=AdaptiveStatus, dependencies=[Depends(require_operator)])
async def status(request: Request):
    return request.app.state.adaptive.snapshot()

@router.post('/fault', response_model=AdaptiveStatus, dependencies=[Depends(require_mutation)])
async def fault(payload: FaultInput, request: Request):
    sender = request.app.state.adaptive
    if not sender.enabled:
        raise error(409, 'SYNTHETIC_DISABLED', 'Uji data buatan belum diaktifkan.')
    sender.fault = payload.fault
    if payload.fault != 'frozen_data':
        sender.frozen = None
    return sender.snapshot()
