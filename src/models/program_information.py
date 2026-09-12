"""Thông tin chương trình do đội ngũ biên tập và các yêu cầu cần người trả lời.

Nội dung đã tạo phiên bản không được sửa tại chỗ. ``ProgramInformationItem``
chỉ giữ con trỏ tới bản mới nhất và bản đang phát hành; nhờ vậy đội ngũ có thể
soạn bản mới mà người học vẫn đọc được bản đã duyệt trước đó.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class ProgramInformationItem(Base):
    """Đầu mục thông tin ổn định, tách vòng đời khỏi nội dung phiên bản."""

    __tablename__ = "program_information_items"
    __table_args__ = (Index("ix_program_information_scope_status", "cohort_slug", "visibility", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_slug: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    visibility: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="draft")
    latest_version: Mapped[int] = mapped_column(Integer, default=1)
    published_version: Mapped[int | None] = mapped_column(Integer, default=None)
    created_by: Mapped[str] = mapped_column(String(64))
    updated_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class ProgramInformationVersion(Base):
    """Ảnh chụp nội dung bất biến của một đầu mục."""

    __tablename__ = "program_information_versions"
    __table_args__ = (
        UniqueConstraint("item_id", "version", name="uq_program_information_item_version"),
        Index("ix_program_information_version_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("program_information_items.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(32), index=True)
    visibility: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    source_url: Mapped[str | None] = mapped_column(String(2048), default=None)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ProgramInformationRequest(Base):
    """Câu hỏi người dùng chủ động đồng ý chia sẻ cho đội ngũ xử lý."""

    __tablename__ = "program_information_requests"
    __table_args__ = (Index("ix_program_information_request_queue", "cohort_slug", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cohort_slug: Mapped[str] = mapped_column(String(64), index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shared_question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), index=True, default="open")
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_item_id: Mapped[int | None] = mapped_column(ForeignKey("program_information_items.id"), default=None)
    resolved_by: Mapped[str | None] = mapped_column(String(64), default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


def _reject_version_mutation(*_args: object, **_kwargs: object) -> None:
    """Chặn ORM sửa/xóa phiên bản; thay đổi nội dung phải tạo dòng mới."""
    raise RuntimeError("ProgramInformationVersion là bất biến; hãy tạo phiên bản mới.")


event.listen(ProgramInformationVersion, "before_update", _reject_version_mutation)
event.listen(ProgramInformationVersion, "before_delete", _reject_version_mutation)
