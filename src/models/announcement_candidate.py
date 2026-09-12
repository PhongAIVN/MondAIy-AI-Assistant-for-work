"""Thông báo Discord do admin duyệt, giữ raw evidence và candidate theo cohort."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class AnnouncementCandidate(Base):
    __tablename__ = "announcement_candidates"
    __table_args__ = (
        UniqueConstraint("cohort_slug", "content_hash", name="uq_announcement_candidate_cohort_hash"),
        Index("ix_announcement_candidate_cohort_status", "cohort_slug", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_slug: Mapped[str] = mapped_column(String(64), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    preview: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    information_item_id: Mapped[int | None] = mapped_column(default=None)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
