"""Bounded worker transport. Raw video and ATCS stay available on inference failure."""
import asyncio
import base64
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from contracts.configuration import PROJECT_ROOT
from contracts.video import TrackedVehicle


class VisionWorker:
    def __init__(self, settings):
        self.enabled = settings.sigap_yolo_enabled
        self.python = settings.sigap_vision_python or sys.executable
        self.model = Path(settings.sigap_yolo_model).resolve()
        self.fps = 5  # Matches the shared decoder; buffer duration is two seconds.
        self.lock = asyncio.Lock()
        self.process = None
        self.retry_after = 0.0
        self.message = 'YOLO belum diaktifkan.' if not self.enabled else 'YOLO siap dimulai saat video berjalan.'

    async def close(self):
        process, self.process = self.process, None
        if process:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
            # Drain the pipes as well as waiting for the process. On Windows,
            # wait() alone can leave pipe transports open after the loop stops.
            with suppress(BrokenPipeError, ConnectionResetError):
                await process.communicate()
            await process.wait()

    async def infer(self, direction, session, frame_id, jpeg, captured=None, latest=None):
        if not self.enabled or time.monotonic() < self.retry_after:
            return None
        async with self.lock:
            position = None
            if latest is not None:
                sample = latest()
                if sample is None:
                    return None
                frame_id, jpeg, captured, position = sample
            if time.monotonic() < self.retry_after or (captured is not None and time.monotonic() - captured > 3):
                return None
            try:
                if not self.model.is_file():
                    raise FileNotFoundError('Model belum tersedia.')
                if self.process is None or self.process.returncode is not None:
                    logs = PROJECT_ROOT / 'work' / 'runtime'
                    logs.mkdir(parents=True, exist_ok=True)
                    with (logs / 'vision.log').open('ab') as log:
                        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
                        self.process = await asyncio.create_subprocess_exec(self.python, '-u', '-m', 'vision.worker',
                            str(self.model), cwd=PROJECT_ROOT, stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE, stderr=log, limit=4_000_000, **flags)
                payload = dict(direction=direction, session=str(session), frame_id=frame_id, fps=self.fps,
                    jpeg=base64.b64encode(jpeg).decode('ascii'))
                self.process.stdin.write((json.dumps(payload) + '\n').encode())
                await self.process.stdin.drain()
                # Cold model startup can take longer than subsequent inference.
                line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
                result = json.loads(line)
                if result.get('error') or (result.get('direction'), result.get('session'), result.get('frame_id')) != (direction, str(session), frame_id):
                    raise ValueError('Identitas hasil tracking tidak cocok.')
                result['tracks'] = [TrackedVehicle.model_validate(t) for t in result['tracks']]
                result['jpeg'] = base64.b64decode(result['jpeg'], validate=True)
                if not result['jpeg'].startswith(b'\xff\xd8'):
                    raise ValueError('Hasil frame tidak valid.')
                self.message = 'YOLO + ByteTrack berjalan.'
                result.update(input_jpeg=jpeg, input_frame_id=frame_id,
                              input_captured=captured, input_position=position)
                return result
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception:
                self.message = 'Tracking terganggu. Video asli tetap tersedia; periksa log vision.'
                self.retry_after = time.monotonic() + 10
                await self.close()
                return None
