"""Opt-in integration on a dedicated PostgreSQL database, never the operator database."""
import os
import secrets
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.orm import Session

from backend.app.accounts import create_operator
from backend.app.auth import COOKIE_NAME
from backend.app.database import check_database, make_engine
from backend.app.main import create_app
from backend.app.models import OperatorAccount, OperatorSession
from backend.app.settings import Settings
from contracts.configuration import PROJECT_ROOT


@pytest.mark.postgres
def test_real_postgres_migration_login_and_revocation(monkeypatch):
    database = os.getenv('SIGAP_TEST_POSTGRES_DB')
    password = os.getenv('SIGAP_TEST_POSTGRES_PASSWORD')
    if not database or not password:
        pytest.skip('Siapkan database khusus *_test dan SIGAP_TEST_POSTGRES_DB/PASSWORD.')
    if not database.endswith('_test'):
        pytest.fail('Database pengujian harus berakhiran _test.')
    values = {
        'POSTGRES_DB': database, 'POSTGRES_PASSWORD': password,
        'POSTGRES_USER': os.getenv('SIGAP_TEST_POSTGRES_USER', 'sigap'),
        'SIGAP_DB_HOST': os.getenv('SIGAP_TEST_POSTGRES_HOST', '127.0.0.1'),
        'SIGAP_DB_PORT': os.getenv('SIGAP_TEST_POSTGRES_PORT', '5432'),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    config = Config(str(PROJECT_ROOT / 'alembic.ini'))
    command.upgrade(config, 'head')
    command.check(config)
    engine = make_engine(Settings())
    account_id = None
    try:
        report = check_database(engine)
        assert report.status == 'reachable' and report.schema_status == 'current'
        columns = {column['name'] for column in inspect(engine).get_columns('operator_accounts')}
        assert 'password_hash' in columns and 'password' not in columns
        assert 'operator_sessions' in inspect(engine).get_table_names()
        username = f'pg.test.{uuid4().hex}'
        account_password = secrets.token_urlsafe(24)
        with Session(engine) as db, db.begin():
            account = create_operator(db, username, 'PostgreSQL Integration', account_password)
            account_id = account.id
        origin = {'Origin': 'http://127.0.0.1:5173', 'X-SIGAP-Request': '1'}
        with TestClient(create_app(Settings())) as client:
            assert client.get('/api/health').status_code == 401
            assert client.post('/api/auth/login', headers=origin, json={'username': username, 'password': 'incorrect'}).status_code == 401
            login = client.post('/api/auth/login', headers=origin, json={'username': username, 'password': account_password})
            assert login.status_code == 200
            raw = client.cookies[COOKIE_NAME]
            assert client.get('/api/health').status_code == 200
            assert client.get('/api/configuration').status_code == 200
            # Recreating the backend still sees the database-backed session.
            with TestClient(create_app(Settings())) as restarted:
                assert restarted.get('/api/auth/session', headers={'Cookie': f'{COOKIE_NAME}={raw}'}).status_code == 200
            with Session(engine) as db:
                saved = db.scalar(select(OperatorSession).where(OperatorSession.operator_id == account_id))
                assert saved is not None and saved.token_hash != raw
                assert saved.expires_at.tzinfo is not None
            assert client.post('/api/auth/logout', headers={**origin, 'X-CSRF-Token': login.json()['csrf_token']}).status_code == 204
            assert client.get('/api/configuration', headers={'Cookie': f'{COOKIE_NAME}={raw}'}).status_code == 401
            login = client.post('/api/auth/login', headers=origin, json={'username': username, 'password': account_password})
            assert login.status_code == 200
            with Session(engine) as db, db.begin():
                db.get(OperatorAccount, account_id).is_active = False
            assert client.get('/api/configuration').status_code == 401
    finally:
        if account_id is not None:
            with Session(engine) as db, db.begin():
                db.execute(delete(OperatorAccount).where(OperatorAccount.id == account_id))
            with engine.connect() as connection:
                assert connection.execute(text('SELECT count(*) FROM operator_sessions WHERE operator_id = :id'), {'id': account_id}).scalar_one() == 0
        engine.dispose()
