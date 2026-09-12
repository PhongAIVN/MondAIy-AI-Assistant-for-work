from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ChannelNotificationDelivery(Base):
    """Receipt giao reminder trên một kênh ngoài extension.

    Extension giữ bảng ``notification_deliveries`` hiện có để không làm migration
    phá dữ liệu pilot. Kênh mới dùng bảng này và dedupe theo đúng channel.
    """

    __tablename__ = "channel_notification_deliveries"
    __table_args__ = (
        UniqueConstraint("channel", "reminder_id", name="uq_channel_delivery_channel_reminder"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), default=None)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ChannelUpdateReceipt(Base):
    """Claim update webhook trước side effect để provider retry không gửi trùng."""

    __tablename__ = "channel_update_receipts"
    __table_args__ = (UniqueConstraint("channel", "external_update_id", name="uq_channel_update_external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    external_update_id: Mapped[str] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TelegramLinkIntent(Base):
    """Short-lived one-time code used by the bot deep-link connection flow."""

    __tablename__ = "telegram_link_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
