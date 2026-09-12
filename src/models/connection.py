from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

ConnectionProvider = str  # "discord" | "google" | "telegram" | "jira" | "outlook"


class Connection(Base):
    """1 dòng = 1 kết nối dịch vụ ngoài (Discord/Google/Telegram/Jira) của 1 user."""

    __tablename__ = "connections"
    __table_args__ = (
        Index(
            "uq_connection_user_provider_non_google",
            "user_id",
            "provider",
            unique=True,
            sqlite_where=text("provider <> 'google'"),
            postgresql_where=text("provider <> 'google'"),
        ),
        Index(
            "uq_connection_user_google_identity",
            "user_id",
            "provider",
            "provider_user_id",
            unique=True,
            sqlite_where=text("provider = 'google' AND provider_user_id IS NOT NULL"),
            postgresql_where=text("provider = 'google' AND provider_user_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    account_label: Mapped[str | None] = mapped_column(String(255), default=None)
    # Định danh trên chính platform đó (Gmail: email lowercase — không có ID số như Discord),
    # dùng để so sánh is_self khi normalize message.
    provider_user_id: Mapped[str | None] = mapped_column(String(128), default=None)
    # Định danh site cho provider multi-tenant (Jira Cloud: cloudId — bắt
    # buộc trong path mọi lời gọi REST). Generic thay vì đặt tên riêng từng
    # provider vì connector đa site khác sau này cũng cần cột này.
    external_site_id: Mapped[str | None] = mapped_column(String(255), default=None)
    # Text thay vì VARCHAR(2048) — token Jira (JWT) mã hoá xong dài hơn nhiều
    # so với Gmail/Discord, từng vượt 2048 ký tự và bị Postgres từ chối insert.
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    scopes: Mapped[str | None] = mapped_column(String(512), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Gmail connection state machine. Tokens remain encrypted and server-side.
    status: Mapped[str] = mapped_column(String(32), default="connected_pending_sync")
    initial_sync_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    email_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1024), default=None)
