from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class RunNodeEvent(Base):
    """1 dòng = 1 node pipeline đã chạy xong cho 1 run — lưu lại để SSE replay
    được sau khi user F5, không chỉ phát 1 lần rồi mất."""

    __tablename__ = "run_node_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    count: Mapped[int | None] = mapped_column(Integer, default=None)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
