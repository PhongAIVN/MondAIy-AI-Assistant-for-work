from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class SyncCursor(Base):
    """1 dòng = 1 con trỏ đồng bộ (key/value) dùng nội bộ cho pipeline ingest."""

    __tablename__ = "sync_cursors"
    # key unique toàn cục thì 2 user cùng đọc 1 provider ghi đè cursor của
    # nhau — chưa dùng bảng này trong pipeline (xem plan TAPB-121) nhưng sửa
    # trước khi có ai wire vào, rẻ hơn sửa sau khi đã có data thật.
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_sync_cursor_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    key: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
