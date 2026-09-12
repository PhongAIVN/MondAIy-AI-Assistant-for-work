from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class AppRating(Base):
    """Voluntary in-product experience rating, scoped to one authenticated user."""

    __tablename__ = "app_ratings"
    __table_args__ = (Index("ix_app_ratings_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text, default=None)
    trigger: Mapped[str] = mapped_column(String(32), default="action_count")
    session_id: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    meaningful_action_count: Mapped[int] = mapped_column(Integer, default=0)
    session_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
