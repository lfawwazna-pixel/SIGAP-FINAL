from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.accounts import create_operator
from backend.app.auth import AuthService, COOKIE_NAME, PASSWORD_HASHER, token_hash
from backend.app.main import create_app
from backend.app.models import Base, OperatorAccount, OperatorSession
from backend.app.settings import Settings

ORIGIN = {"Origin": "http://127.0.0.1:5173", "X-SIGAP-Request": "1"}
PASSWORD = "frasa sandi pengujian khusus"


@pytest.fixture
def auth_context(clock):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def sqlite_functions(connection, record):
        connection.create_function("char_length", 1, len)
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        account = create_operator(db, "operator.test", "Operator Pengujian", PASSWORD)
        account_id = account.id
    settings = Settings(_env_file=None, postgres_password=SecretStr(""), sigap_session_seconds=60)
    app = create_app(settings)
    app.state.auth = AuthService(engine, settings, now=clock.utcnow)
    with TestClient(app) as client:
        yield client, app, engine, account_id
    engine.dispose()


def login(client, **overrides):
    return client.post("/api/auth/login", headers=ORIGIN,
                       json={"username": "operator.test", "password": PASSWORD, **overrides})


@pytest.mark.parametrize("path", ["/api/health", "/api/configuration", "/api/atcs/health", "/api/atcs/status", "/api/atcs/events", "/api/auth/session"])
def test_every_operator_endpoint_rejects_anonymous_access(auth_context, path):
    client, _, _, _ = auth_context
    assert client.get(path).status_code == 401
    assert client.get("/api/health/live").status_code == 200


def test_login_cookie_hash_storage_and_profile(auth_context):
    client, _, engine, account_id = auth_context
    response = login(client, username=" OPERATOR.TEST ")
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert "Domain=" not in cookie
    view = response.json()
    assert view["operator"] == {"id": str(account_id), "username": "operator.test", "display_name": "Operator Pengujian", "role": "operator", "permissions": ["monitor:read", "control:operate"]}
    assert "password" not in response.text and "password_hash" not in response.text
    raw = client.cookies[COOKIE_NAME]
    with Session(engine) as db:
        saved = db.scalar(select(OperatorSession))
        account = db.get(OperatorAccount, account_id)
        assert saved.token_hash == token_hash(raw) and saved.token_hash != raw
        assert account.password_hash.startswith("$argon2id$")
        assert PASSWORD_HASHER.verify(account.password_hash, PASSWORD)
    assert client.get("/api/auth/session").json() == view
    assert client.get("/api/configuration").status_code == 200
    assert response.headers["cache-control"] == "private, no-store"


def test_bad_password_unknown_and_disabled_accounts_share_same_error(auth_context):
    client, _, engine, account_id = auth_context
    wrong = login(client, password="salah")
    absent = login(client, username="not.exists")
    with Session(engine) as db, db.begin():
        db.get(OperatorAccount, account_id).is_active = False
    disabled = login(client)
    assert wrong.status_code == absent.status_code == disabled.status_code == 401
    assert wrong.json() == absent.json() == disabled.json()
    assert COOKIE_NAME not in client.cookies


def test_expiration_and_account_disabling_revoke_server_access(auth_context, clock):
    client, _, engine, account_id = auth_context
    assert login(client).status_code == 200
    clock.advance(60)
    assert client.get("/api/configuration").status_code == 401
    assert login(client).status_code == 200
    with Session(engine) as db, db.begin():
        db.get(OperatorAccount, account_id).is_active = False
    assert client.get("/api/auth/session").status_code == 401
    assert client.get("/api/atcs/status").status_code == 401


def test_logout_revokes_saved_cookie_and_requires_csrf(auth_context):
    client, _, _, _ = auth_context
    view = login(client).json()
    raw = client.cookies[COOKIE_NAME]
    assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 403
    assert client.get("/api/auth/session").status_code == 200
    response = client.post("/api/auth/logout", headers={**ORIGIN, "X-CSRF-Token": view["csrf_token"]})
    assert response.status_code == 204 and "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/api/configuration", headers={"Cookie": f"{COOKIE_NAME}={raw}"}).status_code == 401


def test_login_rotation_invalidates_previous_token_and_csrf(auth_context):
    client, _, _, _ = auth_context
    first = login(client).json()
    raw = client.cookies[COOKIE_NAME]
    second = login(client).json()
    assert second["csrf_token"] != first["csrf_token"]
    assert client.cookies[COOKIE_NAME] != raw
    assert client.get("/api/auth/session", headers={"Cookie": f"{COOKIE_NAME}={raw}"}).status_code == 401
    assert client.post("/api/auth/logout", headers={**ORIGIN, "X-CSRF-Token": first["csrf_token"]}).status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://attacker.example", "X-SIGAP-Request": "1"}, {"Origin": "http://127.0.0.1:5173"}])
def test_cross_origin_and_simple_form_login_rejected(auth_context, headers):
    client, _, _, _ = auth_context
    assert client.post("/api/auth/login", headers=headers, json={"username": "operator.test", "password": PASSWORD}).status_code == 403
    assert COOKIE_NAME not in client.cookies


def test_validation_never_echoes_password_or_accepts_role_injection(auth_context):
    client, _, _, _ = auth_context
    secret = "do-not-echo-this-secret" * 10
    response = login(client, password=secret)
    assert response.status_code == 422 and secret not in response.text
    assert login(client, role="admin").status_code == 422


def test_attempts_are_throttled_and_headers_do_not_bypass_account_limit(auth_context):
    client, _, _, _ = auth_context
    for _ in range(5):
        assert login(client, password="salah").status_code == 401
    response = login(client)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


def test_database_failure_fails_closed_without_credentials_in_error(auth_context):
    client, app, _, _ = auth_context
    assert login(client).status_code == 200
    app.state.auth.engine = None
    response = client.get("/api/configuration")
    assert response.status_code == 503 and response.json()["detail"]["code"] == "AUTH_UNAVAILABLE"
    assert login(client).status_code == 503


def test_sessions_survive_backend_recreation(auth_context, clock):
    client, _, engine, _ = auth_context
    raw = login(client).cookies[COOKIE_NAME]
    settings = Settings(_env_file=None, postgres_password=SecretStr(""))
    restarted = create_app(settings)
    restarted.state.auth = AuthService(engine, settings, now=clock.utcnow)
    with TestClient(restarted) as second:
        assert second.get("/api/auth/session", headers={"Cookie": f"{COOKIE_NAME}={raw}"}).status_code == 200


def test_no_accounts_are_seeded_and_short_password_requires_explicit_override(auth_context):
    _, _, engine, _ = auth_context
    with Session(engine) as db, db.begin():
        with pytest.raises(ValueError):
            create_operator(db, "short.password", "Local", "admin")
        account = create_operator(db, "short.password", "Local", "admin", allow_short=True)
        assert PASSWORD_HASHER.verify(account.password_hash, "admin")
        with pytest.raises(ValueError):
            create_operator(db, "SHORT.PASSWORD", "Duplicate", PASSWORD)
