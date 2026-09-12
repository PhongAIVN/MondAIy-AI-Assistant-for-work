"""Hai bảng của bộ nhớ dài hạn.

`user_profile_memories` là lớp explicit profile: chỉ chứa facts do chính người
dùng khai rõ, mỗi key một giá trị hiện hành.

`user_memories` là lớp semantic/canonical theo memory-lifecycle §4: có kind,
trạng thái, thẩm quyền nguồn, khoảng hiệu lực và liên kết bằng chứng. Fact mới
không ghi đè fact cũ mà tạo phiên bản mới rồi trỏ `supersedes_id` về bản cũ, nên
lịch sử vẫn đọc lại được — §6 cấm xoá tại chỗ.
"""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.evidence import VECTOR_DIMS


def _now() -> datetime:
    return datetime.now(UTC)


class UserProfileMemory(Base):
    """Một fact profile hiện hành của một user.

    Không lưu nguyên tin nhắn hay suy luận tự do ở đây. `key` thuộc allowlist
    trong service; unique `(user_id, key)` khiến phát biểu mới thay thế giá trị
    cũ thay vì tích lũy các phiên bản mâu thuẫn vào prompt.
    """

    __tablename__ = "user_profile_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_profile_memory_key"),
        Index("ix_user_profile_memories_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(Text)
    source_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class UserMemory(Base):
    """1 dòng = 1 phiên bản của một fact dài hạn về đúng 1 user.

    Danh tính của fact nằm ở `memory_key` chứ không ở `id`: nhiều dòng cùng
    `memory_key` là các phiên bản nối tiếp của cùng một fact, phân biệt bằng
    `version`. Truy hồi chỉ lấy phiên bản còn hiệu lực tại thời điểm hỏi, nên
    câu hỏi về quá khứ vẫn trả đúng giá trị của quá khứ.

    `subject`/`predicate`/`object_json` là dạng bộ ba của §4. `search_text` là
    bản dựng phẳng của bộ ba đó, chỉ để so khớp từ khoá lúc truy hồi — không
    phải nguồn chuẩn, sửa fact thì dựng lại từ bộ ba.
    """

    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("memory_key", "version", name="uq_user_memory_key_version"),
        # Truy hồi luôn lọc theo user rồi tới trạng thái, nên đặt user trước.
        Index("ix_user_memories_user_status", "user_id", "status"),
        Index("ix_user_memories_user_kind", "user_id", "kind"),
        Index("ix_user_memories_user_reinforced", "user_id", "last_reinforced_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Định danh bền của fact, giữ nguyên qua mọi phiên bản. API dùng giá trị này
    # khi người dùng xác nhận hay từ chối một fact, không dùng `id`.
    memory_key: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    kind: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(255))
    predicate: Mapped[str] = mapped_column(String(64))
    object_json: Mapped[dict] = mapped_column(JSON, default=dict)
    search_text: Mapped[str] = mapped_column(Text, default="")
    # Vector của `search_text`, cùng model nhúng với `chunks.embedding` theo
    # ADR-006. Rỗng cho tới khi job nhúng nền chạy; truy hồi từ khoá vẫn tìm
    # được trong khoảng đó. Xoá memory là xoá luôn vector vì nó nằm cùng dòng —
    # đó chính là lý do ADR-006 chọn pgvector thay vì một kho vector riêng.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIMS), default=None)
    # Model đã sinh ra vector đang lưu. Lệch với model trong config nghĩa là
    # vector cũ vô nghĩa và phải nhúng lại, vì so cosine giữa hai không gian
    # nhúng khác nhau cho ra số vô nghĩa chứ không báo lỗi.
    embedding_model: Mapped[str | None] = mapped_column(String(128), default=None)

    status: Mapped[str] = mapped_column(String(16), default="candidate")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    # user | official | inferred — quyết định fact nào thắng khi mâu thuẫn, xem
    # `AUTHORITY_RANK` trong services/memory_store.py.
    source_authority: Mapped[str] = mapped_column(String(16), default="inferred")
    # user | rule | model | import, theo §4. Giữ tách khỏi source_authority vì
    # một rule vẫn có thể đọc từ nguồn chính thức.
    created_by: Mapped[str] = mapped_column(String(16), default="rule")

    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # None nghĩa là còn hiệu lực. Được set khi có phiên bản mới thay thế.
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_reinforced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Số lần fact này được quan sát lại y hệt. Càng lặp lại càng đáng tin, nên nó
    # là một thừa số của công thức xếp hạng §7.
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=1)
    # Số lần người dùng nói fact này sai. Chỉ hạ điểm chứ không tự xoá, vì xoá
    # ngầm là mất dấu vết kiểm chứng.
    negative_feedback_count: Mapped[int] = mapped_column(Integer, default=0)

    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("user_memories.id", ondelete="SET NULL"), default=None)
    # Phiên bản của bộ trích xuất đã sinh ra dòng này. Đổi luật trích thì tăng
    # giá trị, để sau còn lọc ra những dòng do luật cũ sinh.
    extractor_version: Mapped[str] = mapped_column(String(32), default="")
    source_conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), default=None
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class UserMemoryEvidence(Base):
    """Nối một phiên bản memory với bằng chứng đã sinh ra nó.

    memory-lifecycle §11 đòi mọi canonical memory có ít nhất một bằng chứng đọc
    lại được. Bảng này giữ tham chiếu chứ không chép nội dung, nên khi bằng
    chứng gốc bị thu hồi thì memory mất căn cứ ngay chứ không còn bản sao mồ côi.
    """

    __tablename__ = "user_memory_evidence"
    __table_args__ = (UniqueConstraint("memory_id", "evidence_type", "evidence_ref", name="uq_user_memory_evidence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    memory_id: Mapped[int] = mapped_column(ForeignKey("user_memories.id", ondelete="CASCADE"), index=True)
    # conversation_message | source_item | chunk | user_input
    evidence_type: Mapped[str] = mapped_column(String(32))
    # Khoá của bằng chứng trong bảng tương ứng, để chuỗi vì mỗi nguồn một kiểu id.
    evidence_ref: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
