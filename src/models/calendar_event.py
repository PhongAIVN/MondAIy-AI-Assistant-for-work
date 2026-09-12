from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class CalendarEvent(Base):
    """1 dòng = 1 sự kiện lịch đã đọc về và lưu lại (FR-102).

    Bảng này là bộ nhớ đệm, không phải nguồn chuẩn. Google vẫn là nơi giữ sự
    thật; ở đây chỉ giữ bản chụp gần nhất để lưới lịch hiện ra ngay thay vì
    phải chờ gọi API. Vì vậy mọi dòng đều mang `synced_at` để giao diện nói rõ
    dữ liệu cũ tới mức nào, đúng yêu cầu không được trình bày dữ liệu đã lưu
    như dữ liệu thời gian thực.
    """

    __tablename__ = "calendar_events"
    __table_args__ = (
        # Khoá tự nhiên phải gồm user_id: cùng một event_id của Google có thể
        # xuất hiện ở hai tài khoản khác nhau (lịch dùng chung), unique chỉ
        # theo (calendar_id, event_id) sẽ khiến người này ghi đè bản của
        # người kia — đúng loại lỗi rò dữ liệu mà FR-105 đặt ngưỡng 0.
        UniqueConstraint("user_id", "calendar_id", "event_id", name="uq_calendar_event_user_cal_event"),
        # Lưới tuần luôn truy vấn theo khoảng thời gian trong phạm vi 1 user.
        Index("ix_calendar_events_user_window", "user_id", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    calendar_id: Mapped[str] = mapped_column(String(512))
    event_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    # active = còn ở nguồn; deleted = người dùng xoá qua mondaiy; stale = nguồn
    # báo không còn tồn tại. Ba trạng thái này khác nhau về ý nghĩa nên không
    # gộp thành một cờ boolean (FR-104).
    status: Mapped[str] = mapped_column(String(16), default="active")
    deep_link: Mapped[str | None] = mapped_column(String(1024), default=None)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Bản chụp payload gốc, dùng để hoàn tác một lần xoá mà không phải gọi lại
    # Google (BR-14). Không chứa danh sách người tham dự vì P0 không xử lý.
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class CalendarOperation(Base):
    """1 dòng = 1 thao tác ghi trực tiếp của người dùng, kèm dữ liệu để hoàn tác.

    Cơ chế: trước khi ghi lên Google, lưu trạng thái trước đó vào `before`.
    Trong cửa sổ hoàn tác, endpoint undo đọc lại `before` và áp ngược thao tác.
    Lưu ở máy chủ chứ không để client giữ, vì client có thể đóng tab giữa
    chừng và vì payload hoàn tác không được phép do client gửi lên tuỳ ý.
    """

    __tablename__ = "calendar_operations"
    __table_args__ = (Index("ix_calendar_operations_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    calendar_id: Mapped[str] = mapped_column(String(512))
    event_id: Mapped[str] = mapped_column(String(255))
    # create | update | delete
    op: Mapped[str] = mapped_column(String(16))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
