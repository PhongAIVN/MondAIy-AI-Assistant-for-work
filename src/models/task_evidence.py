from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class TaskEvidence(Base):
    """1 dòng = 1 trích dẫn tin nhắn làm bằng chứng cho 1 Task."""

    __tablename__ = "task_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), default=None)
    provider: Mapped[str] = mapped_column(String(32))
    evidence_quote: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[str] = mapped_column(String(1024))
    # Nguồn (message gốc) có đính kèm file hay không — dùng hiện badge 📎 ở
    # Tasks page, không phải "task này có attachment_text đã trích được".
    has_attachment: Mapped[bool] = mapped_column(Boolean, default=False)
