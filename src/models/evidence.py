"""Lớp bằng chứng: item thô từ connector và chunk dùng để truy hồi.

Tên bảng lấy theo architecture.md §5 (`source_items`, `source_item_versions`) và
PRD §10 (`chunks`). Hai tài liệu gọi khác nhau ở lớp tài liệu — PRD dùng
`documents`/`document_versions` — nên chỗ này bám architecture vì đây là bảng
connector ghi vào. Xem TODO(OD-EV1) dưới `SourceItem`.
"""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# JSONB trên Postgres để lọc được bằng toán tử `?|` và đánh index GIN; sqlite
# rơi về JSON thường để test không cần Postgres.
JsonList = JSON().with_variant(JSONB(), "postgresql")

# Số chiều của vector nhúng, PHẢI khớp model của provider đang cấu hình. Hằng số
# cố định là bẫy: `EMBEDDING_PROVIDER` mặc định vẫn là openrouter (model trả 2048)
# nên cài mới sẽ tạo cột 1024 rồi nhúng 2048 vào — hỏng ngay lệnh ghi đầu tiên.
#
# Giá trị này chỉ dùng lúc TẠO BẢNG lần đầu. Với database đã có, `embed_chunks.py`
# tự dò số chiều thật của model rồi ALTER cột (và drop index cũ trước, xem lý do
# trong chính hàm đó).
_DIMS_THEO_PROVIDER = {"openrouter": 2048, "fpt": 1024}


def _vector_dims() -> int:
    from src.config import get_settings

    return _DIMS_THEO_PROVIDER[get_settings().embedding_provider]


VECTOR_DIMS = _vector_dims()


class SourceScope(Base):
    """1 dòng = 1 phạm vi nguồn đã đăng ký, ví dụ một kênh Discord.

    Mức A/B gán ở đây chứ không gán wait connector — Program Frame §5.
    """

    __tablename__ = "source_scopes"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_scope_provider_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    parent_external_id: Mapped[str | None] = mapped_column(String(64), default=None)
    guild_external_id: Mapped[str | None] = mapped_column(String(64), default=None)
    kind: Mapped[int | None] = mapped_column(Integer, default=None)
    is_thread: Mapped[bool] = mapped_column(default=False)
    # Mức mặc định là B. Nâng lên A phải do quản trị chương trình khai báo và
    # ghi vào Program Frame §6 — hiện danh sách đó còn trống, xem OI-02.
    tier: Mapped[str] = mapped_column(String(1), default="B")


class SourceItem(Base):
    """1 dòng = 1 item thô từ nguồn, với Discord là 1 tin nhắn.

    Trường bám FR-010: nhà cung cấp, mã ngoài, đường dẫn mở lại, nội dung cần
    thiết, thời điểm nguồn cập nhật, thời điểm quan sát và mã băm.
    """

    __tablename__ = "source_items"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_item_provider_external"),
        Index("ix_item_scope_time", "scope_id", "source_updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    scope_id: Mapped[int] = mapped_column(ForeignKey("source_scopes.id"), index=True)

    author_external_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    author_name: Mapped[str | None] = mapped_column(String(255), default=None)
    # Role tại thời điểm cào. Là bằng chứng để đề xuất, không phải thẩm quyền —
    # BR-04 cấm suy vai trò chương trình từ hoạt động quan sát được.
    author_roles: Mapped[list | None] = mapped_column(JsonList, default=None)

    content: Mapped[str] = mapped_column(Text, default="")
    item_type: Mapped[int | None] = mapped_column(Integer, default=None)
    reply_to_external_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    attachment_count: Mapped[int] = mapped_column(Integer, default=0)

    deep_link: Mapped[str | None] = mapped_column(String(512), default=None)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[str] = mapped_column(String(32), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class SourceItemVersion(Base):
    """1 dòng = 1 phiên bản nội dung của một item.

    FR-013: cùng mã ngoài nhưng mã băm mới thì tạo phiên bản mới; mã băm cũ chỉ
    cập nhật lần quan sát. Không ghi đè để giữ được lịch sử tin đã sửa.
    """

    __tablename__ = "source_item_versions"
    __table_args__ = (UniqueConstraint("item_id", "content_hash", name="uq_version_item_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text, default="")
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Chunk(Base):
    """1 dòng = 1 đơn vị truy hồi, gom từ nhiều item theo chunker.

    `mode` ghi lại cách gom — `buoi`, `mach` hay `nguyen_khoi` — để sau này đổi
    luật chunk thì biết dòng nào cần dựng lại.
    """

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("run_id", "chunk_key", name="uq_chunk_run_key"),
        Index("ix_chunk_scope_time", "scope_id", "first_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    chunk_key: Mapped[str] = mapped_column(String(64))
    scope_id: Mapped[int] = mapped_column(ForeignKey("source_scopes.id"), index=True)

    mode: Mapped[str] = mapped_column(String(16))
    group_key: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    author_ids: Mapped[list | None] = mapped_column(JsonList, default=None)
    author_roles: Mapped[list | None] = mapped_column(JsonList, default=None)

    first_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deep_link: Mapped[str | None] = mapped_column(String(512), default=None)

    # Rỗng wait tới khi chạy bước nhúng. Truy hồi bằng FTS vẫn chạy được khi cột
    # này còn trống, nên hai bước tách rời được.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(VECTOR_DIMS), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ChunkItem(Base):
    """Nối chunk với từng item trong nó, để trích dẫn trỏ về đúng tin nhắn."""

    __tablename__ = "chunk_items"
    __table_args__ = (UniqueConstraint("chunk_id", "item_id", name="uq_chunk_item"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunks.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("source_items.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
