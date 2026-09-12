"""Dấu vết chống gửi trùng khi admin báo thay đổi lịch chương trình."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ProgramEventNotice(Base):
    """Một revision của một mốc chỉ được tạo một thông báo cho mỗi user."""

    __tablename__ = "program_event_notices"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "program_event_id",
            "revision_hash",
            name="uq_program_event_notice_user_revision",
        ),
        Index("ix_program_event_notice_event_revision", "program_event_id", "revision_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    program_event_id: Mapped[int] = mapped_column(ForeignKey("program_events.id"), index=True)
    revision_hash: Mapped[str] = mapped_column(String(64))
    reminder_id: Mapped[int | None] = mapped_column(
        ForeignKey("reminders.id", ondelete="CASCADE"), unique=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
