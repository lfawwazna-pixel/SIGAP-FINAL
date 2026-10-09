"""Autonomous decision sender; observing a page never starts/stops control."""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from typing import Literal
from adaptive.policy import AdaptivePolicy
from contracts.configuration import load_config
from backend.app.auth import require_operator, error
from backend.app.mutations import require_mutation
from contracts.adaptive import AdaptiveStatus, MeasurementBatch
from contracts.control import ControlCommand, CommandReceipt, ControlStatus
from contracts.models import Contract
from backend.app.measurements import VideoMeasurements
from backend.app.emergency import EmergencyCoordinator


class AdaptiveSender:
    def __init__(self, settings, intersection):
        self.video_mode = settings.sigap_yolo_enabled and settings.sigap_adaptive_video
        self.enabled = self.video_mode or settings.sigap_adaptive_synthetic
        self.video = None
        self.video_measurements = VideoMeasurements(intersection)
        self.emergency = EmergencyCoordinator(enabled=settings.sigap_evp_enabled)
        self.priority_session = None
        self.priority_sent = False
        self.emergency_serving = False
        self.control_owned = False
        self.auto_resume = False
        self.held = False
        self.lock = asyncio.Lock()
        self.headers = {'Authorization': 'Bearer '+settings.sigap_control_api_key.get_secret_value()}
        self.intersection = intersection
        self.sender = uuid4()
        self.run_id = None
        self.policy = AdaptivePolicy()
        self.policy.baseline = load_config(settings.sigap_config_path).fixed_time.green_seconds
        self.started = time.monotonic()
        self.sequences = dict(observe=0, heartbeat=0, plan=0, priority=0)
        self.batch = self.frozen = self.preview = None
        self.last_measurement = None
        self.fault = 'none'
        self.message = 'Data buatan belum diaktifkan pada layanan ini.'
        self.state = 'disabled'
        self.decisions = []
        self.applied = None
        self.task = None

    def observe_emergency_frame(self):
        # Consume every accepted tracking result; controller HTTP polling is slower
        # than the camera and must not discard fresh confirmation evidence.
        if self.video_mode:
            self.emergency.update(self.video, control_active=bool(self.control_owned
                and not self.held and self.fault == 'none'))

    def suspend_emergency(self):
        self.control_owned = False
        self.priority_session = None
        self.priority_sent = self.emergency_serving = False
        self.emergency.suspend()
        if self.video is not None:
            self.video.vision.focus = False

    async def start(self, client):
        self.client = client
        if self.enabled:
            self.task = asyncio.create_task(self.run(), name='sigap-adaptive')

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def command(self, status, action, **fields):
        at = datetime.now(timezone.utc)
        if action in self.sequences:
            self.sequences[action] += 1
            fields['sequence'] = self.sequences[action]
        cmd = ControlCommand(request_id=uuid4(), atcs_run_id=status.atcs_run_id, sender_id=self.sender,
            action=action, issued_at=at, expires_at=at+timedelta(seconds=3), **fields)
        r = await self.client.post('/control/commands', headers=self.headers, json=cmd.model_dump(mode='json', include=cmd.model_fields_set))
        if r.status_code not in (200, 409):
            r.raise_for_status()
        receipt = CommandReceipt.model_validate(r.json())
        if receipt.request_id != cmd.request_id or receipt.atcs_run_id != status.atcs_run_id:
            raise ValueError('Tanda terima tidak cocok.')
        return receipt

    async def cycle(self):
        async with self.lock:
            await self._cycle()

    async def hold(self):
        async with self.lock:
            self.auto_resume, self.held = False, True
            self.suspend_emergency()
            # Stop renewing control even if the release cannot be delivered.
            # ATCS then expires the heartbeat independently.
            try:
                r = await self.client.get('/control'); r.raise_for_status()
                status = ControlStatus.model_validate(r.json())
                if status.sender_id == self.sender and status.session_id:
                    await self.command(status, 'release', session_id=status.session_id, expected_revision=status.revision)
            except Exception:
                self.state, self.message = 'unavailable', 'Pemulihan otomatis dibatalkan. ATCS memantau pelepasan kendali.'

    async def _cycle(self):
        if self.fault == 'sender_stopped':
            self.suspend_emergency()
            self.state, self.message = 'unavailable', 'Uji pengirim berhenti: heartbeat dan pengamatan dihentikan.'
            self.batch = self.preview = None
            if self.video is not None:
                self.video.vision.focus = False
            return
        r = await self.client.get('/control'); r.raise_for_status()
        status = ControlStatus.model_validate(r.json())
        if not status.available or (not self.video_mode and not status.allow_test_source) or status.intersection_id != self.intersection:
            raise ValueError('ATCS belum mengizinkan sumber atau statusnya tidak tersedia.')
        if status.atcs_run_id != self.run_id:
            self.run_id = status.atcs_run_id
            baseline = self.policy.baseline
            self.policy = AdaptivePolicy()
            self.policy.baseline = baseline
            self.policy.config.minimum_green = status.policy.minimum_green_seconds
            self.policy.config.maximum_green = status.policy.maximum_green_seconds if self.video_mode else min(60, status.policy.maximum_green_seconds)
            self.policy.config.data_timeout = status.policy.data_timeout_seconds
            self.started = time.monotonic()
            self.applied = None
            self.frozen = None
            self.last_measurement = None
            self.decisions = []
        if self.video_mode:
            batch = self.video_measurements.snapshot(self.video)
        else:
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
        receipt = await self.command(status, 'observe', source='cctv' if self.video_mode else 'integration_test', observations={d: dict(
            observed_at=v.observed_at, usable=v.usable) for d,v in batch.approaches.items()})
        if receipt.outcome == 'rejected':
            raise ValueError(receipt.message)
        r = await self.client.get('/control'); r.raise_for_status()
        status = ControlStatus.model_validate(r.json())
        self.control_owned = bool(status.state == 'adaptive' and status.controller == 'SIGAP'
            and status.session_id and status.sender_id == self.sender and not self.held and self.fault == 'none')
        if not self.control_owned:
            self.suspend_emergency()
        elif self.priority_session != status.session_id:
            # A newly acquired session must confirm fresh evidence of its own.
            self.emergency.suspend()
            self.priority_session, self.priority_sent = status.session_id, False
        now, at = time.monotonic()-self.started, datetime.now(timezone.utc)
        if status.active_request_id and status.active_request_id != self.applied:
            decision = next((d for d in self.decisions if d.request_id == status.active_request_id), None)
            if decision:
                decision.outcome = 'applied'
                self.policy.served(decision.approach, now, decision.green_seconds)
            self.applied = status.active_request_id
        for decision in self.decisions:
            if decision.outcome == 'accepted' and decision.request_id not in (status.active_request_id, status.pending_request_id):
                decision.outcome = 'cancelled'
        self.preview = self.policy.choose(batch, now, at)
        self.state = 'active' if status.state == 'adaptive' and status.sender_id == self.sender else 'ready' if status.ready else 'unavailable'
        self.message = ('SIGAP mengambil alih kendali berdasarkan YOLO + ByteTrack.' if self.state == 'active'
            else 'Empat pendekat siap; aktifkan kendali SIGAP.' if self.video_mode else 'Adaptif menggunakan data buatan; bukan deteksi video.') if status.ready else status.readiness_reason
        target = self.emergency.update(self.video, control_active=self.control_owned).target if self.video_mode else None
        self.emergency_serving = self.control_owned and status.emergency_serving
        if self.emergency.state == 'recovering' and not status.emergency and not status.emergency_serving and status.state == 'fixed_time':
            self.emergency.recovered()
        if self.video is not None:
            self.video.vision.focus = bool(target and self.control_owned)
        if self.held:
            return
        if self.video_mode and self.auto_resume and status.ready and status.state == 'fixed_time' and status.sender_id == self.sender:
            await self.command(status, 'activate', expected_revision=status.revision)
            return
        if status.sender_id != self.sender or not status.session_id:
            return  # First acquisition requires operator activation; video recovery may resume.
        await self.command(status, 'heartbeat', session_id=status.session_id)
        if self.video_mode and self.control_owned and (target is not None or self.priority_sent or status.emergency is not None):
            receipt = await self.command(status, 'priority', session_id=status.session_id, priority_target=target)
            if receipt.outcome == 'rejected':
                raise ValueError(receipt.message)
            self.priority_sent = target is not None
            if target is not None:
                self.message = 'Prioritas EVP terkonfirmasi; keputusan antrean ditangguhkan.'
                return
            r = await self.client.get('/control'); r.raise_for_status()
            status = ControlStatus.model_validate(r.json())
            self.emergency_serving = status.emergency_serving
        phase = None
        if self.emergency.state == 'recovering' and not status.emergency and not status.emergency_serving:
            r = await self.client.get('/status'); r.raise_for_status()
            phase = r.json()
            # A cleared target may still own the minimum green/yellow interval.
            if status.state == 'fixed_time' or phase['phase'] == 'all_red':
                self.emergency.recovered()
        if not status.ready or self.preview.approach is None or status.pending_request_id:
            return
        if phase is None:
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
                self.suspend_emergency()
                # Do not manufacture fresh measurements on errors. ATCS owns the timeout.
                self.state, self.message = 'unavailable', 'Pengukuran atau komunikasi adaptif terputus. ATCS memantau fallback.'
                self.batch = self.preview = None
                if self.video is not None:
                    self.video.vision.focus = False
            await asyncio.sleep(.5)

    def snapshot(self):
        provider = self.video_measurements
        batch = self.batch
        if self.video_mode and self.video is not None:
            # Display detection independently of acquiring the phase controller.
            # All map poses and per-approach timestamps come from this snapshot.
            batch = provider.snapshot(self.video)
        source = batch.source if self.video_mode and batch else 'recording' if self.video_mode else 'synthetic'
        return AdaptiveStatus(enabled=self.enabled, source=source, fault=self.fault, status=self.state,
            message=self.message, policy=self.policy.config, measurements=batch,
            decisions=([self.preview] if self.preview else [])+list(reversed(self.decisions)),
            auto_resume=self.auto_resume, source_sessions=provider.source_sessions if self.video_mode else {},
            issues=provider.issues if self.video_mode else {},
            map_vehicles=provider.vehicles if self.video_mode and batch else [],
            emergency=self.emergency.snapshot(servicing=self.emergency_serving))


class FaultInput(Contract):
    fault: Literal['none', 'frozen_data', 'invalid_data', 'sender_stopped']


router = APIRouter(prefix='/api/adaptive', tags=['Adaptif data buatan'])

@router.get('', response_model=AdaptiveStatus, dependencies=[Depends(require_operator)])
async def status(request: Request):
    return request.app.state.adaptive.snapshot()

@router.post('/fault', response_model=AdaptiveStatus, dependencies=[Depends(require_mutation)])
async def fault(payload: FaultInput, request: Request):
    sender = request.app.state.adaptive
    if not sender.enabled or sender.video_mode:
        raise error(409, 'SYNTHETIC_DISABLED', 'Uji data buatan belum diaktifkan.')
    sender.fault = payload.fault
    if payload.fault != 'frozen_data':
        sender.frozen = None
    return sender.snapshot()


@router.post('/hold', response_model=AdaptiveStatus, dependencies=[Depends(require_mutation)])
async def hold(request: Request):
    sender = request.app.state.adaptive
    if not sender.enabled or not sender.video_mode:
        raise error(409, 'VIDEO_CONTROL_DISABLED', 'Kendali dari video belum diaktifkan.')
    await sender.hold()
    return sender.snapshot()
