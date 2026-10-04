"""Fondasi akun operator; tidak membuat akun atau password default."""
from alembic import op
import sqlalchemy as sa

revision = "0001_operator_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operator_accounts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_operator_accounts_username"),
        sa.CheckConstraint("char_length(password_hash) > 0", name="ck_operator_hash_not_empty"),
    )


def downgrade():
    op.drop_table("operator_accounts")
