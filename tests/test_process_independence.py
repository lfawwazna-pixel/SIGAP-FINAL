"""Real processes and HTTP, with a separate short-cycle fixture (not the baseline)."""
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from contracts.configuration import PROJECT_ROOT, load_config


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_for_service(client, url, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Test service exited before startup; inspect its pytest temporary log.")
        try:
            response = client.get(url)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(.05)
    raise AssertionError(f"Test service startup timed out: {url}")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.process
def test_atcs_keeps_ticking_after_backend_stops_and_restarts_with_new_session(tmp_path):
    fixture = load_config().model_dump()
    fixture["fixed_time"].update(green_seconds=dict.fromkeys(["U", "T", "S", "B"], 1),
                                 yellow_seconds=1, all_red_min_seconds=1, nominal_cycle_seconds=12)
    config_path = tmp_path / "short-cycle.json"
    config_path.write_text(json.dumps(fixture), encoding="utf-8")
    atcs_port, backend_port = free_port(), free_port()
    while backend_port == atcs_port:
        backend_port = free_port()
    atcs_url, backend_url = f"http://127.0.0.1:{atcs_port}", f"http://127.0.0.1:{backend_port}"
    environment = {**os.environ, "SIGAP_CONFIG_PATH": str(config_path), "SIGAP_ATCS_BASE_URL": atcs_url,
                   "POSTGRES_PASSWORD": "", "PYTHONUNBUFFERED": "1"}
    processes = []
    handles = []

    def start(module, port, label):
        handle = (tmp_path / f"{label}.log").open("wb")
        handles.append(handle)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", module, "--host", "127.0.0.1", "--port", str(port),
             "--workers", "1", "--no-access-log"], cwd=PROJECT_ROOT, env=environment,
            stdout=handle, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        processes.append(process)
        return process

    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            atcs = start("atcs_simulator.app.main:app", atcs_port, "atcs")
            wait_for_service(client, f"{atcs_url}/status", atcs)
            backend = start("backend.app.main:app", backend_port, "backend")
            wait_for_service(client, f"{backend_url}/api/health/live", backend)
            via_backend = client.get(f"{backend_url}/api/atcs/status")
            assert via_backend.status_code == 401
            assert client.get(f"{backend_url}/api/health").status_code == 401
            before = client.get(f"{atcs_url}/status").json()
            before_traffic = client.get(f"{atcs_url}/traffic").json()
            before_events = client.get(f"{atcs_url}/events").json()
            stop(backend)
            # No browser and no status polling during this interval.
            time.sleep(4.2)
            after = client.get(f"{atcs_url}/status").json()
            assert after["run_id"] == before["run_id"]
            assert after["simulation_time_seconds"] - before["simulation_time_seconds"] >= 4
            assert after["sequence_number"] > before["sequence_number"]
            after_traffic = client.get(f"{atcs_url}/traffic").json()
            assert after_traffic['run_id'] == before_traffic['run_id']
            assert after_traffic['traffic_sequence'] > before_traffic['traffic_sequence']
            assert after_traffic['time_seconds'] > before_traffic['time_seconds']
            events = client.get(f"{atcs_url}/events", params={"after": before_events["latest_sequence"],
                                                           "run_id": before["run_id"]}).json()
            assert sum(event["event_type"] == "phase_changed" for event in events["events"]) >= 3
            stop(atcs)
            restarted = start("atcs_simulator.app.main:app", atcs_port, "atcs-restarted")
            new_status = wait_for_service(client, f"{atcs_url}/status", restarted)
            assert new_status["run_id"] != before["run_id"]
            assert new_status["simulation_time_seconds"] < 3
            reset = client.get(f"{atcs_url}/events", params={"run_id": before["run_id"], "after": 999}).json()
            assert reset["run_changed"] and reset["events"][0]["sequence_number"] == 1
    finally:
        for process in reversed(processes):
            stop(process)
        for handle in handles:
            handle.close()
