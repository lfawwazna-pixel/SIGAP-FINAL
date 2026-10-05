"""Short local smoke benchmark against the exact JSON worker used by SIGAP."""
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import cv2


def main():
    root = Path(__file__).resolve().parents[1]
    samples = root/'work'/'tracking-review'
    cases = dict(U='U-utara.mp4', T='T-timur.mp4', S='S-selatan.mp4', B='B-barat.mp4')
    log = (samples/'local-worker.log').open('wb')
    worker = subprocess.Popen([sys.executable, '-u', '-m', 'vision.worker', str(root/'models'/'sigap_yolo26s'/'best.pt')],
        cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    caps = {d: cv2.VideoCapture(str(samples/f)) for d, f in cases.items()}
    sessions = {d: str(uuid4()) for d in cases}
    times = {d: [] for d in cases}
    identifiers = {d: set() for d in cases}
    started = time.perf_counter()
    try:
        for frame_id in range(1, 9):
            for d, cap in caps.items():
                for _ in range(6):
                    ok, frame = cap.read()
                assert ok
                frame = cv2.resize(frame, (640, round(frame.shape[0]*640/frame.shape[1]/2)*2))
                ok, jpeg = cv2.imencode('.jpg', frame); assert ok
                request = dict(direction=d, session=sessions[d], frame_id=frame_id, fps=5, jpeg=base64.b64encode(jpeg).decode())
                worker.stdin.write((json.dumps(request)+'\n').encode()); worker.stdin.flush()
                result = json.loads(worker.stdout.readline())
                assert not result.get('error'), result
                assert (result['direction'], result['session'], result['frame_id']) == (d, sessions[d], frame_id)
                ids = [t['track_id'] for t in result['tracks']]
                assert len(ids) == len(set(ids)), 'Duplicate camera IDs'
                identifiers[d].update(ids)
                if frame_id > 1:
                    times[d].append(result['processing_ms'])
                if frame_id == 8:
                    (samples/f'{d}_local_tracking.jpg').write_bytes(base64.b64decode(result['jpeg']))
        report = dict(device=result['device'], samples_per_camera=7, preview_fps=5,
            note='Warm processing throughput; four cameras share one model. Not a GPU T4 result.',
            total_wall_seconds=round(time.perf_counter()-started,2),
            cameras={d: dict(processing_fps=round(1000/(sum(t)/len(t)),2), observed_track_ids=len(identifiers[d])) for d,t in times.items()})
        (samples/'local_benchmark.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        worker.stdin.close(); worker.wait(timeout=10); log.close()
        for cap in caps.values(): cap.release()


if __name__ == '__main__':
    main()
