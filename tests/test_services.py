import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from atcs_simulator.app.main import create_app as create_atcs
from backend.app.main import create_app as create_protected_backend
from backend.app.auth import require_operator
from backend.app.database import check_database
from backend.app.settings import Settings
from contracts.models import AtcsStatus, DatabaseCheck, Health


def settings(**kwargs):
    return Settings(_env_file=None, postgres_password=SecretStr(""), **kwargs)


def create_backend(configuration):
    app = create_protected_backend(configuration)
    # These tests isolate health/proxy behavior. Real access checks are in test_auth.py.
    app.dependency_overrides[require_operator] = lambda: object()
    return app


def test_atcs_starts_fixed_time_with_all_red(clock):
    with TestClient(create_atcs(clock=clock)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["foundation_ready"] is True
        assert health.json()["database"]["status"] == "not_required"
        assert health.json()["capabilities"]["phase_engine"] == "running"
        assert health.json()["stage"] == "4"
        response = client.get("/status")
        status = AtcsStatus.model_validate(response.json())
        assert status.availability == "available" and status.run_id
        assert status.phase == "all_red" and status.active_approach is None
        assert status.remaining_seconds == 2
        assert status.conflict_area.source == "provider"
        assert response.headers["cache-control"] == "no-store"
        assert status.observed_at.tzinfo is not None


def test_unimplemented_phase_cannot_report_fake_countdown():
    with TestClient(create_atcs()) as client:
        data = client.get("/status").json()
    data["availability"] = "not_implemented"
    data["remaining_seconds"] = 0
    with pytest.raises(ValidationError):
        AtcsStatus.model_validate(data)


@pytest.mark.parametrize("database,code,ready", [
    (DatabaseCheck(status="not_configured", schema_status="unknown"), 503, False),
    (DatabaseCheck(status="unavailable", schema_status="unknown"), 503, False),
    (DatabaseCheck(status="reachable", schema_status="missing_or_outdated"), 503, False),
    (DatabaseCheck(status="reachable", schema_status="current"), 200, True),
])
def test_backend_liveness_and_database_readiness_are_distinct(database, code, ready):
    app = create_backend(settings())
    # Isolated readiness scenarios; this is not a real database integration test.
    app.state.database_check = lambda: database
    with TestClient(app) as client:
        assert client.get("/api/health/live").status_code == 200
        response = client.get("/api/health")
        assert response.status_code == code
        report = Health.model_validate(response.json())
        assert report.liveness == "alive"
        assert report.foundation_ready is ready
        assert report.capabilities.authentication == ("available" if ready else "unavailable")
        assert report.capabilities.override == "unavailable"
        assert report.capabilities.ai == "not_implemented"


def test_missing_credentials_do_not_claim_database_connection():
    assert check_database(None).status == "not_configured"
    with TestClient(create_backend(settings())) as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json()["database"]["status"] == "not_configured"


def test_services_read_identical_configuration():
    with TestClient(create_backend(settings())) as backend, TestClient(create_atcs()) as atcs:
        assert backend.get("/api/configuration").json() == atcs.get("/configuration").json()


@pytest.mark.parametrize("mode", ["disconnected", "malformed", "wrong_service", "wrong_intersection"])
def test_atcs_proxy_rejects_untrustworthy_upstream(mode):
    app = create_backend(settings())
    with TestClient(create_atcs()) as atcs:
        upstream_health = atcs.get("/health").json()
        upstream_status = atcs.get("/status").json()

    def handler(request):
        if mode == "disconnected":
            raise httpx.ConnectError("credential-must-not-leak", request=request)
        if mode == "malformed":
            return httpx.Response(200, json={"liveness": "alive"})
        if mode == "wrong_service":
            return httpx.Response(200, json={**upstream_health, "service": "backend"})
        return httpx.Response(200, json={**upstream_status, "intersection_id": "WRONG"})

    with TestClient(app) as client:
        client.portal.call(app.state.atcs_client.aclose)
        app.state.atcs_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://atcs")
        endpoint = "status" if mode == "wrong_intersection" else "health"
        response = client.get(f"/api/atcs/{endpoint}")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "ATCS_UNAVAILABLE"
        assert "credential-must-not-leak" not in response.text


def test_proxy_preserves_atcs_status_without_inventing_state(clock):
    app = create_backend(settings())
    atcs_app = create_atcs(clock=clock)
    with TestClient(atcs_app) as atcs, TestClient(app) as client:
        client.portal.call(app.state.atcs_client.aclose)
        app.state.atcs_client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=atcs.get(request.url.path).json())), base_url="http://atcs")
        assert client.get("/api/atcs/health").json()["service"] == "atcs"
        response = client.get("/api/atcs/status")
        assert response.status_code == 200
        assert response.json()["remaining_seconds"] == 2
        assert response.json()["run_id"] == atcs.get("/status").json()["run_id"]
        assert client.get("/api/atcs/events").json()["events"][0]["event_type"] == "service_started"


def test_atcs_fault_is_distinct_from_api_liveness_and_proxy_keeps_it(clock):
    atcs_app = create_atcs(clock=clock)
    backend = create_backend(settings())
    with TestClient(atcs_app) as atcs, TestClient(backend) as client:
        async def fault():
            atcs_app.state.runtime.engine.end(at=clock.utcnow(), fault=True)
        atcs.portal.call(fault)
        assert atcs.get("/health/live").status_code == 200
        health = atcs.get("/health")
        assert health.status_code == 503
        assert health.json()["capabilities"]["phase_engine"] == "faulted"
        def handler(request):
            response = atcs.get(request.url.path)
            return httpx.Response(response.status_code, json=response.json())
        client.portal.call(backend.state.atcs_client.aclose)
        backend.state.atcs_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://atcs")
        assert client.get("/api/atcs/health").status_code == 503
        status = client.get("/api/atcs/status")
        assert status.status_code == 503 and status.json()["engine_state"] == "faulted"


def test_event_pagination_validation_and_restart(clock):
    app = create_atcs(clock=clock)
    with TestClient(app) as client:
        first = client.get("/events").json()
        assert first["events"][0]["event_type"] == "service_started"
        assert client.get("/events?after=-1").status_code == 422
        assert client.get("/events?limit=501").status_code == 422
        assert client.get("/events?after=999").status_code == 400
        assert client.get("/events?after=1").json()["events"] == []
    with TestClient(app) as client:
        restarted = client.get("/events", params={"run_id": first["run_id"], "after": 999}).json()
        assert restarted["run_changed"] and restarted["run_id"] != first["run_id"]
        assert restarted["events"][0]["sequence_number"] == 1
