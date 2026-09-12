import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.db import get_db
from src.models.app_rating import AppRating
from src.models.schemas import CamelModel
from src.services.feedback_quality import (
    FeedbackAssessment,
    FeedbackAssessmentUnavailableError,
    assess_feedback_quality,
    feedbacks_are_duplicates,
)
from src.services.usage_quota import (
    consume_feedback_attempt,
    grant_llm_questions,
    record_feedback_quality_rejection,
)

router = APIRouter(prefix="/ratings", tags=["ratings"])
logger = logging.getLogger(__name__)

_FEEDBACK_REWARD = 5
_REJECTION_MESSAGES = {
    "too_generic": "Hãy góp ý cụ thể một tính năng, trải nghiệm hoặc điều bạn muốn sản phẩm cải thiện.",
    "rating_mismatch": "Số sao và nội dung góp ý đang chưa khớp nhau. Hãy kiểm tra lại để đội ngũ hiểu đúng đánh giá của bạn.",
    "duplicate": "Phản hồi này trùng với phản hồi bạn đã gửi và không được cộng thêm lượt.",
    "filler": "ê chúng tôi đọc được buồn đó nha, đánh giá thật công tâm vào",
    "prompt_injection": "ê chúng tôi đọc được buồn đó nha, đánh giá thật công tâm vào",
    "other": "ê chúng tôi đọc được buồn đó nha, đánh giá thật công tâm vào",
}


class RatingCreateRequest(CamelModel):
    rating: int = Field(..., ge=1, le=5)
    # Giữ ngưỡng vừa đủ để loại input rỗng nhưng không chặn feedback thật.
    feedback: str = Field(..., min_length=20, max_length=2000)
    trigger: Literal["action_count", "time_elapsed", "manual"] = "action_count"
    session_id: str | None = Field(default=None, max_length=128)
    meaningful_action_count: int = Field(default=0, ge=0, le=10000)
    session_duration_seconds: int = Field(default=0, ge=0, le=86400)


class RatingResponse(CamelModel):
    id: int
    rating: int
    feedback: str | None
    bonus_questions_awarded: int
    questions_remaining: int


def _recent_feedback(db: Session, user_id: str) -> list[str]:
    return list(
        db.scalars(
            select(AppRating.feedback)
            .where(AppRating.user_id == user_id, AppRating.feedback.is_not(None))
            .order_by(AppRating.created_at.desc(), AppRating.id.desc())
            .limit(20)
        ).all()
    )


def _reject_duplicate(feedback: str, previous_feedback: list[str]) -> None:
    if any(feedbacks_are_duplicates(feedback, previous) for previous in previous_feedback):
        raise HTTPException(
            status_code=409,
            detail="Phản hồi này trùng với phản hồi bạn đã gửi và không được cộng thêm lượt.",
        )


@router.post("", response_model=RatingResponse, status_code=201)
@limiter.limit("10/minute")
async def create_rating(
    request: Request,
    payload: RatingCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RatingResponse:
    feedback = payload.feedback.strip()
    if len(feedback) < 20:
        raise HTTPException(status_code=422, detail="Phản hồi phải dài ít nhất 20 ký tự.")

    strict_quality_gate = consume_feedback_attempt(db, user_id)

    # Reject obvious repeats before paying for a model call. The check is run
    # again after locking the user row to close concurrent double submissions.
    recent_feedback = _recent_feedback(db, user_id)
    _reject_duplicate(feedback, recent_feedback)
    # Release the read transaction/connection before waiting on the external
    # model. A fresh transaction below locks the user row for the actual grant.
    db.rollback()
    if strict_quality_gate:
        try:
            assessment = await assess_feedback_quality(feedback, payload.rating, recent_feedback)
        except FeedbackAssessmentUnavailableError as exc:
            logger.warning("Không đọc được verdict feedback: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Chưa thể xác thực phản hồi lúc này. Vui lòng thử lại sau.",
            ) from exc
        except Exception as exc:
            logger.exception("LLM đánh giá feedback bị lỗi")
            raise HTTPException(
                status_code=503,
                detail="Chưa thể xác thực phản hồi lúc này. Vui lòng thử lại sau.",
            ) from exc
    else:
        if len(feedback) < 40:
            raise HTTPException(status_code=422, detail="Phản hồi phải dài ít nhất 40 ký tự.")
        assessment = FeedbackAssessment(True, "Đã vượt qua ngưỡng độ dài tối thiểu.")
    if not assessment.accepted:
        record_feedback_quality_rejection(db, user_id)
        raise HTTPException(
            status_code=422,
            detail=_REJECTION_MESSAGES.get(assessment.code, _REJECTION_MESSAGES["other"]),
        )

    questions_remaining = grant_llm_questions(db, user_id, _FEEDBACK_REWARD)
    _reject_duplicate(feedback, _recent_feedback(db, user_id))
    row = AppRating(
        user_id=user_id,
        rating=payload.rating,
        feedback=feedback,
        trigger=payload.trigger,
        session_id=payload.session_id,
        meaningful_action_count=payload.meaningful_action_count,
        session_duration_seconds=payload.session_duration_seconds,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RatingResponse(
        id=row.id,
        rating=row.rating,
        feedback=row.feedback,
        bonus_questions_awarded=_FEEDBACK_REWARD,
        questions_remaining=questions_remaining,
    )
