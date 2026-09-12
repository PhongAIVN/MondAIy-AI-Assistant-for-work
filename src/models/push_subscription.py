from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class PushSubscription(Base):
    """Một endpoint Web Push mà trình duyệt của người dùng đã cấp cho ta.

    Khoá thật của bảng là ``endpoint``: trình duyệt cấp đúng một endpoint cho
    mỗi cặp (thiết bị, hồ sơ trình duyệt), nên unique ở đây là thứ chặn việc
    cùng một máy nhận thông báo nhiều lần. ``user_id`` chỉ là chủ sở hữu hiện
    tại — đăng nhập tài khoản khác trên cùng máy sẽ chuyển quyền sở hữu chứ
    không tạo dòng thứ hai, nếu không người dùng mới sẽ nhận thông báo của
    người cũ.

    ``last_error_class`` chỉ giữ TÊN LOẠI lỗi (không giữ nội dung phản hồi của
    push service) để chẩn đoán mà không đưa dữ liệu gốc vào dữ liệu vận hành
    theo PRD §13.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    endpoint: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error_class: Mapped[str | None] = mapped_column(String(64), default=None)
