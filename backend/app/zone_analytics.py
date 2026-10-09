"""Read-only arrival profiles from the same calibrated admission as the dashboard.

Counts unique, freshly observed ordinary identities entering each zone. A frame's
standing population is not an arrival rate. This does not change tracking/control.
"""
from collections import Counter, OrderedDict, deque
from datetime import datetime, timezone
from hashlib import sha256
import json
import time
from contracts.analytics import ZoneApproachDemand, ZoneDemand, DemandProvenance, TrafficComposition, ComparisonInput
from contracts.zones import inside, zone_tracks
from backend.app.impact_queue import KINDS, MOVEMENTS
from backend.app.measurements import line_side


class ZoneDemandCollector:
    def __init__(self):
        self.states, self.captured, self.hub = {}, OrderedDict(), None

    @staticmethod
    def generation(channel):
        return (str(channel.session), channel.calibration.model_dump_json() if channel.calibration else '')

    def observe(self, hub):
        self.hub = hub
        for direction, channel in hub.channels.items():
            generation = self.generation(channel)
            state = self.states.get(direction)
            if state is None or state['generation'] != generation:
                state = self.states[direction] = dict(generation=generation, frame=None, tracker=None,
                    start=None, last=None, seen=set(), events=deque(), source=channel.source, loops=0,
                    visibility='full' if channel.calibration and channel.calibration.upstream_queue_visible else 'partial')
            view = channel.view()
            if not channel.calibration or not view.detection_ready or view.state != 'playing' or channel.tracked_at is None:
                state['start'], state['last'] = None, None
                state['events'].clear()
                state['tracker'] = None
                continue
            frame = (str(channel.tracker_session), channel.tracked_id)
            admitted = zone_tracks(channel.tracks, channel.calibration)
            ambiguous = any(sum(inside((t.bbox[0]+t.bbox[2])/2,t.bbox[3],p) for p in channel.calibration.lanes.values()) != 1 for t in admitted)
            ambiguous = ambiguous or any(abs(line_side(sum(p.x for p in polygon)/len(polygon),
                sum(p.y for p in polygon)/len(polygon),channel.calibration.stop_line)) < 1e-8
                for name,polygon in channel.calibration.lanes.items() if name != 'outer')
            if ambiguous:
                state['start'], state['last'], state['tracker'] = None, None, None
                state['events'].clear()
                continue
            if frame == state['frame']:
                continue
            state['frame'] = frame
            at = channel.tracked_at
            gap = state['last'] is None or at-state['last'] > 3 or at < state['last']
            if gap:
                state['start'] = at
                state['events'].clear()
                state['tracker'] = None
            state['last'], state['loops'] = at, channel.loop_count
            fresh_tracker = state['tracker'] != str(channel.tracker_session)
            if fresh_tracker:
                state['tracker'], state['seen'] = str(channel.tracker_session), set()
            entries = []
            for track in admitted:
                if track.coasted or track.track_id in state['seen']:
                    continue
                # Even excluded EVP IDs are remembered; a fluctuating class
                # must not turn an existing identity into a later arrival.
                state['seen'].add(track.track_id)
                if fresh_tracker or track.class_name not in KINDS:
                    continue
                x1, _, x2, y = track.bbox
                x = (x1+x2)/2
                lanes = [name for name, polygon in channel.calibration.lanes.items() if inside(x,y,polygon)]
                if len(lanes) != 1:
                    continue
                lane = lanes[0]
                polygon = channel.calibration.lanes[lane]
                sign = line_side(sum(p.x for p in polygon)/len(polygon),sum(p.y for p in polygon)/len(polygon),channel.calibration.stop_line)
                if lane != 'outer' and (abs(sign) < 1e-8 or line_side(x,y,channel.calibration.stop_line)*sign < 0):
                    continue
                entries.append((track.class_name,dict(outer='left',middle='straight',inner='right')[lane]))
            state['events'].append((at,entries))
            while state['events'] and state['events'][0][0] < at-180:
                state['events'].popleft()

    def snapshot(self, now=None, at=None):
        now, at = time.monotonic() if now is None else now, at or datetime.now(timezone.utc)
        approaches = []
        for direction in 'UTSB':
            s = self.states.get(direction)
            valid = s is not None and s['last'] is not None and 0 <= now-s['last'] <= 3
            if valid and self.hub is not None:
                valid = s['generation'] == self.generation(self.hub.channels[direction])
            seconds = min(180,max(0,s['last']-s['start'])) if valid else 0
            entries = [v for stamp, batch in s['events'] for v in batch if stamp > s['last']-seconds] if valid else []
            classes, movements = Counter(v[0] for v in entries), Counter(v[1] for v in entries)
            rate = len(entries)*60/seconds if seconds else 0
            state = 'ready' if valid and seconds >= 60 and rate <= 180 else 'collecting' if valid and rate <= 180 else 'unavailable'
            message = ('Profil kedatangan teramati dalam zona; bukan arus lapangan lengkap.' if state == 'ready' else
                'Kumpulkan minimal 60 detik tracking berkelanjutan.' if state == 'collecting' else
                'Laju teramati melebihi batas eksperimen 180 kendaraan/menit.' if rate > 180 else
                'Video harus berjalan dengan tracking mutakhir dan kalibrasi lajur.')
            approaches.append(ZoneApproachDemand(direction=direction,state=state,message=message,
                source=s['source'] if s else 'none', observed_seconds=round(seconds,3), entries=len(entries),
                demand_per_minute=round(rate,4), by_class={k:classes[k] for k in KINDS},
                by_movement={m:movements[m] for m in MOVEMENTS},
                queue_visibility=s['visibility'] if s else 'partial', loop_count=s['loops'] if s else 0))
        ready = all(p.state == 'ready' for p in approaches)
        fingerprint = None
        if ready:
            signature = self.signature()
            fingerprint = sha256(json.dumps([signature,[p.model_dump() for p in approaches]],sort_keys=True).encode()).hexdigest()
            self.captured[fingerprint] = (now,at,signature,approaches)
            self.captured.move_to_end(fingerprint)
            while len(self.captured) > 100:
                self.captured.popitem(last=False)
        return ZoneDemand(ready=ready, generated_at=at, approaches=approaches,fingerprint=fingerprint,
            message='Profil siap dipakai sebagai masukan eksperimen, tanpa mengubah kendali lampu.' if ready else
            'Profil zona belum lengkap. Jalankan dan kalibrasikan empat video, atau gunakan skenario manual.')

    def signature(self):
        if self.hub is not None:
            return tuple((d,self.generation(self.hub.channels[d])) for d in 'UTSB')
        return tuple((d,self.states[d]['generation']) for d in 'UTSB' if d in self.states)

    def resolve(self, spec, now=None):
        now = time.monotonic() if now is None else now
        captured = self.captured.get(spec.observation_fingerprint)
        if not captured or not 0 <= now-captured[0] <= 600 or captured[2] != self.signature():
            raise ValueError('Profil zona kedaluwarsa atau sumber berubah. Ambil profil terbaru dari panel analitik.')
        _, at, _, profiles = captured
        classes = {k:sum(p.by_class[k] for p in profiles) for k in KINDS}
        turns = {m:sum(p.by_movement[m] for p in profiles) for m in MOVEMENTS}
        # Zero arrivals is valid. Composition is irrelevant for a zero-rate arm.
        default_classes = classes if sum(classes.values()) else spec.class_mix
        default_turns = turns if sum(turns.values()) else spec.turn_mix
        raw = spec.model_dump()
        raw.update(demand_per_minute={p.direction:p.demand_per_minute for p in profiles},
            class_mix=default_classes, turn_mix=default_turns,
            queue_visibility='full' if all(p.queue_visibility == 'full' for p in profiles) else 'partial',
            approach_composition={p.direction:TrafficComposition(class_mix=p.by_class if p.entries else default_classes,
                turn_mix=p.by_movement if p.entries else default_turns).model_dump() for p in profiles})
        return ComparisonInput.model_validate(raw), DemandProvenance(source='zone_observation', captured_at=at,
            fingerprint=spec.observation_fingerprint, approaches=profiles)
