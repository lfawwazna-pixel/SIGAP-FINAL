from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OperatorAccount(Base):
    __tablename__ = "operator_accounts"
    __table_args__ = (CheckConstraint("char_length(password_hash) > 0", name="ck_operator_hash_not_empty"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("uq_operator_username_lower", func.lower(OperatorAccount.username), unique=True)


class OperatorSession(Base):
    __tablename__ = "operator_sessions"
    __table_args__ = (CheckConstraint("expires_at > created_at", name="ck_session_expiry"),)
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("operator_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
