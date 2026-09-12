from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    """1 dòng = 1 dự án do người dùng tự tạo để gom các hội thoại liên quan.

    Chỉ là lớp SẮP XẾP: agent không đọc mô tả dự án khi trả lời (quyết định của
    chủ sở hữu sản phẩm, 2026-08-22). Nhờ vậy gán sai project không làm hỏng câu
    trả lời, chỉ làm rối chỗ cất.

    `description` vừa cho người đọc vừa là tư liệu để so khớp: hội thoại mới
    được đối chiếu với mô tả + tiêu đề các hội thoại đã có trong dự án để gợi ý
    "có muốn thêm vào đây không". Xem src/services/project_matching.py.
    """

    __tablename__ = "projects"
    __table_args__ = (
        # Tên trùng nhau trong CÙNG một người dùng chỉ gây nhầm lẫn; giữa hai
        # người dùng thì không liên quan gì tới nhau.
        UniqueConstraint("user_id", "name", name="uq_project_user_name"),
        Index("ix_projects_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # user_id lưu chuỗi vì get_current_user_id trả về chuỗi — cùng convention
    # đã ghi ở conversations.user_id và messages.user_id.
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # Màu nhãn hiển thị trên thẻ dự án. Lưu chuỗi thay vì enum để thêm màu
    # không phải migration.
    color: Mapped[str] = mapped_column(String(16), default="slate")
    # ---- Tóm tắt tổng quan dự án (cache) ----
    # Viết bằng LLM từ các hội thoại bên trong. PHẢI cache: sinh lại mỗi lần mở
    # trang là đốt token cho một nội dung gần như không đổi.
    summary: Mapped[str] = mapped_column(Text, default="")
    # Dấu vân tay của tập hội thoại lúc sinh tóm tắt: "<số hội thoại>:<mốc cập
    # nhật mới nhất>". Khác dấu này nghĩa là nội dung đã đổi -> sinh lại. Dùng
    # dấu vân tay thay vì hạn thời gian để dự án nằm im cả tháng không bị sinh
    # lại vô ích, còn dự án vừa thêm hội thoại thì cập nhật ngay.
    summary_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
