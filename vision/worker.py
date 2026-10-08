"""Local JSON-lines worker: one model, separate ByteTrack state per camera/session."""
import base64
from collections import Counter
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from vision.stability import TrackStabilizer, distinct_box_indices

os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path.cwd() / 'work' / 'yolo-settings'))


def main():
    # Ultralytics logs must never enter the JSON transport.
    with redirect_stdout(sys.stderr):
        import cv2
        import numpy as np
        import torch
        from ultralytics import YOLO
        from ultralytics.trackers.byte_tracker import BYTETracker
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.utils import LOGGER
        LOGGER.setLevel('ERROR')
        torch.set_num_threads(2)
        # Four FFmpeg decoders share the CPU with tracking and the web services.
        # Small JPEG frames do not benefit from OpenCV's own large thread pool.
        cv2.setNumThreads(1)
        path = Path(sys.argv[1]).resolve()
        if not path.is_file():
            raise FileNotFoundError('Configured model is missing')
        model = YOLO(str(path))
        expected = ['car', 'motorcycle', 'bus', 'truck', 'ambulance', 'fire_truck']
        if [model.names[i] for i in range(len(model.names))] != expected:
            raise ValueError('Expected the six-class SIGAP model')
        device = '0' if torch.cuda.is_available() else 'cpu'
        trackers = {}
        diagnostics = os.environ.get('SIGAP_VISION_DIAGNOSTICS') == '1'
        window_started, window, completed = time.perf_counter(), [], 0
        print('YOLO26s + ByteTrack ready on ' + device, file=sys.stderr, flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            started = time.perf_counter()
            frame = cv2.imdecode(np.frombuffer(base64.b64decode(request['jpeg']), dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError('Invalid JPEG')
            decoded_at = time.perf_counter()
            key = (request['direction'], request['session'])
            if key not in trackers:
                # Remove the old session of this camera without disturbing other cameras.
                trackers = {k: v for k, v in trackers.items() if k[0] != key[0]}
                args = SimpleNamespace(track_high_thresh=.25, track_low_thresh=.1,
                    new_track_thresh=.35, track_buffer=2 * request['fps'], match_thresh=.8, fuse_score=True)
                trackers[key] = dict(tracker=BYTETracker(args), counter=0, last_frame=None, stable=TrackStabilizer())
            state = trackers[key]
            tracker = state['tracker']
            gap = request['frame_id'] - state['last_frame'] if state['last_frame'] is not None else 1
            if gap <= 0:
                raise ValueError('Frame must advance within a camera session')
            if gap > 2 * request['fps']:
                tracker.reset()
                state['stable'].tracks.clear()
                state['stable'].aliases.clear()
                state['stable'].last_time = None
            else:
                # Expire lost tracks according to source time, including skipped frames.
                tracker.frame_id += gap - 1
            BaseTrack._count = state['counter']
            predict_started = time.perf_counter()
            with redirect_stdout(sys.stderr):
                result = model.predict(frame, imgsz=640, conf=.1, device=device, verbose=False)[0]
                predicted_at = time.perf_counter()
                boxes = result.boxes.cpu().numpy()
                keep = distinct_box_indices(boxes.xyxy, boxes.cls, boxes.conf, expected)
                rows = tracker.update(boxes[keep], frame)
            tracked_at = time.perf_counter()
            state['counter'], state['last_frame'] = BaseTrack._count, request['frame_id']
            height, width = frame.shape[:2]
            objects = []
            for row in rows:
                x1, y1, x2, y2, track_id, score, class_id = row[:7]
                name = expected[int(class_id)]
                if not np.isfinite(row[:7]).all():
                    continue
                track_id = int(track_id)
                objects.append(dict(track_id=track_id, class_name=name, confidence=float(score),
                    bbox=[float(max(0, min(1, v))) for v in (x1/width, y1/height, x2/width, y2/height)]))
            objects = state['stable'].update(objects, request['frame_id']/request['fps'])
            for obj in objects:
                track_id, name = obj['track_id'], obj['class_name']
                if request.get('focus_evp') and name not in ('ambulance', 'fire_truck'):
                    continue  # Keep background measurements; only EVP receives an overlay during priority.
                x1,y1,x2,y2 = [v*s for v,s in zip(obj['bbox'], (width,height,width,height))]
                color = ((37 * track_id + 80) % 180 + 60, (67 * track_id) % 180 + 60, (97 * track_id) % 180 + 60)
                if name in ('ambulance', 'fire_truck'):
                    color = (20, 90, 245)
                a, b, c, d = [int(v) for v in (x1, y1, x2, y2)]
                cv2.rectangle(frame, (a, b), (c, d), color, 2)
                text = f'{name} #{request["direction"]}:{track_id}' + (' ~' if obj['coasted'] else '')
                cv2.putText(frame, text, (max(0, a), max(12, b - 4)), cv2.FONT_HERSHEY_SIMPLEX, .36, color, 1, cv2.LINE_AA)
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise ValueError('JPEG encoding failed')
            response = dict(direction=request['direction'], session=request['session'], frame_id=request['frame_id'],
                jpeg=base64.b64encode(encoded).decode('ascii'), tracks=objects,
                processing_ms=(time.perf_counter() - started) * 1000, device=device)
            if diagnostics:
                timings = dict(decode=(decoded_at-started)*1000,
                    predict=(predicted_at-predict_started)*1000,
                    track=(tracked_at-predicted_at)*1000,
                    draw_encode=(time.perf_counter()-tracked_at)*1000)
                response['timings_ms'] = timings
                completed += 1
                # Exclude cold startup, then aggregate to stderr; stdout remains JSON transport.
                if completed <= 4:
                    window_started = time.perf_counter()
                else:
                    window.append((request['direction'], response['processing_ms'], timings))
                    elapsed = time.perf_counter()-window_started
                    if elapsed >= 10:
                        counts = Counter(row[0] for row in window)
                        total = sorted(row[1] for row in window)
                        profile = dict(samples=len(window), seconds=round(elapsed,2),
                            camera_fps={d:round(counts[d]/elapsed,2) for d in 'UTSB'},
                            processing_mean_ms=round(sum(total)/len(total),2),
                            processing_p95_ms=round(total[int((len(total)-1)*.95)],2),
                            stage_mean_ms={k:round(sum(row[2][k] for row in window)/len(window),2) for k in timings},
                            device=device, opencv_threads=cv2.getNumThreads(), torch_threads=torch.get_num_threads())
                        print('[vision-performance] '+json.dumps(profile,separators=(',',':')),file=sys.stderr,flush=True)
                        window_started, window = time.perf_counter(), []
        except Exception as exc:
            print(type(exc).__name__, file=sys.stderr, flush=True)
            response = dict(error=type(exc).__name__)
        print(json.dumps(response, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
