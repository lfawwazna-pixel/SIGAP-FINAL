"""Scripted test sender, explicitly labelled integration_test (not YOLO/adaptive logic)."""
import argparse
from datetime import datetime, timedelta, timezone
import os
import time
from uuid import uuid4

import httpx


def run(url, scenario):
    key = os.environ['SIGAP_CONTROL_API_KEY']
    sender = str(uuid4())
    sequences = dict(observe=0, heartbeat=0, plan=0)
    activated = False
    first_adaptive = None
    frozen_at = None
    with httpx.Client(base_url=url, timeout=2, trust_env=False, headers={'Authorization': f'Bearer {key}'}) as client:
        initial = client.get('/control').json()
        if not initial['allow_test_source'] or initial['policy']['minimum_green_seconds'] != 1:
            raise RuntimeError('Refusing to send test commands to a non-lab controller.')
        run_id = initial['atcs_run_id']

        def submit(action, **values):
            at = datetime.now(timezone.utc)
            body = dict(request_id=str(uuid4()), atcs_run_id=run_id, sender_id=sender, action=action,
                        issued_at=at.isoformat(), expires_at=(at+timedelta(seconds=3)).isoformat())
            if action in sequences:
                sequences[action] += 1
                body['sequence'] = sequences[action]
            response = client.post('/control/commands', json={**body, **values})
            response.raise_for_status()
            return response.json()

        while True:
            at = datetime.now(timezone.utc)
            status = client.get('/control').json()
            if status['atcs_run_id'] != run_id:
                raise RuntimeError('Lab ATCS restarted; sender must be explicitly restarted.')
            if status['state'] == 'adaptive' and first_adaptive is None:
                first_adaptive = time.monotonic()
            if scenario == 'data-freeze' and first_adaptive is not None and time.monotonic()-first_adaptive >= 1:
                frozen_at = frozen_at or at
            observed = (frozen_at or at).isoformat()
            submit('observe', source='integration_test', observations={d: dict(observed_at=observed, usable=True) for d in 'UTSB'})
            status = client.get('/control').json()
            if not activated and status['ready']:
                submit('activate', expected_revision=status['revision'])
                activated = True  # No automatic reacquisition after any fallback.
                status = client.get('/control').json()
            if status['session_id']:
                session = status['session_id']
                # A revocation can occur between the read and POST; it is expected during a fault test.
                try:
                    submit('heartbeat', session_id=session)
                    if status['pending_request_id'] is None:
                        submit('plan', session_id=session, approach='T', green_seconds=2,
                               plan_valid_until=(at+timedelta(seconds=60)).isoformat())
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 409:
                        raise
            time.sleep(.2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Internal source for the isolated integration lab.')
    parser.add_argument('--url', required=True)
    parser.add_argument('--scenario', choices=['sender-stop', 'data-freeze', 'release'], required=True)
    args = parser.parse_args()
    run(args.url, args.scenario)
