from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# Tần suất chạy hợp lệ của 1 routine. "trigger" (chạy theo sự kiện, vd có email
# mới) CHƯA làm ở đây — chưa có ADR/PRD định nghĩa "trigger" nghĩa là gì và
# chưa có hạ tầng event-driven sau pipeline sync. # TODO(OD): bổ sung khi có
# quyết định rõ ràng từ PM/Tech Lead.
ROUTINE_FREQUENCIES = ("daily", "every_other_day", "weekly", "monthly")


class Routine(Base):
    """1 dòng = 1 automation do user tự đặt: instructions tự do + lịch chạy.

    Khác `NotificationPreference` (1 dòng/user, cấu hình chung), routine là
    N dòng/user — mỗi routine là 1 automation độc lập. `instructions` được
    đưa thẳng vào agent làm `query`, dùng đúng graph chat hiện có
    (`src/agents/graph.py`) nên chỉ có thể tạo bản nháp local (Task proposed
    qua `draft_task`/`suggest_tasks`/`create_productivity_item`) — không có
    tool nào trong bộ đó ghi ra ứng dụng bên ngoài, đúng BR-13.
    """

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(String(16), default="daily")
    interval_days: Mapped[int] = mapped_column(Integer, default=2)
    # Chỉ có giá trị khi frequency="weekly". 0=Thứ Hai .. 6=Chủ Nhật (Python weekday()).
    day_of_week: Mapped[int | None] = mapped_column(Integer, default=None)
    # Chỉ có giá trị khi frequency="monthly". Ngày > số ngày thực của tháng thì
    # kẹp về ngày cuối tháng đó lúc so khớp, không lưu lại giá trị đã kẹp.
    day_of_month: Mapped[int | None] = mapped_column(Integer, default=None)
    # Giờ local (0-23) — cùng ý nghĩa NotificationPreference.daily_brief_hour.
    hour: Mapped[int] = mapped_column(Integer, default=7)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Lưu đúng lựa chọn của user — CHƯA có delivery thật đứng sau (chưa gửi
    # push/email khi routine chạy xong). Nối delivery là việc khác, sau này;
    # cột này chỉ đảm bảo không mất lựa chọn của user khi tính năng đó ra đời.
    notify_push: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    # Ngày (theo timezone ở trên, format YYYY-MM-DD) đã chạy gần nhất — chặn
    # chạy 2 lần trong cùng 1 ngày nếu worker quét nhiều lượt, y hệt cơ chế
    # NotificationPreference.daily_brief_last_date.
    last_run_date: Mapped[str | None] = mapped_column(String(10), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class RoutineRun(Base):
    """1 dòng = 1 lần routine đã chạy, kèm kết quả để user đọc lại trong app.

    `output_text`/`output_json` KHÔNG bao giờ tự ghi ra ứng dụng bên ngoài —
    đây là nội dung đọc trong mondaiy, đúng hướng an toàn đã chốt (BR-13).
    """

    __tablename__ = "routine_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    output_text: Mapped[str | None] = mapped_column(Text, default=None)
    output_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
