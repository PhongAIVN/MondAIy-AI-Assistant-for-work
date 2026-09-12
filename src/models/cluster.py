from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Cluster(Base):
    """1 dòng = 1 cụm tin nhắn liên quan tới cùng 1 việc, trước khi (hoặc sau khi) hoá thành Task."""

    __tablename__ = "clusters"
    # cùng lý do với Task.cluster_key — xem uq_task_user_cluster_key.
    __table_args__ = (UniqueConstraint("user_id", "cluster_key", name="uq_cluster_user_cluster_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    cluster_key: Mapped[str] = mapped_column(String(64))
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ClusterMessage(Base):
    """Bảng nối nhiều-nhiều giữa Cluster và Message."""

    __tablename__ = "cluster_messages"
    # PK (cluster_id, message_id) không phủ tra cứu ngược "message này thuộc
    # cluster nào" — cần index riêng trên message_id (review mục "Thiếu linh tinh").
    __table_args__ = (Index("ix_cluster_messages_message_id", "message_id"),)

    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id", ondelete="CASCADE"), primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
