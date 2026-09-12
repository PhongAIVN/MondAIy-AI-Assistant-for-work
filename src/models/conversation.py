from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Conversation(Base):
    """1 dòng = 1 phiên chat của đúng 1 user.

    TODO(OD-02): thời hạn lưu lịch sử trò chuyện chưa được chốt (PRD mục 19).
    Chưa có job xoá theo hạn, nên hiện giữ vô thời hạn cho tới khi có quyết định.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        # Màn hình danh sách lấy hội thoại của 1 user, mới nhất trước.
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id lưu chuỗi vì get_current_user_id trả về chuỗi, và users.id là
    # INTEGER nên không đặt ForeignKey — cùng lý do đã ghi ở messages.user_id.
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255), default="Hội thoại mới")
    # Bộ nhớ ngắn hạn của phiên: các lượt cũ đã bị đẩy ra khỏi cửa sổ nguyên văn
    # được nén lại đây, để hội thoại dài không mất phần đầu. Đây là văn bản do
    # model sinh, luôn đưa vào prompt như dữ liệu chứ không phải chỉ dẫn.
    summary: Mapped[str] = mapped_column(Text, default="")
    # Lượt cuối cùng đã nằm trong `summary`. Lần nén sau chỉ đọc các lượt có id
    # lớn hơn giá trị này, nên chi phí không phình theo độ dài phiên.
    summary_through_message_id: Mapped[int | None] = mapped_column(Integer, default=None)
    # Dự án chứa hội thoại này. NULL = chưa xếp vào đâu — đó là trạng thái mặc
    # định và hợp lệ, không phải thiếu dữ liệu. Không đặt ForeignKey cứng để xoá
    # dự án không kéo theo xoá hội thoại; API tự dọn tham chiếu.
    project_id: Mapped[int | None] = mapped_column(Integer, index=True, default=None)
    # Người dùng ghim phiên để truy cập nhanh từ Sidebar.
    is_favorite: Mapped[bool] = mapped_column(default=False, nullable=False)
    share_visibility: Mapped[str] = mapped_column(String(16), default="private")
    share_token: Mapped[str | None] = mapped_column(String(96), unique=True, index=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConversationMessage(Base):
    """1 dòng = 1 lượt nói trong phiên chat, của người dùng hoặc của trợ lý."""

    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_conv_messages_conv_created", "conversation_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    # "user" hoặc "assistant".
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    # Phần phân tích nội bộ của agent. Giữ lại để đối chiếu khi câu trả lời sai,
    # không hiển thị thẳng cho người dùng.
    analysis: Mapped[str | None] = mapped_column(Text, default=None)
    # Các trường có cấu trúc của một câu trả lời có căn cứ: tóm lược, thay đổi,
    # danh sách bằng chứng. Đường Gmail briefing dựng sẵn rồi gửi lên, nên lưu
    # nguyên khối thay vì tách cột — hình dạng còn đổi theo giao diện.
    extras: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Phản hồi của người dùng về câu trả lời (FR-035).
    feedback: Mapped[str | None] = mapped_column(String(16), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
