from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ScheduleConflict(Base):
    """1 dòng = 1 lần một task và một sự kiện lịch bị coi là trùng nhau.

    Hai kiểu trùng nằm chung một bảng vì luồng người dùng giống nhau — hiện cả
    hai bên, hỏi ưu tiên bên nào — chỉ khác cách suy ra gợi ý:

    - `time_overlap`: hai bên chiếm cùng một khoảng giờ nhưng là hai việc khác
      nhau. Người dùng chọn ưu tiên bên nào, hệ thống KHÔNG tự dời giờ.
    - `same_item`: cùng một việc xuất hiện hai lần (một bên là task rút ra từ
      nguồn, một bên là sự kiện đã có trên lịch). Người dùng chọn bản chính.

    Bảng chỉ ghi thêm, không ghi đè: một cặp task/sự kiện đổi giờ sẽ sinh dòng
    mới với `conflict_key` mới, dòng cũ chuyển sang `superseded` chứ không bị
    sửa (PRD FR-032, FR-041). Nhờ vậy quyết định người dùng đã đưa ra vẫn đọc
    lại được sau khi dữ liệu nguồn thay đổi.
    """

    __tablename__ = "schedule_conflicts"
    __table_args__ = (
        # conflict_key đã băm cả user_id nhưng vẫn scope unique theo user: khoá
        # unique toàn cục làm rò sự tồn tại dữ liệu người khác khi hai user vô
        # tình sinh cùng khoá, và đây đúng chỗ CalendarEvent đã cẩn thận
        # (uq_calendar_event_user_cal_event).
        UniqueConstraint("user_id", "conflict_key", name="uq_schedule_conflict_user_key"),
        # Panel trên trang Tasks luôn đọc theo (user, status) rồi sắp theo giờ
        # bắt đầu của bên task.
        Index("ix_schedule_conflicts_user_status", "user_id", "status", "task_starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    # Băm từ (user, kiểu trùng, task, lịch, sự kiện, giờ hai bên) — chạy lại
    # detect với cùng dữ liệu không sinh dòng trùng (FR-012).
    conflict_key: Mapped[str] = mapped_column(String(64))
    # time_overlap | same_item
    conflict_type: Mapped[str] = mapped_column(String(16))

    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    calendar_id: Mapped[str] = mapped_column(String(512))
    event_id: Mapped[str] = mapped_column(String(255))

    # Giờ hai bên tại thời điểm phát hiện. Lưu lại thay vì join ngược vì dòng
    # `resolved` phải kể đúng bối cảnh lúc người dùng quyết định, kể cả khi
    # task hoặc sự kiện đã đổi giờ sau đó.
    task_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    overlap_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # Ảnh chụp bên sự kiện (title, giờ, deep_link) để giao diện vẽ được panel
    # mà không phải gọi lại Google hay đọc thêm bảng calendar_events.
    event_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    # prioritize_task | prioritize_event | undecided. `undecided` là giá trị
    # hợp lệ và hay gặp: không đủ căn cứ thì phải nói không biết chứ không đoán
    # (PRD §8 nguyên tắc từ chối trả lời).
    suggestion: Mapped[str] = mapped_column(String(24), default="undecided")
    # Danh sách slug lý do, giao diện tự dịch. Slug tiếng Anh vì đây là khoá dữ
    # liệu, không phải văn bản cho người đọc.
    suggestion_reasons: Mapped[list] = mapped_column(JSON, default=list)

    # open = chờ người dùng quyết; resolved = đã quyết; superseded = giờ hai bên
    # đã đổi nên có dòng mới thay thế; stale = hai bên không còn trùng nữa.
    status: Mapped[str] = mapped_column(String(16), default="open")
    # prioritize_task | prioritize_event | accept_both — cùng bộ từ vựng với
    # `suggestion` để so được "người dùng có làm theo gợi ý không".
    resolution: Mapped[str | None] = mapped_column(String(24), default=None)
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
