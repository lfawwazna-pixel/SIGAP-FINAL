from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from backend.app.settings import Settings
from contracts.models import DatabaseCheck

EXPECTED_REVISION = "0002_operator_sessions"


def make_engine(settings: Settings) -> Engine | None:
    url = settings.database_url()
    if url is None:
        return None
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2, pool_timeout=3,
                         connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
                         hide_parameters=True)


def check_database(engine: Engine | None) -> DatabaseCheck:
    if engine is None:
        return DatabaseCheck(status="not_configured", schema_status="unknown")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = connection.execute(text(
                "SELECT to_regclass('public.alembic_version'), to_regclass('public.operator_accounts'), to_regclass('public.operator_sessions')"
            )).one()
            current = False
            if all(tables):
                revisions = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
                current = revisions == {EXPECTED_REVISION}
            return DatabaseCheck(status="reachable", schema_status="current" if current else "missing_or_outdated")
    except (SQLAlchemyError, OSError):
        # Connection strings and driver exceptions may contain credentials.
        return DatabaseCheck(status="unavailable", schema_status="unknown")
