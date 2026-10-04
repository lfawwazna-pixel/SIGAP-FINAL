"""Run with python -m integration_lab --scenario sender-stop|data-freeze|release."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

import httpx

from contracts.configuration import PROJECT_ROOT, load_config


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def run_lab(scenario, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    config = load_config().model_dump()
    config['fixed_time'].update(green_seconds=dict.fromkeys('UTSB', 3), yellow_seconds=1,
                               all_red_min_seconds=1, nominal_cycle_seconds=20)
    path = directory/'lab-intersection.json'
    path.write_text(json.dumps(config), encoding='utf-8')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    key = secrets.token_urlsafe(48)
    env = {**os.environ, 'SIGAP_CONFIG_PATH': str(path.resolve()), 'SIGAP_CONTROL_API_KEY': key,
           'ATCS_ENABLE_TEST_SOURCE': 'true', 'PYTHONUNBUFFERED': '1'}
    processes, logs = [], []

    def spawn(arguments, label):
        log = (directory/f'{label}.log').open('wb')
        logs.append(log)
        process = subprocess.Popen([sys.executable, *arguments], cwd=PROJECT_ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        processes.append(process)
        return process

    def wait_for(client, predicate, timeout=20):
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            if processes[0].poll() is not None:
                raise AssertionError('Lab controller exited. Check atcs.log.')
            try:
                response = client.get('/control')
                if response.status_code == 200 and predicate(response.json()):
                    return response.json()
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise AssertionError('Lab condition timed out. Inspect the saved logs.')

    try:
        spawn(['-m', 'uvicorn', 'integration_lab.controller:factory', '--factory', '--host', '127.0.0.1',
               '--port', str(port), '--workers', '1', '--no-access-log'], 'atcs')
        with httpx.Client(base_url=url, timeout=2, trust_env=False, headers={'Authorization': f'Bearer {key}'}) as client:
            initial = wait_for(client, lambda x: x['available'])
            sender = spawn(['-m', 'integration_lab.sender', '--url', url, '--scenario', scenario], 'sender')
            active = wait_for(client, lambda x: x['state'] == 'adaptive')
            release_id = None
            if scenario == 'sender-stop':
                stop(sender)
                # No browser/backend/GET request drives the next transitions.
                time.sleep(8)
            elif scenario == 'release':
                at = datetime.now(timezone.utc)
                release_id = str(uuid4())
                response = client.post('/control/commands', json=dict(request_id=release_id,
                    action='release', atcs_run_id=active['atcs_run_id'], sender_id=active['sender_id'],
                    session_id=active['session_id'], expected_revision=active['revision'],
                    issued_at=at.isoformat(), expires_at=(at+timedelta(seconds=3)).isoformat()))
                assert response.status_code == 200 and response.json()['outcome'] == 'accepted'
            final = wait_for(client, lambda x: x['state'] == 'fixed_time' and x['fallback_code'] is not None)
            assert final['atcs_run_id'] == initial['atcs_run_id']
            assert final['session_id'] is None and final['activation_required']
            if scenario == 'data-freeze':
                assert sender.poll() is None and final['fallback_code'] == 'DATA_UNUSABLE'
            if scenario == 'release':
                assert final['fallback_code'] == 'OPERATOR_RELEASE'
                assert client.get(f'/control/receipts/{release_id}').json()['outcome'] == 'applied'
            elif scenario == 'sender-stop':
                assert final['fallback_code'] in ('DATA_UNUSABLE', 'HEARTBEAT_LOST')
            before = client.get('/status').json()
            time.sleep(.3)
            after = client.get('/status').json()
            assert after['sequence_number'] > before['sequence_number']
            assert after['mode'] == 'fixed_time'
            # Old owner cannot regain authority by sending a fresh heartbeat.
            at = datetime.now(timezone.utc)
            old = client.post('/control/commands', json=dict(request_id=str(uuid4()), action='heartbeat',
                atcs_run_id=active['atcs_run_id'], sender_id=active['sender_id'], session_id=active['session_id'],
                sequence=99999, issued_at=at.isoformat(), expires_at=(at+timedelta(seconds=3)).isoformat()))
            assert old.status_code == 409 and old.json()['code'] == 'SESSION_REVOKED'
            result = dict(scenario=scenario, result='passed', fallback=final['fallback_code'],
                same_atcs_run=True, old_session_rejected=True, operator_reactivation_required=True,
                isolated_port=port, source='integration_test', field_hardware_connected=False)
            (directory/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
            return result
    finally:
        for process in reversed(processes):
            stop(process)
        for log in logs:
            log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SIGAP–ATCS lab on a temporary isolated port. Main ATCS is untouched.')
    parser.add_argument('--scenario', choices=['sender-stop', 'data-freeze', 'release'], default='sender-stop')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        print(json.dumps(run_lab(args.scenario, args.output), indent=2))
    else:
        with TemporaryDirectory(prefix='sigap-control-lab-') as directory:
            print(json.dumps(run_lab(args.scenario, directory), indent=2))
