"""Explicit, revocable grants from an application user to source scopes."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class SourceScopeAccess(Base):
    """A deny-by-default grant for one user and one source scope.

    Access is intentionally separate from ``SourceScope.tier``: tier describes
    source reliability, while this table describes who may read the scope.
    Rows are revoked/expired instead of deleted so an audit trail remains.
    """

    __tablename__ = "source_scope_access"
    __table_args__ = (
        Index("ix_scope_access_active_user", "user_id", "status", "valid_to"),
        Index("ix_scope_access_scope", "scope_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("source_scopes.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="confirmed", index=True)
    granted_by: Mapped[str | None] = mapped_column(String(128), default=None)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
