from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# CP0 (checkpoint đầu TAPB-121): schema audit cho từng bước pipeline, tách khỏi
# messages/tasks (dữ liệu nghiệp vụ cuối). Mục đích thuần audit/provenance —
# tra được 1 run đã fetch/lọc/trích xuất gì, không phải để resume khi crash
# giữa chừng (xem quyết định trong PR).
_now = lambda: datetime.now(UTC)  # noqa: E731


class PipelineRawMessage(Base):
    """1 dòng = 1 item thô lấy về từ connector, trước normalize."""

    __tablename__ = "pipeline_raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("connections.id", ondelete="SET NULL"), default=None)
    provider: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(255))
    raw_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineNormalizedMessage(Base):
    """1 dòng = 1 item sau normalize (shape chung provider/text/sent_at/deep_link)."""

    __tablename__ = "pipeline_normalized_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    raw_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_raw_messages.id", ondelete="SET NULL"), default=None
    )
    provider: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    external_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str | None] = mapped_column(String(255), default=None)
    author_id: Mapped[str | None] = mapped_column(String(128), default=None)
    author_name: Mapped[str | None] = mapped_column(String(255), default=None)
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dm: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deep_link: Mapped[str | None] = mapped_column(String(1024), default=None)
    normalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineAttachmentExtract(Base):
    """1 dòng = 1 attachment đã được thử xử lý (kể cả bị skip/fail — `status`
    ghi lại lý do). Lưu text đã trích, KHÔNG lưu bytes gốc của file; cùng tier
    nhạy cảm với `PipelineNormalizedMessage.text` (ephemeral theo run, xoá
    cascade theo `runs.id`)."""

    __tablename__ = "pipeline_attachment_extracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    normalized_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_normalized_messages.id", ondelete="SET NULL"), default=None
    )
    filename: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # ok | ok_empty | skipped_type | skipped_size | skipped_other | failed
    status: Mapped[str] = mapped_column(String(32))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extracted_chars: Mapped[int] = mapped_column(Integer, default=0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # [{"class": "action"|"deadline"|"key_point", "text": ..., "section": ...}]
    # — kết quả LangExtract theo section (trang/sheet/heading), None khi
    # structured extraction tắt/lỗi/fallback về nối phẳng.
    structured_extract: Mapped[list | None] = mapped_column(JSON, default=None)


class PipelineFilteredMessage(Base):
    """1 dòng = 1 item lọt qua filter heuristic (điểm >= ngưỡng)."""

    __tablename__ = "pipeline_filtered_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    normalized_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_normalized_messages.id", ondelete="SET NULL"), default=None
    )
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_batches.id", ondelete="SET NULL"), default=None)
    score: Mapped[int] = mapped_column(Integer)
    filtered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineBatch(Base):
    """1 dòng = 1 lô 15-20 tin gửi cho LLM trong extract_batch."""

    __tablename__ = "pipeline_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    batch_index: Mapped[int] = mapped_column(Integer)
    item_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineExtractedItem(Base):
    """1 dòng = 1 tín hiệu việc-cần-làm LLM rút ra từ 1 message trong batch."""

    __tablename__ = "pipeline_extracted_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_batches.id", ondelete="SET NULL"), default=None)
    filtered_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_filtered_messages.id", ondelete="SET NULL"), default=None
    )
    title: Mapped[str] = mapped_column(String(500))
    assignee_hint: Mapped[str | None] = mapped_column(String(255), default=None)
    time_expression: Mapped[str | None] = mapped_column(String(500), default=None)
    evidence_quote: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineResolvedItem(Base):
    """1 dòng = 1 extracted_item sau khi chuẩn hoá due_at/ambiguous (time_resolve) và
    người phụ trách/assignee (identity_resolve)."""

    __tablename__ = "pipeline_resolved_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    extracted_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("pipeline_extracted_items.id", ondelete="SET NULL"), default=None
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    assignee: Mapped[str | None] = mapped_column(String(255), default=None)
    assignee_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
