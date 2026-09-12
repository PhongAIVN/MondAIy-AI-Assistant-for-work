"""Sự kiện đo lường và nhật ký thay đổi.

Hai bảng tách nhau vì hai mục đích khác nhau và hai chế độ lưu khác nhau:

`telemetry_events` là số liệu sản phẩm theo PRD §13 — **không bao giờ chứa nội
dung gốc**, chỉ chứa thuộc tính đã nằm trong danh sách cho phép. Xoá được theo
thời hạn lưu mà không mất bằng chứng.

`audit_events` là lịch sử thay đổi theo FR-070 — ai làm gì, lúc nào, phiên bản
nào. Cái này phải giữ vì nó là bằng chứng vận hành, và nó tham chiếu tới bản ghi
thật chứ không sao chép nội dung.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

JsonDict = JSON().with_variant(JSONB(), "postgresql")


class TelemetryEvent(Base):
    """1 dòng = 1 sự kiện đo lường, tên và thuộc tính theo PRD §13."""

    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("ix_telemetry_ten_time", "name", "created_at"),
        Index("ix_telemetry_trace", "trace_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(48), index=True)
    # Nối các sự kiện của cùng một yêu cầu, đi xuyên từ connector tới câu trả lời
    # — architecture §9 đòi trace ID chạy suốt chuỗi đó.
    trace_id: Mapped[str] = mapped_column(String(36), default="")
    # Bề mặt phát sinh: web, telegram, discord, cli. Không nằm trong bảng PRD §13
    # nhưng cần để tách số liệu giữa các bề mặt — xem TODO(OD-TEL1).
    surface: Mapped[str] = mapped_column(String(16), default="web")
    user_id: Mapped[str | None] = mapped_column(String(128), index=True, default=None)
    # Chỉ chứa thuộc tính đã qua danh sách cho phép của telemetry.py.
    attributes: Mapped[dict | None] = mapped_column(JsonDict, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class AuditEvent(Base):
    """1 dòng = 1 thao tác đã thay đổi trạng thái, theo FR-070.

    Khác telemetry ở chỗ nó trỏ tới bản ghi cụ thể (`object_type`, `object_id`)
    để truy ngược được, và không bị xoá theo thời hạn đo lường.
    """

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_doi_tuong", "object_type", "object_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(48), index=True)
    object_type: Mapped[str] = mapped_column(String(48))
    object_id: Mapped[str] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(16), default="system")
    actor_id: Mapped[str | None] = mapped_column(String(128), default=None)
    trace_id: Mapped[str] = mapped_column(String(36), default="")
    version_label: Mapped[str | None] = mapped_column(String(64), default=None)
    details: Mapped[dict | None] = mapped_column(JsonDict, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
