"""Sesi operator yang dapat dicabut; tanpa akun/password bawaan."""
from alembic import op
import sqlalchemy as sa

revision = "0002_operator_sessions"
down_revision = "0001_operator_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_operator_username_lower", "operator_accounts", [sa.text("lower(username)")], unique=True)
    op.create_table(
        "operator_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("operator_id", sa.Uuid(as_uuid=True), sa.ForeignKey("operator_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expires_at > created_at", name="ck_session_expiry"),
    )
    op.create_index("ix_operator_sessions_operator_id", "operator_sessions", ["operator_id"])
    op.create_index("ix_operator_sessions_expires_at", "operator_sessions", ["expires_at"])


def downgrade():
    op.drop_table("operator_sessions")
    op.drop_index("uq_operator_username_lower", table_name="operator_accounts")
