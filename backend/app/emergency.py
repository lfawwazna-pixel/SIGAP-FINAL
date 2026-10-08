"""Multi-camera, time-aware confirmation of actual emergency detections."""
from collections import deque
from datetime import datetime, timedelta, timezone
import time
from contracts.emergency import EmergencyStatus, EmergencyTarget
from backend.app.measurements import inside, line_side

class EmergencyCoordinator:
    def __init__(self, enabled=True, confidence=.6, confirmations=3, confirm_seconds=.6,
                 loss_seconds=1.2, maximum_seconds=60):
        self.enabled, self.threshold = enabled, confidence
        self.confirmations, self.confirm_seconds = confirmations, confirm_seconds
        self.loss_seconds, self.maximum_seconds = loss_seconds, maximum_seconds
        self.records, self.completed = {}, {}
        self.target = None
        self.events = deque(maxlen=20)
        self.state, self.message = 'idle', 'Tidak ada EVP terkonfirmasi.'
        self.started = None
        self.candidates = []

    def log(self, message):
        self.events.append(message)
        self.message = message

    def update(self, hub, now=None, at=None, control_active=True):
        now = time.monotonic() if now is None else now
        at = datetime.now(timezone.utc) if at is None else at
        if not self.enabled or hub is None:
            self.state = 'unavailable'
            self.target = None
            self.message = 'EVP video belum diaktifkan.'
            return self.snapshot()
        self.completed = {k:expiry for k,expiry in self.completed.items() if expiry is None or now < expiry}
        seen, available = set(), False
        for direction, channel in hub.channels.items():
            view = channel.view()
            if not view.detection_ready or view.state != 'playing' or channel.calibration is None:
                continue
            if channel.tracked_at is None or now-channel.tracked_at > 2:
                continue
            available = True
            cal = channel.calibration
            stamp = at-timedelta(seconds=max(0, now-channel.tracked_at))
            for track in channel.tracks:
                key = f'{direction}:{channel.session}:{channel.tracker_session}:{track.track_id}'
                if key in self.completed:
                    continue
                prior = self.records.get(key)
                if track.coasted or track.class_name not in ('ambulance', 'fire_truck') or track.confidence < self.threshold:
                    continue  # Display memory is not fresh classification evidence.
                if self.target and key == self.target.event_id and track.class_name != self.target.kind:
                    continue  # A class flip is not fresh proof of the locked target.
                x1,y1,x2,y2 = track.bbox
                x = (x1+x2)/2
                lanes = [name for name,polygon in cal.lanes.items() if inside(x,y2,polygon)]
                if len(lanes) != 1:
                    if prior is None:
                        continue
                    lane = prior['lane']
                else:
                    lane = lanes[0]
                if lane == 'outer':
                    continue  # Free left slip lane does not require a green override.
                polygon = cal.lanes[lane]
                cx,cy = sum(p.x for p in polygon)/len(polygon),sum(p.y for p in polygon)/len(polygon)
                upstream = line_side(cx,cy,cal.stop_line)
                if abs(upstream) < .0001:
                    continue
                extent = max(abs(line_side(p.x,p.y,cal.stop_line)) for p in polygon)
                passed = line_side(x,y1,cal.stop_line)*upstream < 0 and line_side(x,y2,cal.stop_line)*upstream < 0
                if passed:
                    self.completed[key] = None
                    self.records.pop(key,None)
                    if self.target and self.target.event_id == key:
                        self.log(f'EVP {direction} #{track.track_id} melewati garis henti; pemulihan melalui clearance.')
                        self.target, self.started, self.state = None, None, 'recovering'
                    continue
                distance = min(1,abs(line_side(x,y2,cal.stop_line))/max(extent,.0001))
                target = EmergencyTarget(event_id=key,direction=direction,source_session=channel.session,
                    track_id=track.track_id,kind=track.class_name,confidence=track.confidence,
                    distance_to_stop=distance,observed_at=stamp)
                record = self.records.setdefault(key,dict(first=channel.tracked_at,last=channel.tracked_at,
                    frame=None,hits=0,target=target,lane=lane))
                if record['frame'] != channel.tracked_id:
                    if record['target'].kind != target.kind or channel.tracked_at-record['last'] > self.loss_seconds:
                        record.update(first=channel.tracked_at,hits=0)
                    record.update(frame=channel.tracked_id,last=channel.tracked_at,hits=record['hits']+1,target=target,lane=lane)
                seen.add(key)
        self.records = {k:v for k,v in self.records.items() if now-v['last'] <= self.loss_seconds}
        # A session reset, dropped source or sustained loss cannot keep an old override alive.
        if self.target:
            if not control_active:
                self.started = None
            elif self.started is None:
                self.started = now
            record = self.records.get(self.target.event_id)
            if not record or self.started is not None and now-self.started >= self.maximum_seconds:
                self.completed[self.target.event_id] = None if record else now+3.0
                self.log('EVP hilang, sumber berubah, atau batas pelayanan tercapai; kembali melalui clearance.')
                self.target, self.started, self.state = None, None, 'recovering'
            elif self.target.event_id in seen:
                self.target = record['target']
        eligible = [v['target'] for v in self.records.values()
                    if v['hits'] >= self.confirmations and v['last']-v['first'] >= self.confirm_seconds
                    and v['target'].event_id not in self.completed]
        eligible.sort(key=lambda t:(t.kind != 'ambulance',t.distance_to_stop,t.observed_at,t.direction,t.track_id))
        self.candidates = eligible[:32]
        # Lock one target until completion; a fluctuating ranking cannot alternate lamp requests.
        if self.target is None and eligible and self.state != 'recovering':
            self.target, self.started, self.state = eligible[0], now if control_active else None, 'confirmed'
            self.log(f'EVP terkonfirmasi: {self.target.kind} {self.target.direction} #{self.target.track_id}. Adaptif antrean ditangguhkan.')
        elif self.target is None and self.state != 'recovering':
            self.state = 'confirming' if self.records else 'idle' if available else 'unavailable'
            self.message = 'Memverifikasi beberapa pengamatan EVP.' if self.records else 'Tidak ada EVP terkonfirmasi.' if available else 'Tracking atau kalibrasi belum siap untuk EVP.'
        self.completed = dict(list(self.completed.items())[-256:])
        return self.snapshot()

    def recovered(self):
        if self.state == 'recovering' and self.target is None:
            self.state, self.message = 'idle', 'Prioritas EVP selesai; keputusan adaptif normal dipulihkan.'

    def snapshot(self, servicing=False):
        state = 'servicing' if self.target and servicing else self.state
        return EmergencyStatus(state=state,target=self.target,candidates=self.candidates,
            focus=self.target is not None,message=self.message,events=list(self.events))
