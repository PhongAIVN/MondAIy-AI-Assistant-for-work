"""Lịch chương trình nhập từ ICS feed của ban tổ chức.

Bảng này tách khỏi `calendar_events` (lịch Google cá nhân của người dùng) và
khỏi `source_items` (tin nhắn Discord đã cào). Lý do: đây là dữ liệu chung của
cả cohort, không thuộc về một user nào, và có hình dạng sự kiện — mốc bắt đầu,
mốc kết thúc, loại mốc — chứ không phải hình dạng tin nhắn.

Xem ADR-008 để biết vì sao nguồn này được thêm và ai được đọc.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.evidence import JsonList


class ProgramEvent(Base):
    """1 dòng = 1 sự kiện trong lịch chương trình của một cohort."""

    __tablename__ = "program_events"
    __table_args__ = (
        UniqueConstraint("cohort_slug", "external_id", name="uq_program_event_cohort_external"),
        Index("ix_program_event_cohort_time", "cohort_slug", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Khóa cohort để một lần nhập nhầm feed của khóa khác không trộn vào lịch
    # đang phục vụ, và để truy vấn luôn lọc được theo đúng khóa của người hỏi.
    cohort_slug: Mapped[str] = mapped_column(String(64), index=True)
    # UID trong ICS, ví dụ "event:8@phoenix...". Đây là khóa ổn định của BTC nên
    # nhập lại feed là cập nhật đúng dòng cũ chứ không nhân bản.
    external_id: Mapped[str] = mapped_column(String(191))

    # custom | daily_deadline | weekly_deadline | gate_deadline | mentor_duty
    event_type: Mapped[str] = mapped_column(String(32), index=True, default="custom")
    # program = cả cohort được thấy; team = chỉ nhóm liên quan. Mentor duty là
    # loại thứ hai: đưa vào câu trả lời chung là nói lịch của nhóm khác cho
    # người không thuộc nhóm đó.
    visibility: Mapped[str] = mapped_column(String(16), index=True, default="program")

    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    host: Mapped[str | None] = mapped_column(String(255), default=None)
    location_url: Mapped[str | None] = mapped_column(String(512), default=None)

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Băm nội dung để lần nhập sau phân biệt được "BTC sửa" với "không đổi gì",
    # theo đúng cách source_items phân biệt phiên bản (FR-013).
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # --- Lớp quản trị (ADR-010) ---

    # feed = mốc do ICS của ban tổ chức sinh ra; admin = mốc do quản trị tự tạo.
    # Mốc `admin` không bao giờ bị lần nhập feed sau đó đụng tới.
    origin: Mapped[str] = mapped_column(String(16), index=True, default="feed")
    # draft = chỉ quản trị thấy; published = học viên mức A thấy; archived = gỡ
    # khỏi lịch mà không xóa dấu vết.
    status: Mapped[str] = mapped_column(String(16), index=True, default="published")

    # Tên các trường quản trị đã sửa tay. Lần nhập feed sau **không** ghi đè
    # những trường này — nếu ghi đè thì mọi chỉnh sửa của ban tổ chức nội bộ đều
    # bị xóa sau lần đồng bộ kế tiếp, im lặng.
    locked_fields: Mapped[list | None] = mapped_column(JsonList, default=None)
    # Ảnh chụp giá trị từ feed ở lần nhập gần nhất. Giữ lại để (a) phát hiện
    # feed đổi đúng vào trường đang bị khóa, (b) cho phép hoàn về bản gốc.
    feed_payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    # True khi feed đổi một trường quản trị đang giữ. Không tự xử: hiện lên
    # trang quản trị để người quyết định giữ bản nào.
    source_conflict: Mapped[bool] = mapped_column(default=False, index=True)

    updated_by: Mapped[str | None] = mapped_column(String(64), default=None)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
