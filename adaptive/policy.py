from datetime import datetime
from contracts.adaptive import AdaptivePolicyConfig, AdaptiveDecision, MeasurementBatch
from contracts.configuration import PROJECT_ROOT

DIRECTIONS = ('U', 'T', 'S', 'B')


class AdaptivePolicy:
    def __init__(self, config=None):
        self.config = config or AdaptivePolicyConfig.model_validate_json(
            (PROJECT_ROOT/'configs/adaptive-policy.json').read_text(encoding='utf-8'))
        self.last_served = dict.fromkeys(DIRECTIONS, 0.0)
        self.previous = None

    def served(self, approach, now):
        # Only applied green counts as service, never a submitted plan.
        self.last_served[approach] = now
        self.previous = approach

    def choose(self, batch: MeasurementBatch, now: float, at: datetime):
        p = self.config
        data = batch.approaches
        invalid = [d for d, v in data.items() if not v.usable or
                   not -.5 <= (at-v.observed_at).total_seconds() <= p.data_timeout]
        scores = {d: round(p.queue_weight*v.queue_count+p.wait_weight*v.oldest_wait_seconds+
                          p.age_weight*max(0, now-self.last_served[d]), 3) for d, v in data.items()}
        if invalid:
            return AdaptiveDecision(decided_at=at, measurement_sequence=batch.sequence,
                approach=None, green_seconds=None, reason='Data tidak layak: '+', '.join(invalid), scores=scores, inputs=data)
        eligible = [d for d in DIRECTIONS if data[d].exit_available and data[d].controlled_count]
        if not eligible:
            eligible = [d for d in DIRECTIONS if data[d].exit_available]
            reason = 'Tidak ada kebutuhan terkontrol; pelayanan minimum bergilir.'
        else:
            reason = 'Prioritas antrean dan waktu tunggu.'
        if not eligible:
            return AdaptiveDecision(decided_at=at, measurement_sequence=batch.sequence,
                approach=None, green_seconds=None, reason='Semua keluaran terblokir.', scores=scores, inputs=data)
        overdue = [d for d in eligible if data[d].controlled_count and now-self.last_served[d] >= p.service_age_target]
        if overdue:
            selected = min(overdue, key=lambda d: (self.last_served[d], -data[d].oldest_wait_seconds, DIRECTIONS.index(d)))
            reason = 'Pemerataan: pendekat melewati target usia pelayanan.'
        else:
            alternatives = [d for d in eligible if d != self.previous]
            selected = max(alternatives or eligible, key=lambda d: (scores[d], -self.last_served[d], -DIRECTIONS.index(d)))
        v = data[selected]
        duration = min(p.maximum_green, max(p.minimum_green,
            p.minimum_green+p.seconds_per_queued_vehicle*v.queue_count+.5*(v.controlled_count-v.queue_count)))
        return AdaptiveDecision(decided_at=at, measurement_sequence=batch.sequence,
            approach=selected, green_seconds=round(duration, 1), reason=reason, scores=scores, inputs=data)


def measure_world(world, intersection_id, session, at):
    """Synthetic provider only. Slips never contribute to signal-controlled demand."""
    approaches = {}
    for d in DIRECTIONS:
        cars = [v for v in world.vehicles if v.route.origin == d and not v.committed]
        controlled = [v for v in cars if v.route.movement != 'left']
        waiting = [v for v in controlled if v.stopped]
        approaches[d] = dict(observed_at=at, usable=True, controlled_count=len(controlled),
            queue_count=len(waiting), oldest_wait_seconds=max((v.wait for v in waiting), default=0),
            slip_count=sum(v.route.movement == 'left' for v in cars),
            exit_available=any(world.exit_available(v) for v in controlled) if controlled else True)
    return MeasurementBatch(intersection_id=intersection_id, source='synthetic', source_session=session,
        sequence=world.sequence, approaches=approaches)
