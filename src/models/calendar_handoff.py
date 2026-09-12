from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class CalendarHandoff(Base):
    """1 dòng = 1 task đã sinh sẵn link chuyển sang ứng dụng lịch (.ics/mẫu
    Google Calendar). `opened` phân biệt 'đã xác nhận bản nháp' với 'đã mở
    trong ứng dụng lịch' (FR-065) — không tuyên bố sự kiện đã lưu nếu người
    dùng chưa thật sự mở link."""

    __tablename__ = "calendar_handoffs"
    __table_args__ = (UniqueConstraint("task_id", name="uq_calendar_handoff_task_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    opened: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
