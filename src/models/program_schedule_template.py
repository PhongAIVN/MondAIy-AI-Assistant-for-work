"""Mẫu lịch lặp theo cohort do quản trị viên phát hành."""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ProgramScheduleTemplate(Base):
    """Một khung giờ lặp, dùng để sinh các mốc lịch chương trình."""

    __tablename__ = "program_schedule_templates"
    __table_args__ = (Index("ix_program_template_cohort_active", "cohort_slug", "active"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_slug: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    host: Mapped[str | None] = mapped_column(String(255), default=None)
    location_url: Mapped[str | None] = mapped_column(String(512), default=None)
    event_type: Mapped[str] = mapped_column(String(32), default="custom")
    # Danh sách thứ trong tuần, phân tách bằng dấu phẩy: 0=thứ Hai .. 6=Chủ nhật.
    weekdays: Mapped[str] = mapped_column(String(32))
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
