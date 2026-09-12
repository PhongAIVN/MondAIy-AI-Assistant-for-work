"""Nghiệp vụ học thích ứng P1 — consent, audit, candidate review, reset.

Ranh giới của Slice 1 (ADR-017): chưa có worker học và chưa có context
assembly đọc bảng này. Việc của service ở đây là nền tảng lưu trữ + điều
khiển của user phải đúng và kiểm tra được, để các slice sau chỉ gắn vào.

Quy ước quan trọng: mọi hàm nhận `user_id` đã là int (đã chuyển ở biên API).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.learning import (
    CANDIDATE_TYPES,
    LEARNING_CAPABILITIES,
    LearningAuditEvent,
    LearningCandidate,
    LearningConsent,
)

# Chính sách đã chốt trong ADR-017 ngày 22/08. Đổi giá trị = đổi ADR trước.
POLICY_VERSION = "v1"
PENDING_RETENTION_DAYS = 30
MAX_PENDING_CANDIDATES = 5

# Trạng thái còn "sống" — xuất hiện trong inbox; còn lại là trạng thái kết thúc.
ACTIVE_CANDIDATE_STATUSES = ("candidate", "evaluation_failed", "pending_review")

# Reset theo scope: mỗi lớp học xoá đúng candidate_type tương ứng.
SCOPE_TO_CANDIDATE_TYPES: dict[str, tuple[str, ...]] = {
    "style": ("style_preference",),
    "skills": ("skill",),
    "routines": ("routine",),
}
RESET_SCOPES = (*SCOPE_TO_CANDIDATE_TYPES.keys(), "all")


class LearningCapabilityError(ValueError):
    """Capability hoặc scope không nằm trong allowlist."""


def _as_utc(moment: datetime | None) -> datetime | None:
    """SQLite trả datetime naive dù cột khai timezone-aware — coi naive là UTC.

    Cùng cách xử lý của chat_sync/calendar_cache; so sánh thẳng sẽ raise
    TypeError trên SQLite và chỉ lộ khi chạy test, không phải lúc dev local.
    """
    if moment is None:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _require_capability(capability: str) -> str:
    if capability not in LEARNING_CAPABILITIES:
        raise LearningCapabilityError(f"Capability không hợp lệ: {capability}")
    return capability


def get_consents(db: Session, user_id: int) -> dict[str, LearningConsent]:
    """Trạng thái hiện hành của cả bốn công tắc — thiếu dòng nghĩa là mặc định tắt."""
    rows = db.execute(
        select(LearningConsent).where(LearningConsent.user_id == user_id)
    ).scalars().all()
    return {row.capability: row for row in rows}


def set_consent(
    db: Session, user_id: int, *, capability: str, enabled: bool, actor: str = "user"
) -> LearningConsent:
    """Bật/tắt một năng lực học. Thu hồi ghi `revoked_at` để truy được thời điểm."""
    _require_capability(capability)
    now = datetime.now(UTC)
    row = db.execute(
        select(LearningConsent).where(
            LearningConsent.user_id == user_id, LearningConsent.capability == capability
        )
    ).scalar_one_or_none()
    if row is None:
        row = LearningConsent(user_id=user_id, capability=capability, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
        row.policy_version = POLICY_VERSION

    if enabled:
        row.consented_at = now
        row.revoked_at = None
    else:
        # Chỉ stamp revoked_at khi đang bật -> tắt; tắt lần nữa đừng đè dấu cũ.
        if row.revoked_at is None:
            row.revoked_at = now
    row.updated_at = now

    db.add(
        LearningAuditEvent(
            user_id=user_id,
            actor=actor,
            action="consent_enabled" if enabled else "consent_revoked",
            target_type="capability",
            target_ref=capability,
            reason_codes=[f"policy:{POLICY_VERSION}"],
        )
    )
    db.commit()
    db.refresh(row)
    return row


def is_learning_enabled(db: Session, user_id: int, capability: str) -> bool:
    """Cổng DUY NHẤT mà worker/service kiểm tra trước khi học.

    Cờ tổng `adaptive_learning_enabled` là global kill switch của ADR-017:
    phải chặn cả ở đây chứ không chỉ ở API, nếu không tắt cờ khi có sự cố
    vẫn không dừng được worker đã đọc consent=True từ trước đó.
    """
    if not get_settings().adaptive_learning_enabled:
        return False
    _require_capability(capability)
    state = get_consents(db, user_id).get(capability)
    return bool(state and state.enabled)


def list_active_candidates(db: Session, user_id: int, limit: int = 50) -> list[LearningCandidate]:
    """Inbox duyệt: chỉ candidate còn sống của đúng user, hết hạn thì loại sẵn."""
    now = datetime.now(UTC)
    rows = list(
        db.execute(
            select(LearningCandidate)
            .where(
                LearningCandidate.user_id == user_id,
                LearningCandidate.status.in_(ACTIVE_CANDIDATE_STATUSES),
            )
            .order_by(LearningCandidate.created_at.desc())
            .limit(limit * 2)
        ).scalars()
    )
    alive: list[LearningCandidate] = []
    expired_any = False
    for row in rows:
        expires_at = _as_utc(row.expires_at)
        if expires_at is not None and expires_at <= now:
            row.status = "expired"
            row.decided_at = now
            expired_any = True
            continue
        alive.append(row)
        if len(alive) >= limit:
            break
    if expired_any:
        db.commit()
    return alive


def reject_candidate(
    db: Session, user_id: int, candidate_id: int, *, reason_codes: list[str] | None = None
) -> LearningCandidate | None:
    """Từ chối một candidate. Stable key giữ nguyên để latch chống nag ở slice sau."""
    row = db.execute(
        select(LearningCandidate).where(
            LearningCandidate.id == candidate_id, LearningCandidate.user_id == user_id
        )
    ).scalar_one_or_none()
    if row is None or row.status not in ACTIVE_CANDIDATE_STATUSES:
        return None
    row.status = "rejected"
    row.decided_at = datetime.now(UTC)
    row.review_reason_codes = reason_codes or ["user_rejected"]
    db.add(
        LearningAuditEvent(
            user_id=user_id,
            actor="user",
            action="candidate_rejected",
            target_type=row.candidate_type,
            target_ref=f"{row.candidate_key}:v{row.version}",
            reason_codes=row.review_reason_codes,
        )
    )
    db.commit()
    db.refresh(row)
    return row


def forget_candidates_by_scope(db: Session, user_id: int, scope: str) -> int:
    """Reset học theo lớp (FR-113): candidate trong scope chuyển `forgotten`.

    Đây là reset mềm phục vụ audit — không hard-delete lịch sử ngay; job dọn
    theo SLA 30 ngày thuộc slice retention sau. Signal/skill/style data thật
    sẽ được orchestrate thêm khi các bảng đó bắt đầu có dữ liệu accepted.
    """
    if scope not in RESET_SCOPES:
        raise LearningCapabilityError(f"Scope không hợp lệ: {scope}")
    types = (
        CANDIDATE_TYPES
        if scope == "all"
        else SCOPE_TO_CANDIDATE_TYPES[scope]
    )
    now = datetime.now(UTC)
    rows = list(
        db.execute(
            select(LearningCandidate).where(
                LearningCandidate.user_id == user_id,
                LearningCandidate.candidate_type.in_(types),
                LearningCandidate.status.notin_(("forgotten",)),
            )
        ).scalars()
    )
    for row in rows:
        row.status = "forgotten"
        row.decided_at = now
    db.add(
        LearningAuditEvent(
            user_id=user_id,
            actor="user",
            action="learning_reset",
            target_type="scope",
            target_ref=scope,
            reason_codes=["user_requested"],
        )
    )
    db.commit()
    return len(rows)


def list_audit_events(db: Session, user_id: int, limit: int = 50) -> list[LearningAuditEvent]:
    return list(
        db.execute(
            select(LearningAuditEvent)
            .where(LearningAuditEvent.user_id == user_id)
            .order_by(LearningAuditEvent.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def candidate_expiry(now: datetime | None = None) -> datetime:
    """Hạn sống mặc định của một candidate mới — pending retention ADR-017."""
    return (now or datetime.now(UTC)) + timedelta(days=PENDING_RETENTION_DAYS)
