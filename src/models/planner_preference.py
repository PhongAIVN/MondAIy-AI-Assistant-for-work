from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class PlannerPreference(Base):
    """Hợp đồng ngày làm việc, một bản ghi riêng cho mỗi người dùng."""

    __tablename__ = "planner_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_planner_preference_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    workday_start_minute: Mapped[int] = mapped_column(Integer, default=8 * 60)
    lunch_start_minute: Mapped[int] = mapped_column(Integer, default=12 * 60)
    lunch_end_minute: Mapped[int] = mapped_column(Integer, default=14 * 60)
    workday_end_minute: Mapped[int] = mapped_column(Integer, default=18 * 60)
    happy_time_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    happy_time_start_minute: Mapped[int] = mapped_column(Integer, default=16 * 60)
    happy_time_end_minute: Mapped[int] = mapped_column(Integer, default=17 * 60)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
