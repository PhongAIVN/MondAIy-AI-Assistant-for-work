"""Bảng phục vụ tầng chống spam token khi đọc Google Docs/Sheets.

Quota nằm ở DB chứ không ở bộ nhớ tiến trình: nhiều replica API dùng chung một
hạn mức, và một lần restart không được cấp lại lượt cho người dùng.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class DocumentReadQuota(Base):
    """1 dòng = hạn mức đọc tài liệu trong ngày của 1 user (Docs + Sheets dùng chung)."""

    __tablename__ = "document_read_quotas"
    __table_args__ = (UniqueConstraint("user_id", name="uq_document_read_quota_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    # Ngày theo múi giờ ứng dụng (ISO date), đổi ngày thì reset bộ đếm.
    quota_day: Mapped[str] = mapped_column(String(10))
    reads_used: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class DocumentReadCache(Base):
    """1 dòng = kết quả đề xuất task đã tính cho đúng một revision của một file.

    Khoá băm từ (user_id, file_id, revision, extractor_version, sheet_name) nên
    file hoặc contract phân tích đổi là sinh khoá mới, không trả kết quả cũ.
    """

    __tablename__ = "document_read_caches"
    __table_args__ = (UniqueConstraint("user_id", "cache_key", name="uq_document_read_cache_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    cache_key: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
