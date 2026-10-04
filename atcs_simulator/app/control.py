"""ATCS-owned authority, watchdogs and safe handover. No browser/backend timer dependency."""
from collections import OrderedDict, deque
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import uuid4

from atcs_simulator.app.engine import FixedTimeEngine
from contracts.control import CommandReceipt, ControlEvent, ControlPolicy, ControlStatus


class Rejected(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


@dataclass
class Plan:
    request_id: object
    approach: str
    green_seconds: float
    expires: float


class ControlSupervisor:
    def __init__(self, engine, settings, policy):
        self.engine, self.settings, self.policy = engine, settings, policy
        self.state = 'fixed_time'
        self.revision = 0
        self.sender = self.source = self.session = None
        self.retired_senders = deque(maxlen=64)
        self.observation_sequence = 0
        self.observations = {}
        self.data_deadlines = {}
        self.heartbeat_deadline = None
        self.sequences = {'heartbeat': 0, 'plan': 0}
        self.pending = self.active = None
        self.activation_request = self.release_request = None
        self.wait_until = None
        self.fallback_code = None
        self.reason = 'ATCS menjalankan fixed-time; aktivasi SIGAP memerlukan sumber yang siap.'
        self.receipts = OrderedDict()
        self.events = deque(maxlen=100)
        self.event_sequence = 0
        self.was_ready = False

    def journal(self, code, message, at, request_id=None):
        self.event_sequence += 1
        self.events.append(ControlEvent(sequence=self.event_sequence, occurred_at=at, code=code,
                                        message=message, request_id=request_id))

    def readiness(self, now):
        if not self.settings.configured:
            return False, 'Kunci komunikasi antarlayanan belum dikonfigurasi.'
        if self.sender is None:
            return False, 'Belum ada sumber CCTV/YOLO yang mengirim kesiapan.'
        if self.source == 'integration_test' and not self.settings.atcs_enable_test_source:
            return False, 'Sumber pengujian tidak diizinkan pada instance ini.'
        if len(self.observations) != 4 or not all(o.usable for o in self.observations.values()):
            return False, 'Data satu atau lebih pendekat tidak layak dipakai.'
        if not self.data_deadlines or min(self.data_deadlines.values()) <= now:
            return False, 'Data pengamatan sudah kedaluwarsa.'
        return True, ('Sumber uji integrasi siap; bukan CCTV aktual.' if self.source == 'integration_test'
                      else 'Pengamatan empat pendekat siap; menunggu aktivasi operator.')

    def update_receipt(self, identity, outcome, code, message, at):
        if identity in self.receipts:
            receipt = self.receipts[identity][1]
            receipt.outcome, receipt.code, receipt.message = outcome, code, message
            receipt.updated_at, receipt.revision = at, self.revision
            self.journal(code, message, at, identity)

    def revoke(self, code, reason, now, at, release_id=None):
        if self.state not in ('activating', 'adaptive'):
            return
        self.revision += 1
        self.state = 'returning_atcs'
        self.session = None  # Fence the old owner before any physical transition.
        self.heartbeat_deadline = None
        self.fallback_code, self.reason = code, reason
        if self.pending:
            self.update_receipt(self.pending.request_id, 'cancelled', code, 'Rencana dibatalkan: '+reason, at)
        if self.activation_request:
            receipt = self.receipts.get(self.activation_request)
            if receipt and receipt[1].outcome == 'accepted':
                self.update_receipt(self.activation_request, 'cancelled', code, reason, at)
        self.pending = self.active = None
        self.release_request = release_id
        self.journal(code, reason, at, release_id)
        self.engine._record('control_changed', reason, self.engine.phase, self.engine.active_approach)

    def check(self, now, at):
        ready, _ = self.readiness(now)
        if ready != self.was_ready:
            self.was_ready = ready
            self.revision += 1
            self.journal('SOURCE_READY' if ready else 'SOURCE_UNREADY', self.readiness(now)[1], at)
        if self.session is None:
            return
        if not ready:
            self.revoke('DATA_UNUSABLE', 'Fallback: data SIGAP tidak layak atau kedaluwarsa.', now, at)
        elif now >= self.heartbeat_deadline:
            self.revoke('HEARTBEAT_LOST', 'Fallback: heartbeat SIGAP terputus.', now, at)
        elif (self.pending and now >= self.pending.expires) or (self.active and now >= self.active.expires):
            self.revoke('PLAN_EXPIRED', 'Fallback: masa berlaku keputusan SIGAP berakhir.', now, at)
        elif self.pending is None and self.wait_until is not None and now >= self.wait_until:
            self.revoke('PLAN_MISSING', 'Fallback: tidak ada keputusan SIGAP berikutnya yang valid.', now, at)

    def submit(self, command, now, at):
        fingerprint = sha256(json.dumps(command.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        previous = self.receipts.get(command.request_id)
        if previous:
            if previous[0] == fingerprint:
                return previous[1].model_copy(update={'duplicate': True})
            return CommandReceipt(request_id=command.request_id, atcs_run_id=self.engine.run_id,
                action=command.action, outcome='rejected', code='REQUEST_ID_REUSED',
                message='Identitas perintah sudah dipakai untuk isi yang berbeda.', session_id=None,
                revision=self.revision, received_at=at, updated_at=at)
        self.check(now, at)
        receipt = CommandReceipt(request_id=command.request_id, atcs_run_id=self.engine.run_id,
            action=command.action, outcome='accepted', code='ACCEPTED', message='Permintaan diterima; menunggu penerapan.',
            session_id=self.session, revision=self.revision, received_at=at, updated_at=at)
        self.receipts[command.request_id] = (fingerprint, receipt)
        while len(self.receipts) > 512:
            # Keep receipts of pending handovers/plans available until completion.
            protected = {self.activation_request, self.release_request,
                         self.pending.request_id if self.pending else None,
                         self.active.request_id if self.active else None}
            removable = next((k for k in self.receipts if k not in protected), None)
            if removable is None:
                break
            self.receipts.pop(removable)
        try:
            if not self.settings.configured:
                raise Rejected('CONTROL_DISABLED', 'Komunikasi kendali belum dikonfigurasi.')
            if command.atcs_run_id != self.engine.run_id:
                raise Rejected('RUN_CHANGED', 'Sesi ATCS sudah berubah; baca keadaan terbaru.')
            if self.engine.state != 'running':
                raise Rejected('ENGINE_UNAVAILABLE', 'Mesin fase tidak operasional.')
            ttl = (command.expires_at-command.issued_at).total_seconds()
            if command.expires_at <= at or ttl > self.policy.maximum_command_ttl_seconds or (command.issued_at-at).total_seconds() > self.policy.clock_skew_seconds:
                raise Rejected('COMMAND_EXPIRED', 'Perintah terlambat atau masa berlakunya tidak sesuai batas.')
            if command.action == 'observe':
                self.observe(command, now, at)
                receipt.outcome, receipt.code, receipt.message = 'applied', 'OBSERVED', 'Kualitas dan umur data diperiksa ATCS.'
            elif command.action == 'activate':
                if command.expected_revision != self.revision:
                    raise Rejected('REVISION_CHANGED', 'Keadaan kendali berubah; baca ulang sebelum aktivasi.')
                if self.state != 'fixed_time' or command.sender_id != self.sender or not self.readiness(now)[0]:
                    raise Rejected('NOT_READY', 'Sumber belum siap atau pengendali sedang dalam transisi.')
                self.session = uuid4()
                self.state = 'activating'
                self.revision += 1
                self.sequences = {'heartbeat': 0, 'plan': 0}
                self.heartbeat_deadline = now+self.policy.heartbeat_timeout_seconds
                self.wait_until = now+self.policy.plan_wait_seconds
                self.activation_request = command.request_id
                self.fallback_code = None
                self.reason = 'Aktivasi diterima; menunggu rencana dan transisi aman.'
            else:
                if self.session is None or command.session_id != self.session or command.sender_id != self.sender:
                    raise Rejected('SESSION_REVOKED', 'Sesi kendali tidak aktif; diperlukan aktivasi operator baru.')
                if command.action in ('heartbeat', 'plan'):
                    if command.sequence <= self.sequences[command.action]:
                        raise Rejected('OUT_OF_ORDER', 'Nomor urut perintah tidak lebih baru.')
                if command.action == 'heartbeat':
                    self.heartbeat_deadline = now+self.policy.heartbeat_timeout_seconds
                    self.sequences['heartbeat'] = command.sequence
                    receipt.outcome, receipt.code, receipt.message = 'applied', 'HEARTBEAT', 'Heartbeat diterima; umur data tetap diperiksa terpisah.'
                elif command.action == 'plan':
                    horizon = (command.plan_valid_until-at).total_seconds()
                    if not self.policy.minimum_green_seconds <= command.green_seconds <= self.policy.maximum_green_seconds:
                        raise Rejected('GREEN_BOUNDS', 'Durasi hijau di luar batas pengendali.')
                    if not command.green_seconds <= horizon <= self.policy.maximum_plan_horizon_seconds:
                        raise Rejected('PLAN_LIFETIME', 'Masa berlaku rencana tidak cukup atau terlalu panjang.')
                    if self.pending:
                        self.update_receipt(self.pending.request_id, 'cancelled', 'SUPERSEDED', 'Digantikan rencana dengan nomor urut lebih baru.', at)
                    self.pending = Plan(command.request_id, command.approach, command.green_seconds, now+horizon)
                    self.sequences['plan'] = command.sequence
                elif command.action == 'release':
                    if command.expected_revision != self.revision:
                        raise Rejected('REVISION_CHANGED', 'Keadaan kendali berubah; baca ulang sebelum pelepasan.')
                    self.revoke('OPERATOR_RELEASE', 'Operator meminta kembali ke ATCS fixed-time.', now, at, command.request_id)
            self.check(now, at)
        except Rejected as exc:
            receipt.outcome, receipt.code, receipt.message = 'rejected', exc.code, exc.message
        receipt.session_id, receipt.revision = self.session, self.revision
        if command.action not in ('heartbeat', 'observe') or receipt.outcome == 'rejected':
            self.journal(receipt.code, receipt.message, at, command.request_id)
        return receipt.model_copy(deep=True)

    def observe(self, command, now, at):
        if command.source == 'integration_test' and not self.settings.atcs_enable_test_source:
            raise Rejected('TEST_SOURCE_DISABLED', 'Sumber uji tidak diizinkan pada instance ATCS ini.')
        if command.sender_id in self.retired_senders:
            raise Rejected('SENDER_RETIRED', 'Proses sumber lama sudah digantikan.')
        same = command.sender_id == self.sender
        if same and (command.sequence <= self.observation_sequence or command.source != self.source):
            raise Rejected('OUT_OF_ORDER', 'Urutan pengamatan atau identitas sumber tidak sesuai.')
        for direction, observation in command.observations.items():
            if (observation.observed_at-at).total_seconds() > self.policy.clock_skew_seconds:
                raise Rejected('DATA_CLOCK', 'Waktu pengamatan berada terlalu jauh di masa depan.')
            if same and direction in self.observations and observation.observed_at < self.observations[direction].observed_at:
                raise Rejected('DATA_REPLAY', 'Waktu pengamatan mundur.')
        if not same:
            if self.sender:
                self.retired_senders.append(self.sender)
                self.revoke('SOURCE_RESTART', 'Fallback: identitas proses sumber SIGAP berubah.', now, at)
            self.observations, self.data_deadlines = {}, {}
            self.sender, self.source = command.sender_id, command.source
            self.revision += 1
        for direction, observation in command.observations.items():
            previous = self.observations.get(direction)
            if previous is None or observation.observed_at > previous.observed_at:
                age = max(0, (at-observation.observed_at).total_seconds())
                self.data_deadlines[direction] = now+max(0, self.policy.data_timeout_seconds-age)
        self.observations = command.observations
        self.observation_sequence = command.sequence

    def apply_plan(self, now, at):
        plan = self.pending
        if now + plan.green_seconds > plan.expires:
            self.revoke('PLAN_EXPIRED', 'Fallback: masa berlaku rencana tidak cukup untuk hijau penuh.', now, at)
            return
        self.pending = None
        self.active = plan
        self.state = 'adaptive'
        self.revision += 1
        self.wait_until = now+plan.green_seconds+self.engine.config.fixed_time.yellow_seconds+self.engine.config.fixed_time.all_red_min_seconds+self.policy.plan_wait_seconds
        self.reason = f'Keputusan SIGAP diterapkan: {plan.approach}, hijau {plan.green_seconds:g} detik.'
        self.engine._transition('green', plan.approach, plan.green_seconds, self.reason)
        self.update_receipt(plan.request_id, 'applied', 'PLAN_APPLIED', self.reason, at)
        if self.activation_request:
            self.update_receipt(self.activation_request, 'applied', 'CONTROL_ACQUIRED', 'SIGAP memperoleh kendali setelah transisi aman.', at)
            self.activation_request = None
        self.engine._record('control_changed', self.reason, 'all_red', None)

    def finish_fallback(self, at):
        self.state = 'fixed_time'
        self.revision += 1
        self.reason = 'ATCS fixed-time kembali mengendalikan; aktivasi SIGAP menunggu operator.'
        if self.release_request:
            self.update_receipt(self.release_request, 'applied', 'RELEASED', self.reason, at)
            self.release_request = None
        self.activation_request = None
        self.journal('FIXED_TIME_RESUMED', self.reason, at)
        self.engine._record('control_changed', self.reason, self.engine.phase, self.engine.active_approach)

    def snapshot(self, now, at, available=True):
        ready, reason = self.readiness(now)
        return ControlStatus(intersection_id=self.engine.config.intersection_id, atcs_run_id=self.engine.run_id,
            observed_at=at, available=available, configured=self.settings.configured,
            allow_test_source=self.settings.atcs_enable_test_source, state=self.state,
            controller='SIGAP' if self.state == 'adaptive' else 'ATCS', revision=self.revision,
            sender_id=self.sender, source=self.source, ready=ready and available, readiness_reason=reason,
            activation_required=self.session is None, session_id=self.session,
            heartbeat_remaining_seconds=max(0, self.heartbeat_deadline-now) if self.heartbeat_deadline is not None else None,
            data_remaining_seconds=max(0, min(self.data_deadlines.values())-now) if self.data_deadlines else None,
            pending_request_id=self.pending.request_id if self.pending else None,
            active_request_id=self.active.request_id if self.active else None,
            fallback_code=self.fallback_code, reason=self.reason, policy=self.policy, events=list(self.events))


class ManagedEngine(FixedTimeEngine):
    def __init__(self, *args, control_settings, policy=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.phase_started = self.last_tick
        self.control = ControlSupervisor(self, control_settings, policy or ControlPolicy())

    def _transition(self, phase, approach, duration, reason):
        super()._transition(phase, approach, duration, reason)
        self.phase_started = self.last_tick

    def tick(self, *, now, at, conflict):
        if self.state != 'running':
            return
        import math
        if not math.isfinite(now) or now < self.last_tick:
            raise ValueError('Clock must be finite and monotonic')
        self.last_tick, self.updated_at, self.conflict = now, at, conflict.model_copy(deep=True)
        self.control.check(now, at)
        state = self.control.state
        if state == 'fixed_time' or (state == 'activating' and self.control.pending is None):
            super().tick(now=now, at=at, conflict=conflict)
            return
        self.sequence_number += 1
        timing = self.config.fixed_time
        if self.phase == 'green':
            interrupted = state in ('activating', 'returning_atcs')
            finish = min(self.deadline, self.phase_started+self.control.policy.minimum_green_seconds) if interrupted else self.deadline
            if now >= finish:
                self._transition('yellow', self.active_approach, timing.yellow_seconds, 'Transisi kuning; pergantian kendali/fase menunggu clearance.')
        elif now >= self.deadline and self.phase == 'yellow':
            self.next_index = (timing.sequence.index(self.active_approach)+1) % len(timing.sequence)
            self._transition('all_red', None, timing.all_red_min_seconds, 'Semua merah minimum sebelum pelepasan pendekat berikutnya.')
        elif self.phase == 'all_red' and now >= self.deadline:
            if conflict.state != 'clear':
                self.reason = 'Semua merah diperpanjang: area konflik terisi atau belum diketahui.'
                if self.clearance_state != 'waiting_conflict':
                    self.clearance_state = 'waiting_conflict'
                    self._record('clearance_held', self.reason, self.phase, None)
                return
            if self.clearance_state == 'waiting_conflict':
                self._record('clearance_released', 'Area konflik kosong.', self.phase, None)
            if state == 'returning_atcs':
                self.control.finish_fallback(at)
                approach = timing.sequence[self.next_index]
                self._transition('green', approach, timing.green_seconds[approach], 'ATCS melanjutkan urutan fixed-time setelah transisi aman.')
            elif self.control.pending:
                self.control.apply_plan(now, at)
            else:
                self.clearance_state = 'waiting_command'
                self.reason = 'Semua merah: menunggu keputusan SIGAP berikutnya; batas waktu dipantau ATCS.'

    def snapshot(self, observed_at):
        # FixedTimeEngine validates its snapshot; waiting_command has a bounded wait.
        report = super().snapshot(observed_at)
        state = self.control.state
        update = {'controller': 'SIGAP' if state == 'adaptive' else 'ATCS',
                  'mode': 'adaptive' if state == 'adaptive' else 'fallback' if state == 'returning_atcs' else 'fixed_time'}
        if self.clearance_state == 'waiting_command':
            update['remaining_seconds'] = max(0, self.control.wait_until-self.last_tick)
        if self.phase == 'green' and (state == 'returning_atcs' or (state == 'activating' and self.control.pending)):
            update['remaining_seconds'] = max(0, min(self.deadline, self.phase_started+self.control.policy.minimum_green_seconds)-self.last_tick)
        return report.model_copy(update=update)

    def end(self, *, at, fault=False):
        self.control.revoke('ENGINE_STOPPED', 'Mesin ATCS berhenti; sesi kendali dicabut.', self.last_tick, at)
        super().end(at=at, fault=fault)
