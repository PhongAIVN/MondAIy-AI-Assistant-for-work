"""Bảng nền tảng của học thích ứng P1 (ADR-017 + execution plan P1, Slice 1).

Nguyên tắc bắt buộc của cả module:

- Mọi bảng dùng `user_id` integer khoá ngoại sang `users.id` — API chuyển claim
  string thành int đúng một lần ở biên. Không lặp lại convention string/int
  trộn lẫn của schema cũ.
- Không có cột nào lưu raw transcript hay compiled prompt. Signal chỉ chứa
  trường có cấu trúc đã redact; audit chỉ ghi id/version/reason code.
- Candidate chưa được chấp nhận không bao giờ được đọc bởi context assembly.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base

# Bốn năng lực học độc lập — mỗi cái một công tắc consent riêng, mặc định tắt.
LEARNING_CAPABILITIES = ("chat_learning", "adaptive_style", "learned_skills", "routine_learning")

# Loại candidate dùng chung một inbox; payload_json có schema riêng theo type.
CANDIDATE_TYPES = ("style_preference", "skill", "routine")

# Trạng thái của candidate theo state machine trong execution plan P1.
CANDIDATE_STATUSES = (
    "candidate",
    "evaluation_failed",
    "pending_review",
    "accepted",
    "rejected",
    "superseded",
    "expired",
    "forgotten",
)


def _now() -> datetime:
    return datetime.now(UTC)


class LearningConsent(Base):
    """Một dòng = trạng thái đồng ý của một user cho đúng một năng lực học.

    Thu hồi (enabled=False) phải dừng quan sát mới ngay: mọi worker đều kiểm
    tra dòng này trước khi đọc thêm dữ liệu nguồn. `policy_version` cho phép
    đổi chính sách consent mà không mất dấu ai đã đồng ý theo bản nào.
    """

    __tablename__ = "learning_consents"
    __table_args__ = (
        UniqueConstraint("user_id", "capability", name="uq_learning_consent_user_capability"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    capability: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_version: Mapped[str] = mapped_column(String(16), default="v1")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LearningReviewCursor(Base):
    """Con nước review theo (user, capability) để chạy lại không sinh trùng.

    Worker chỉ đọc message có id > `high_water_message_id`; lease/last_error là
    chỗ chẩn đoán khi worker chết giữa chừng. Retry idempotent nhờ con nước
    chỉ tăng sau khi commit thành công.
    """

    __tablename__ = "learning_review_cursors"
    __table_args__ = (
        UniqueConstraint("user_id", "capability", name="uq_learning_cursor_user_capability"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    capability: Mapped[str] = mapped_column(String(32))
    high_water_message_id: Mapped[int | None] = mapped_column(Integer, default=None)
    extractor_version: Mapped[str] = mapped_column(String(32), default="v1")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Thông báo lỗi đã cắt ngắn ở lớp service — không đổ nguyên traceback vì có
    # thể mang nội dung hội thoại.
    last_error_summary: Mapped[str | None] = mapped_column(String(200), default=None)


class LearningSignal(Base):
    """Tín hiệu có cấu trúc đã redact rút ra từ dữ liệu nguồn.

    Đây là đơn vị nhỏ nhất của lớp học: không giữ câu chữ gốc, chỉ giữ loại
    tín hiệu thuộc allowlist và giá trị đã chuẩn hoá. `source_message_id` xoá
    theo message nguồn (CASCADE) — message biến mất thì tín hiệu mất giá trị
    bằng chứng ngay tại tầng DB, không đợi job dọn.
    """

    __tablename__ = "learning_signals"
    __table_args__ = (
        Index("ix_learning_signals_user_type", "user_id", "signal_type"),
        Index("ix_learning_signals_source_message", "source_message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Chat message thật nằm ở conversation_messages (bảng `messages` là email
    # ingest từ connector — trỏ nhầm bảng là lỗi FK trên PostgreSQL).
    source_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), default=None
    )
    signal_type: Mapped[str] = mapped_column(String(48))
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome_code: Mapped[str | None] = mapped_column(String(32), default=None)
    extractor_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LearningCandidate(Base):
    """Một đề xuất học đang chờ duyệt hoặc đã được quyết.

    `(user_id, candidate_key, version)` ổn định: sửa đề xuất tạo version mới,
    không ghi đè lịch sử. Candidate là cổng bắt buộc trước khi bất kỳ suy luận
    nào được phép ảnh hưởng response — context assembly chỉ đọc status
    `accepted`.
    """

    __tablename__ = "learning_candidates"
    __table_args__ = (
        UniqueConstraint("user_id", "candidate_key", "version", name="uq_learning_candidate_version"),
        Index("ix_learning_candidates_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    candidate_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    candidate_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    extractor_version: Mapped[str] = mapped_column(String(32), default="v1")
    review_reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    supersedes_id: Mapped[int | None] = mapped_column(Integer, default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class LearningEvidence(Base):
    """Nối candidate với nguồn bằng chứng của nó.

    Evidence trỏ về message nguồn và xoá cùng message (CASCADE) nên reference
    đứt dây gần như không thể tồn tại; service vẫn coi candidate thiếu evidence
    là không đủ điều kiện promotion. Chỉ message của user và hành vi quan sát
    được của user là bằng chứng hợp lệ — đây là ràng buộc ở lớp worker, không
    phải ở cột.
    """

    __tablename__ = "learning_evidence"
    __table_args__ = (Index("ix_learning_evidence_candidate", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learning_candidates.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(24))
    source_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), default=None
    )
    extractor_version: Mapped[str] = mapped_column(String(32), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AssistantContextRef(Base):
    """Phiên bản memory/style/skill đã inject vào một message assistant.

    Là cơ sở duy nhất an toàn để quy feedback về đúng cá nhân hoá đã dùng:
    ghi trong cùng transaction với message, không đoán lại sau. Chỉ lưu id
    phiên bản, không lưu prompt đã compile.
    """

    __tablename__ = "assistant_context_refs"
    __table_args__ = (
        UniqueConstraint("assistant_message_id", name="uq_assistant_context_ref_message"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assistant_message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation_messages.id", ondelete="CASCADE")
    )
    memory_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    style_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    skill_version_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LearningAuditEvent(Base):
    """Nhật ký append-only của vòng học: ai làm gì với đối tượng nào, vì sao.

    Cố ý không có endpoint sửa/xoá. Nội dung chỉ là mã lý do và tham chiếu —
    đủ để audit rollback/reset mà không nhân bản nội dung riêng tư.
    """

    __tablename__ = "learning_audit_events"
    __table_args__ = (Index("ix_learning_audit_user_time", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(24))
    target_ref: Mapped[str] = mapped_column(String(128))
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
