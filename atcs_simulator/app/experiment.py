"""Isolated experiment clock and controller; never sends commands to operational ATCS."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from atcs_simulator.app.traffic import DIRECTIONS, TrafficWorld
from adaptive.policy import AdaptivePolicy, measure_world


class Experiment:
    def __init__(self, config, seed=42):
        self.config = config
        self.seed = seed
        self.world = TrafficWorld(seed)
        self.run_id = str(uuid4())
        self.running = False
        self.speed = 1
        self.strategy = 'adaptive'
        self.phase = 'all_red'
        self.active = None
        self.deadline = config.fixed_time.all_red_min_seconds
        self.fixed_next = 0
        self.last_served = dict.fromkeys(DIRECTIONS, 0.0)
        self.adaptive = AdaptivePolicy()
        self.decision = None
        self.target = None
        self.emergency = False
        self.reason = 'Percobaan siap; tekan Mulai. ATCS utama tetap berjalan.'
        self.world.record(self.reason)

    @property
    def signals(self):
        return {d: self.phase if d == self.active else 'red' for d in DIRECTIONS}

    def transition(self, phase, active, duration, reason):
        self.phase, self.active = phase, active
        self.deadline = self.world.time + duration
        self.reason = reason
        self.world.record(reason)

    def pick_normal(self):
        if self.strategy == 'fixed_time':
            self.decision = None
            return self.config.fixed_time.sequence[self.fixed_next]
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)+timedelta(seconds=self.world.time)
        batch = measure_world(self.world, self.config.intersection_id, self.run_id, at)
        self.decision = self.adaptive.choose(batch, self.world.time, at)
        return self.decision.approach

    def tick(self, dt):
        self.world.step(dt, self.signals)
        now = self.world.time
        timing = self.config.fixed_time
        candidates = self.world.candidates()
        selected = next((v for v in candidates if v.id == self.target), None)
        # Once service is granted, finish it before re-ranking other requests.
        if self.target is not None and selected is None:
            self.target = None
            self.deadline = min(self.deadline, now)
        if candidates and not self.emergency:
            self.emergency = True
            self.decision = None
            self.reason = 'EVP terdeteksi; keputusan adaptif ditangguhkan.'
            self.world.record(self.reason)
            if self.phase == 'green':
                self.transition('yellow', self.active, timing.yellow_seconds, 'Transisi menuju pelayanan darurat.')
        if self.emergency and self.phase == 'green' and self.target is not None:
            # A blocked exit cannot be bypassed; the vehicle remains queued visibly.
            self.reason = f'Prioritas EVP #{self.target} dari {self.active}; menunggu selesai melintas.'
            return
        if now < self.deadline:
            return
        if self.phase == 'green':
            self.last_served[self.active] = now
            if self.strategy == 'fixed_time':
                self.fixed_next = (self.config.fixed_time.sequence.index(self.active)+1) % 4
            self.transition('yellow', self.active, timing.yellow_seconds, 'Hijau selesai; kuning sebelum pergantian.')
        elif self.phase == 'yellow':
            self.transition('all_red', None, timing.all_red_min_seconds, 'Semua merah; menunggu area konflik kosong.')
        elif self.world.read() != 'clear':
            self.reason = 'Semua merah diperpanjang; kendaraan masih di area konflik.'
        else:
            if candidates:
                chosen = candidates[0]
                self.target = chosen.id
                self.emergency = True
                self.transition('green', chosen.route.origin, 0,
                                f'EVP #{chosen.id}: {"ambulans" if chosen.kind == "ambulance" else "pemadam"}, '
                                f'jarak {max(0, chosen.route.gate-chosen.distance):.0f} unit skema. Target pelayanan dikunci.')
            else:
                if self.emergency:
                    self.emergency = False
                    self.world.record('Semua EVP selesai; kembali ke strategi '+self.strategy+'.')
                direction = self.pick_normal()
                if direction is None:
                    self.reason = self.decision.reason
                    return
                queue = sum(v.route.origin == direction and not v.committed for v in self.world.vehicles)
                duration = timing.green_seconds[direction] if self.strategy == 'fixed_time' else self.decision.green_seconds
                self.adaptive.served(direction, now)
                if self.decision:
                    self.decision.outcome = 'applied'
                self.transition('green', direction, duration,
                                f'{"Adaptif percobaan" if self.strategy == "adaptive" else "Fixed-time percobaan"}: '
                                f'{direction}, {queue} kendaraan, hijau {duration} detik. '+(self.decision.reason if self.decision else ''))

    def advance(self, seconds):
        if not self.running:
            return
        remaining = min(max(0, seconds), .5) * self.speed
        while remaining > .000001:
            dt = min(.05, remaining)
            self.tick(dt)
            remaining -= dt

    def snapshot(self, intersection_id):
        candidates = self.world.candidates()
        return {
            'intersection_id': intersection_id, 'source': 'experiment', 'run_id': self.run_id,
            'observed_at': datetime.now(timezone.utc), 'available': True,
            'time_seconds': round(self.world.time, 3), 'running': self.running, 'speed': self.speed,
            'strategy': self.strategy, 'phase': self.phase, 'active_approach': self.active, 'signals': self.signals,
            'remaining_seconds': None if (self.emergency and self.phase == 'green') or (self.phase == 'all_red' and self.world.read() != 'clear') else max(0, self.deadline-self.world.time),
            'emergency': self.emergency, 'target_vehicle': self.target, 'reason': self.reason,
            'demand': dict(self.world.demand), 'blocked_exit': self.world.blocked_exit,
            'events': list(self.world.events), 'evp_queue': [v.id for v in candidates], **self.world.snapshot(),
            'decision': self.decision,
        }
