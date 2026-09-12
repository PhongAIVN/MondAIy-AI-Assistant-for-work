"""Ánh xạ giữa một mốc chương trình và event đã ghi vào lịch Google của user.

Không có bảng này thì lần đồng bộ thứ hai không phân biệt được "mốc này user đã
đồng ý ghi rồi" với "mốc mới" — kết quả là nhân bản toàn bộ lịch chương trình
trong lịch cá nhân của họ, mỗi lần bấm một lần.

Bảng cũng giữ `approved_content_hash`: bản nội dung mà user đã nhìn thấy và
đồng ý tại thời điểm bấm. Ban tổ chức đổi giờ sau đó thì hash lệch, và ADR-009
buộc phải hỏi lại chứ không tự sửa lịch của họ (BR-09).
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ProgramCalendarSync(Base):
    """1 dòng = 1 mốc chương trình đã được một user đồng ý ghi vào lịch của họ."""

    __tablename__ = "program_calendar_syncs"
    __table_args__ = (
        UniqueConstraint("user_id", "program_event_id", name="uq_program_sync_user_event"),
        Index("ix_program_sync_user", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    program_event_id: Mapped[int] = mapped_column(ForeignKey("program_events.id"), index=True)

    calendar_id: Mapped[str] = mapped_column(String(512), default="primary")
    # ID event phía Google. Đây là thứ khiến lần đồng bộ sau sửa đúng event cũ
    # thay vì tạo thêm một event trùng tên.
    event_id: Mapped[str] = mapped_column(String(512))

    # Băm nội dung mốc tại thời điểm user bấm đồng ý.
    approved_content_hash: Mapped[str] = mapped_column(String(64))
    # synced = khớp nguồn; source_changed = BTC đã đổi sau khi user đồng ý và
    # chưa ai duyệt lại.
    status: Mapped[str] = mapped_column(String(24), default="synced", index=True)

    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Số lần user duyệt lại mốc này sau khi nguồn đổi. Giữ lại để biết luồng
    # "hỏi lại" có gây phiền tới mức nào trước khi tính chuyện nới nó.
    reapproved_count: Mapped[int] = mapped_column(Integer, default=0)
