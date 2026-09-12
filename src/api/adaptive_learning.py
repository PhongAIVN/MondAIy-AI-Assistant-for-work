"""API học thích ứng P1 — điều khiển consent, inbox candidate và reset.

Mọi endpoint lấy danh tính từ token (không bao giờ tin `user_id` client gửi)
và chuyển claim string thành int đúng một lần ở đây. Toàn bộ truy vấn đều
lọc theo user đó — rò chéo user là blocker ngưỡng 0 của ADR-017.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.config import get_settings
from src.db import get_db
from src.models.learning import LEARNING_CAPABILITIES
from src.models.schemas import (
    CandidateRejectRequest,
    ConsentListResponse,
    ConsentStateResponse,
    ConsentUpdateRequest,
    LearningAuditEventResponse,
    LearningAuditListResponse,
    LearningCandidateListResponse,
    LearningCandidateResponse,
    LearningResetResponse,
)
from src.services import learning as learning_service
from src.services.learning import LearningCapabilityError

router = APIRouter(prefix="/adaptive-learning", tags=["adaptive-learning"])


def _consent_response(db: Session, user_id: int) -> ConsentListResponse:
    states = learning_service.get_consents(db, user_id)
    return ConsentListResponse(
        consents=[
            ConsentStateResponse(
                capability=capability,
                enabled=bool(states[capability].enabled) if capability in states else False,
                policy_version=states[capability].policy_version if capability in states else None,
                consented_at=states[capability].consented_at if capability in states else None,
                revoked_at=states[capability].revoked_at if capability in states else None,
            )
            for capability in LEARNING_CAPABILITIES
        ]
    )


@router.get("/consent", response_model=ConsentListResponse)
def get_consent(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConsentListResponse:
    return _consent_response(db, int(user_id))


@router.patch("/consent", response_model=ConsentListResponse)
def update_consent(
    request: ConsentUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConsentListResponse:
    # Validate capability TRƯỚC cờ tổng: lỗi input phải là 422 bất kể trạng
    # thái năng lượng của hệ thống, 403 chỉ dành cho input hợp lệ nhưng bị khoá.
    if request.capability not in LEARNING_CAPABILITIES:
        raise HTTPException(status_code=422, detail=f"Capability không hợp lệ: {request.capability}")
    if request.enabled and not get_settings().adaptive_learning_enabled:
        # Cờ tổng ADR-017 đang tắt: consent không có giá trị khi năng lực chưa
        # được mở, chặn từ API để UI nói rõ thay vì nhận lượt bật "ma".
        raise HTTPException(status_code=403, detail="Năng lực học thích ứng chưa được mở.")
    try:
        learning_service.set_consent(db, int(user_id), capability=request.capability, enabled=request.enabled)
    except LearningCapabilityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _consent_response(db, int(user_id))


@router.get("/candidates", response_model=LearningCandidateListResponse)
def list_candidates(
    limit: int = Query(default=50, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningCandidateListResponse:
    rows = learning_service.list_active_candidates(db, int(user_id), limit=limit)
    # Dựng tay thay vì model_validate: cột ORM là payload_json còn field API là
    # payload — để mapping tường minh thì không cần alias hai chiều lắt nhắt.
    return LearningCandidateListResponse(
        candidates=[
            LearningCandidateResponse(
                id=row.id,
                candidate_key=row.candidate_key,
                version=row.version,
                candidate_type=row.candidate_type,
                status=row.status,
                payload=row.payload_json,
                confidence=row.confidence,
                expires_at=row.expires_at,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.post("/candidates/{candidate_id}/reject", response_model=LearningCandidateResponse)
def reject_candidate(
    candidate_id: int,
    request: CandidateRejectRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningCandidateResponse:
    row = learning_service.reject_candidate(
        db, int(user_id), candidate_id, reason_codes=request.reason_codes
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đề xuất hoặc đã được quyết.")
    return LearningCandidateResponse(
        id=row.id,
        candidate_key=row.candidate_key,
        version=row.version,
        candidate_type=row.candidate_type,
        status=row.status,
        payload=row.payload_json,
        confidence=row.confidence,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.delete("", response_model=LearningResetResponse)
def reset_learning(
    scope: str = Query(default="all"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningResetResponse:
    try:
        forgotten = learning_service.forget_candidates_by_scope(db, int(user_id), scope)
    except LearningCapabilityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LearningResetResponse(scope=scope, forgotten=forgotten)


@router.get("/audit", response_model=LearningAuditListResponse)
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LearningAuditListResponse:
    rows = learning_service.list_audit_events(db, int(user_id), limit=limit)
    return LearningAuditListResponse(
        events=[LearningAuditEventResponse.model_validate(row, from_attributes=True) for row in rows]
    )
