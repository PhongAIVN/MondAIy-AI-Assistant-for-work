from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# `kind` phân biệt 4 loại thông báo chạy chung 1 pipe (gộp theo yêu cầu
# 2026-08-12): "task_due" (mốc nhắc FR-090, task_id bắt buộc, milestone =
# "1_day"/"30_min"/"at_time"), "task_proposed" (task mới cần confirm, task_id bắt buộc,
# 1 dòng/task), "conflict_schedule" (2 task confirmed trùng/gần giờ nhau,
# task_id = task đến sau, related_task_id = task đến trước), "conflict_evidence"
# (2 nguồn nói khác nhau về cùng deadline — fuse_and_rank(), task_id có thể
# NULL vì cluster bằng chứng không nhất thiết map 1-1 với 1 Task), "daily_brief"
# (tổng hợp cuối ngày theo giờ user tự chọn, task_id luôn NULL),
# "calendar_changed" (sự kiện trong lịch đã kết nối bị dời giờ hoặc bị huỷ ở
# nguồn — task_id luôn NULL vì nó nói về sự kiện lịch, không về task).
REMINDER_KINDS = (
    "task_due",
    "task_proposed",
    "conflict_schedule",
    "conflict_evidence",
    "daily_brief",
    "calendar_changed",
)


class Reminder(Base):
    """1 dòng = 1 thông báo (mốc nhắc, task mới, conflict hoặc daily brief).

    `status = cancelled` chỉ do người dùng bỏ qua (ADR-007 mục 4) — tách hẳn
    khỏi `task.status`, bỏ qua lời nhắc không được phép rút task khỏi mẫu số
    PRD §4.2. Tên bảng/field giữ nguyên "reminder" vì phần lớn logic (gộp,
    trần, giờ yên lặng, snooze/dismiss, delivery-dedup) vẫn là "nhắc 1 việc gì
    đó tới hạn" — chỉ mở rộng "gì đó" ra ngoài task_due qua cột `kind`.
    """

    __tablename__ = "reminders"
    __table_args__ = (Index("ix_reminders_user_status_scheduled", "user_id", "status", "scheduled_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL cho kind="conflict_evidence"/"daily_brief" — không map 1-1 vào 1 task.
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True, default=None)
    # Chỉ có giá trị cho kind="conflict_schedule" — task còn lại trong cặp trùng giờ.
    related_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), default=None
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="task_due")
    # "1_day" | "30_min" | "at_time" (kind=task_due) — mốc mặc định FR-090. Lưu nhãn tường
    # minh thay vì suy từ offset, để đổi offset sau này không làm sai nhãn đã lưu.
    milestone: Mapped[str] = mapped_column(String(32))
    # Dữ liệu riêng theo kind, không ép chung schema: conflict_evidence lưu
    # topic + quote 2 bên; daily_brief lưu số liệu tổng hợp. Rỗng cho task_due.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    snooze_count: Mapped[int] = mapped_column(Integer, default=0)
    dismiss_reason: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class NotificationDelivery(Base):
    """1 dòng = 1 lần đã giao thông báo cho 1 reminder.

    Khoá theo `reminder_id` để service worker của extension (MV3, bị dừng bất
    kỳ lúc nào) khởi động lại không giao trùng (FR-091) — reminder đã có dòng
    ở đây thì `get_due_notifications` không trả về nữa. `snooze_reminder` xoá
    dòng này để reminder giao lại được ở mốc mới.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("reminder_id", name="uq_notification_delivery_reminder"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("reminders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
