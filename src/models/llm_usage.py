"""Ledger nội bộ cho token, chi phí và latency của từng lời gọi LLM."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class LLMUsageEvent(Base):
    """Không chứa prompt/response; user_id chỉ ở DB nội bộ, không ra metric."""

    __tablename__ = "llm_usage_events"
    __table_args__ = (
        Index("ix_llm_usage_user_time", "user_id", "created_at"),
        Index("ix_llm_usage_model_lane_time", "model", "lane", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128), default=None)
    model: Mapped[str] = mapped_column(String(255))
    lane: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, default=None)
    duration_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    usage_available: Mapped[bool] = mapped_column(Boolean, default=False)
    price_available: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
