from io import StringIO

from alembic import command
from alembic.config import Config

from contracts.configuration import PROJECT_ROOT


def test_migration_compiles_to_postgres_sql_without_seeding_accounts(monkeypatch):
    # Only SQL generation. This does not connect to PostgreSQL.
    monkeypatch.setenv("POSTGRES_PASSWORD", "unused-offline-value")
    output = StringIO()
    config = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE operator_accounts" in sql
    assert "password_hash VARCHAR(255) NOT NULL" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "INSERT INTO operator_accounts" not in sql
    assert "0001_operator_accounts" in sql
