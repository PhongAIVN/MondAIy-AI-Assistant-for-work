from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

RunStatus = str  # "queued" | "running" | "succeeded" | "failed"


class Run(Base):
    """1 dòng = 1 lần bấm Force Sync — gộp state của pipeline task-extraction
    cho FE bám vào (thay vì chỉ có SSE tạm thời, mất khi F5)."""

    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_run_user_idempotency_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # list[{"connectionId": int, "sourceId": str}] — không dùng ARRAY(varchar)
    # như bản review đề xuất vì cần giữ cặp connection+source, không chỉ tên
    # provider; JSON để tương thích cả SQLite (dev) lẫn Postgres.
    sources: Mapped[list] = mapped_column(JSON)
    range_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    range_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # Ngôn ngữ title/summary/detail LLM viết cho run này (xem RunCreateRequest).
    language: Mapped[str] = mapped_column(String(8), default="vi")
    mode: Mapped[str] = mapped_column(String(32), default="task_extraction")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    error_message: Mapped[str | None] = mapped_column(String(1024), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
