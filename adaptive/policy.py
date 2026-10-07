from datetime import datetime
from contracts.adaptive import AdaptivePolicyConfig, AdaptiveDecision, MeasurementBatch
from contracts.configuration import PROJECT_ROOT, load_config

DIRECTIONS = ('U', 'T', 'S', 'B')


class AdaptivePolicy:
    def __init__(self, config=None):
        self.config = config or AdaptivePolicyConfig.model_validate_json(
            (PROJECT_ROOT/'configs/adaptive-policy.json').read_text(encoding='utf-8'))
        self.last_served = dict.fromkeys(DIRECTIONS, 0.0)
        self.previous = None
        self.baseline = load_config().fixed_time.green_seconds
        self.last_green = {}

    def served(self, approach, now, green_seconds=None):
        # Only applied green counts as service, never a submitted plan.
        self.last_served[approach] = now
        self.previous = approach
        if green_seconds is not None:
            self.last_green[approach] = green_seconds

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
        # Zero detections in a partial camera view is not proof of an empty road.
        # Keep that approach in the service-age guard without inventing a count.
        uncertain = {d for d in DIRECTIONS if batch.source != 'synthetic' and data[d].queue_visibility != 'full'}
        eligible = [d for d in DIRECTIONS if data[d].exit_available and (data[d].controlled_count or d in uncertain)]
        if not eligible:
            eligible = [d for d in DIRECTIONS if data[d].exit_available]
            reason = 'Tidak ada kebutuhan terkontrol; pelayanan minimum bergilir.'
        else:
            reason = 'Prioritas antrean dan waktu tunggu.'
        if not eligible:
            return AdaptiveDecision(decided_at=at, measurement_sequence=batch.sequence,
                approach=None, green_seconds=None, reason='Semua keluaran terblokir.', scores=scores, inputs=data)
        overdue = [d for d in eligible if (data[d].controlled_count or d in uncertain) and now-self.last_served[d] >= p.service_age_target]
        if overdue:
            selected = min(overdue, key=lambda d: (self.last_served[d], -data[d].oldest_wait_seconds, DIRECTIONS.index(d)))
            reason = 'Pemerataan: pendekat melewati target usia pelayanan.'
        else:
            alternatives = [d for d in eligible if d != self.previous]
            selected = max(alternatives or eligible, key=lambda d: (scores[d], -self.last_served[d], -DIRECTIONS.index(d)))
        v = data[selected]
        duration = min(p.maximum_green, max(p.minimum_green,
            p.minimum_green+p.seconds_per_queued_vehicle*v.queue_count+.5*(v.controlled_count-v.queue_count)))
        if batch.source != 'synthetic':
            baseline = self.baseline[selected]
            partial = v.queue_visibility != 'full'
            congested = v.queue_reaches_boundary or v.occupancy_ratio >= .35 or (v.queue_count >= 3 and v.oldest_wait_seconds >= 20)
            floor = baseline if congested else baseline*p.video_baseline_floor_ratio if partial else p.minimum_green
            previous = self.last_green.get(selected, baseline)
            duration = min(p.maximum_green, max(duration, floor, previous*(1-p.video_maximum_drop_ratio)))
            reason += (' Antrean padat/menjangkau batas kamera; waktu dasar dipertahankan.' if congested else ' Pandangan antrean sebagian; batas waktu dasar dipertahankan.' if partial else ' Ujung antrean terlihat; durasi boleh dikurangi bertahap.')
            reason += f' Dasar {baseline} dtk; penurunan maksimal {p.video_maximum_drop_ratio*100:g}% per pelayanan.'
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
