from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Task(Base):
    """1 dòng = 1 việc cần làm được đề xuất từ cụm tin nhắn liên quan."""

    __tablename__ = "tasks"
    __table_args__ = (
        # unique toàn cục trên cluster_key gộp nhầm việc của 2 user có cùng
        # title/ngày trùng nhau — phải scope theo user_id (review database.sql,
        # Yến Nhi 2026-08-05).
        UniqueConstraint("user_id", "cluster_key", name="uq_task_user_cluster_key"),
        # Trang task list filter theo status trong 1 user — index đơn user_id
        # không đủ (review mục "Thiếu linh tinh").
        Index("ix_tasks_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    cluster_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    assignee: Mapped[str | None] = mapped_column(String(255), default=None)
    assignee_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    source_count: Mapped[int] = mapped_column(Integer, default=1)
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    calendar_event_id: Mapped[str | None] = mapped_column(String(255), default=None)
    # Explainability (src/services/jira_rules.py) — chỉ có giá trị cho task
    # tạo từ nguồn rule-based (Jira). Task từ nguồn còn dùng LLM (Gmail) để
    # NULL, không suy diễn giá trị giả cho nguồn chưa có rule engine.
    decision: Mapped[str | None] = mapped_column(String(16), default=None)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    rule_version: Mapped[str | None] = mapped_column(String(32), default=None)
    # Số lần người dùng đã bỏ qua 1 lời nhắc của task này — dùng giảm ưu tiên
    # lần sau (ADR-007 mục 5), KHÔNG phải số lần task bị huỷ.
    reminder_dismiss_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Mốc vào thùng rác. Phải là cột RIÊNG chứ không dùng `updated_at`: bất kỳ
    # thao tác nào cũng chạm updated_at, nên lấy nó làm mốc lưu giữ sẽ đẩy hạn
    # xoá lùi mãi hoặc xoá nhầm task vừa được khôi phục.
    # NULL mang nghĩa "không nằm trong thùng rác" — task huỷ TRƯỚC khi có cột này
    # cũng là NULL, và job dọn cố ý bỏ qua chúng thay vì đoán một mốc rồi xoá
    # dữ liệu cũ của người dùng.
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # ADR-021 — cảm biến thời gian làm việc.
    #
    # Mốc người dùng XÁC NHẬN đang làm, không phải mốc suy ra từ lúc họ tick
    # xong. Đo trên production 27/08: 9/14 task được tick vào 0h-1h sáng, nhưng
    # đó gần như chắc chắn là giờ ngồi review lại cả buổi chứ không phải giờ
    # làm. `completed_at` một mình là cảm biến sai, và không thuật toán nào sửa
    # được một cảm biến đo nhầm thứ.
    #
    # NULL nghĩa là chưa từng xác nhận bắt đầu. Cố ý KHÔNG suy ngược từ
    # `created_at` hay `updated_at`: một mốc bịa còn tệ hơn không có mốc, vì
    # reference class sẽ học theo nó.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    # ADR-018 slice 0 — schema cho planner xác định, chưa nối logic ghi.
    # Ước lượng luôn hiển thị dưới dạng khoảng (low, high), không một số đơn.
    estimate_low_min: Mapped[int | None] = mapped_column(Integer, default=None)
    estimate_high_min: Mapped[int | None] = mapped_column(Integer, default=None)
    # Ghi khi user đánh dấu xong (ADR-018 QĐ-5) — logic ghi thuộc việc khác,
    # NGOÀI PHẠM VI của thay đổi schema này.
    actual_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    # Phụ thuộc giữa các việc, dùng cho topological sort ở planner. Cho phép
    # chu trình ở tầng DB — planner phải tự phát hiện và báo, không được treo
    # (xem ADR-018 mục "Hệ quả · Tiêu cực và rủi ro").
    depends_on_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), default=None)
    # 'deep' | 'shallow' — ngưỡng OD-03: cận trên ước lượng trên 45 phút thì deep.
    energy: Mapped[str | None] = mapped_column(String(16), default=None)
    # ADR-019 — dữ liệu đã trích giữ riêng khỏi detail để không mất cấu trúc.
    expected_output: Mapped[str | None] = mapped_column(Text, default=None)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, default=None)
    context_input: Mapped[str | None] = mapped_column(Text, default=None)
    constraints: Mapped[str | None] = mapped_column(Text, default=None)
    execution_tool: Mapped[str | None] = mapped_column(Text, default=None)
    execution_method: Mapped[str | None] = mapped_column(Text, default=None)
    stated_priority: Mapped[str | None] = mapped_column(String(32), default=None)
    stakeholders: Mapped[list | None] = mapped_column(JSON, default=list)
    deliver_to: Mapped[str | None] = mapped_column(Text, default=None)


class TaskStep(Base):
    """1 dòng = 1 bước cụ thể do LLM tách ra cho một Task (ADR-018 slice 0)."""

    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    estimate_min: Mapped[int | None] = mapped_column(Integer, default=None)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
