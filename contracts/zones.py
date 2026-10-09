"""Shared zone admission for worker overlays and server measurements."""
def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def inside(x, y, polygon):
    crossing = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay, bx, by = field(a, 'x'), field(a, 'y'), field(b, 'x'), field(b, 'y')
        cross = (bx-ax)*(y-ay)-(by-ay)*(x-ax)
        if abs(cross) <= 1e-10 and min(ax,bx)-1e-10 <= x <= max(ax,bx)+1e-10 and min(ay,by)-1e-10 <= y <= max(ay,by)+1e-10:
            return True
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            crossing = not crossing
    return crossing


def zone_tracks(tracks, calibration):
    if calibration is None:
        return []
    accepted = {}
    for track in tracks:
        x1, _, x2, y = field(track, 'bbox')
        if not any(inside((x1+x2)/2, y, polygon) for polygon in field(calibration, 'lanes').values()):
            continue
        identity = field(track, 'track_id')
        old = accepted.get(identity)
        # A duplicate identity is one vehicle; prefer a current observation.
        def rank(item):
            coasted = item.get('coasted', False) if isinstance(item, dict) else item.coasted
            return (not coasted, field(item, 'confidence'))
        if old is None or rank(track) > rank(old):
            accepted[identity] = track
    return list(accepted.values())
