from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class NotificationPreference(Base):
    """1 dòng = 1 cấu hình chống bão thông báo của 1 user (ADR-007 mục 8).

    Tạo lười (`get_or_create_preference`) với giá trị mặc định an toàn khi
    user chưa từng chỉnh — không có 3 giá trị này thì với 5-10 người thử
    nghiệm và ~15 việc/tuần/người, extension sẽ bị tắt trước khi thu được
    dữ liệu (đúng lý do ADR-007 nêu).
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preference_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")
    # Giờ yên lặng theo local time trong ngày (0-23). Lời nhắc rơi vào khung
    # này bị dời tới quiet_hours_end thay vì huỷ (ADR-007 mục 8).
    quiet_hours_start: Mapped[int] = mapped_column(Integer, default=22)
    quiet_hours_end: Mapped[int] = mapped_column(Integer, default=7)
    hourly_cap: Mapped[int] = mapped_column(Integer, default=5)
    # Lời nhắc rơi cùng khung giờ (phút) được gộp thành 1 thông báo (FR-095).
    batch_window_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # Giờ local (0-23) user muốn nhận tổng hợp cuối ngày. NULL = tắt — daily
    # brief tự động là hành vi hệ thống chủ động thay người dùng, mặc định TẮT
    # giống tinh thần auto_sync_enabled (ADR-011): phải người dùng tự bật.
    daily_brief_hour: Mapped[int | None] = mapped_column(Integer, default=None)
    # Ngày (theo timezone ở trên, format YYYY-MM-DD) đã sinh daily brief gần
    # nhất — chặn sinh 2 lần trong cùng 1 ngày nếu worker quét nhiều lượt.
    daily_brief_last_date: Mapped[str | None] = mapped_column(String(10), default=None)
    # Bật/tắt từng kênh giao. Mặc định BẬT cả ba, khác với daily_brief_hour:
    # ba cột này không tự sinh thêm thông báo nào, chúng chỉ quyết định thông
    # báo đã sinh được đi qua đường nào. Người dùng đã tự cài extension, tự nối
    # Telegram hay tự bấm cho phép Web Push rồi thì mặc định tắt là bắt họ bật
    # hai lần cho cùng một ý định.
    extension_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    web_push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Danh sách `kind` người dùng không muốn nhận nữa (giá trị thuộc
    # REMINDER_KINDS). Tắt theo loại chứ không theo kênh vì lý do người dùng
    # tắt thường là "tin này không đáng bận tâm", không phải "máy này không cần
    # nhận" — tắt một loại thì tắt trên mọi kênh mới đúng ý đó.
    muted_kinds: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
