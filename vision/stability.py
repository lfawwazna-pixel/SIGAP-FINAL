"""Bounded memory of actual detections, independent per camera/tracker session."""
from copy import deepcopy

def iou(a, b):
    overlap = max(0, min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-overlap
    return overlap/union if union > 0 else 0

class TrackStabilizer:
    def __init__(self, hold_seconds=1.2):
        self.hold = hold_seconds
        self.tracks, self.aliases = {}, {}
        self.next_id = 0
        self.last_time = None

    def update(self, detections, at):
        if self.last_time is not None and at <= self.last_time:
            raise ValueError('Tracking sample must advance')
        self.last_time = at
        self.tracks = {k:v for k,v in self.tracks.items() if at-v['seen'] <= self.hold}
        self.aliases = {k:v for k,v in self.aliases.items() if v in self.tracks}
        matched, pending = set(), []
        # Preserve existing identities before considering a new ByteTrack ID.
        for obj in detections:
            identity = self.aliases.get(obj['track_id'])
            if identity in self.tracks and identity not in matched:
                self._seen(identity, obj, at)
                matched.add(identity)
            else:
                pending.append(obj)
        for obj in pending:
            candidates = sorted(((iou(obj['bbox'], v['object']['bbox']), k)
                for k,v in self.tracks.items() if k not in matched
                and obj['class_name'] == v['object']['class_name']), reverse=True)
            # Reassociate only a unique, strong overlap with a temporarily missing
            # object. Adjacent live vehicles can never be merged with each other.
            if candidates and candidates[0][0] >= .55 and (len(candidates)==1 or candidates[0][0]-candidates[1][0] >= .15):
                identity = candidates[0][1]
            else:
                self.next_id += 1
                identity = self.next_id
            self.aliases[obj['track_id']] = identity
            self._seen(identity, obj, at)
            matched.add(identity)
        output = []
        for identity, value in sorted(self.tracks.items()):
            obj = deepcopy(value['object'])
            coasted = identity not in matched
            # An object observed at the image edge is allowed to leave promptly.
            if coasted and (obj['bbox'][0] <= .002 or obj['bbox'][2] >= .998 or obj['bbox'][3] >= .998):
                continue
            obj.update(track_id=identity, coasted=coasted)
            output.append(obj)
        return output

    def _seen(self, identity, obj, at):
        self.tracks[identity] = dict(object=deepcopy(obj), seen=at)
