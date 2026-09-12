from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Message(Base):
    """1 dòng = 1 tin nhắn/email đã ingest từ nguồn kết nối."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("provider", "source_id", "external_id", name="uq_message_provider_source_external"),
        # Brief/task list truy vấn tin theo khoảng thời gian trong 1 user
        # (review mục "Thiếu linh tinh").
        Index("ix_messages_user_sent_at", "user_id", "sent_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id lưu chuỗi (JWT sub), không đặt ForeignKey vì users.id là INTEGER
    # -- xem cùng convention ở src/models/connection.py.
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("connections.id", ondelete="SET NULL"), default=None)
    provider: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str | None] = mapped_column(String(255), default=None)
    author_id: Mapped[str | None] = mapped_column(String(128), default=None)
    author_name: Mapped[str | None] = mapped_column(String(255), default=None)
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    # Metadata hộp thư mà bản ghi offline trước đây bỏ hẳn. Thiếu chúng thì
    # đường đọc-từ-cache (services/gmail_tools.py) dựng lại item không có
    # to/cc/subject/mailbox_email, nên filter_classify.py im lặng tụt hạng:
    # không chấm được recipient (+20), không phát hiện được mail không gửi
    # cho mình (not_addressed), không đọc được tiêu đề. Kết quả lần chạy đầu
    # (đường API) khác hẳn mọi lần rerun (đường cache).
    subject: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    to_addresses: Mapped[list | None] = mapped_column(JSON, default=None)
    cc_addresses: Mapped[list | None] = mapped_column(JSON, default=None)
    # Địa chỉ mailbox thật đang đồng bộ (connection.provider_user_id), khác
    # User.email đăng nhập app — xem comment trong src/connectors/gmail.py.
    mailbox_email: Mapped[str | None] = mapped_column(String(255), default=None)
    is_unread: Mapped[bool] = mapped_column(Boolean, default=False)
    # Chấm ở normalize() TRƯỚC khi boilerplate bị cắt khỏi text hiển thị.
    has_marketing_boilerplate: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Gmail/Discord luôn dựng được link, nhưng không phải provider nào cũng có
    # (Telegram chẳng hạn) — để nullable, FE ẩn nút "xem nguồn" khi rỗng.
    deep_link: Mapped[str | None] = mapped_column(String(1024), default=None)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # ADR-006 chốt pgvector là kho vector chuẩn, không dùng Chroma. Bảng này vẫn
    # chưa map cột "embedding" của database.sql: lớp truy hồi đọc `chunks`, còn
    # `messages` là tầng tin đã ingest. Thêm cột ở đây chỉ khi có nơi thật sự đọc.
