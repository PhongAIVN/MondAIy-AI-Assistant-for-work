from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Brief(Base):
    """1 dòng = 1 tóm tắt cuối của 1 run — cho FE hiện trang brief sau khi sync xong."""

    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    # list[{"taskId": int, "title": str, "dueAt": str | None}]
    top_priority: Mapped[list] = mapped_column(JSON, default=list)
    # Luôn rỗng ở bản này — chưa có nguồn Calendar để tính conflict thật,
    # không suy diễn. Có dữ liệu Calendar mới điền (xem ADR-002 phạm vi).
    schedule_conflicts: Mapped[list] = mapped_column(JSON, default=list)
    # Grounded source references shown with every briefing.
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
