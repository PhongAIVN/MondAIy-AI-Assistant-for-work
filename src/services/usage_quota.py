"""Durable per-user quotas shared by every API replica."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.user import User


def _reset_daily_quota_if_needed(user: User, quota_day: str) -> None:
    if user.llm_quota_day != quota_day:
        user.llm_quota_day = quota_day
        user.llm_questions_used = 0
        user.llm_bonus_questions = 0


def consume_llm_question(db: Session, user_id: int | str) -> None:
    """Consume one daily question atomically; administrators are unlimited."""
    user = db.execute(select(User).where(User.id == int(user_id)).with_for_update()).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    if user.is_admin:
        return

    settings = get_settings()
    quota_day = datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()
    _reset_daily_quota_if_needed(user, quota_day)
    daily_limit = settings.llm_questions_per_day + user.llm_bonus_questions
    if user.llm_questions_used >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=(
                "Bạn hãy góp ý cải thiện sản phẩm của chúng tôi sẽ nhận được thêm 5 lượt "
                "dùng nữa. Đóng góp của bạn là quý giá với đội ngũ phát triển của chúng tôi."
            ),
        )
    user.llm_questions_used += 1
    db.commit()


def grant_llm_questions(db: Session, user_id: int | str, amount: int = 5) -> int:
    """Grant a same-day allowance and return the number of questions remaining.

    The caller must make this part of the same transaction as the accepted
    feedback row so a feedback submission cannot be rewarded without an audit
    record. This function deliberately does not commit.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    user = db.execute(select(User).where(User.id == int(user_id)).with_for_update()).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")

    settings = get_settings()
    quota_day = datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()
    _reset_daily_quota_if_needed(user, quota_day)
    user.llm_bonus_questions += amount
    return max(
        0,
        settings.llm_questions_per_day + user.llm_bonus_questions - user.llm_questions_used,
    )


def consume_meeting_summary(db: Session, user_id: int | str) -> None:
    """Reserve the single daily meeting-summary attempt for a regular user."""
    user = db.execute(select(User).where(User.id == int(user_id)).with_for_update()).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    if user.is_admin:
        return

    settings = get_settings()
    today = datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()
    if user.meeting_summary_quota_day != today:
        user.meeting_summary_quota_day = today
        user.meeting_summaries_used = 0
    if user.meeting_summaries_used >= 1:
        raise HTTPException(
            status_code=429,
            detail=(
                "Bạn đã dùng lượt tóm tắt cuộc họp hôm nay. "
                "Nếu cần dùng thêm, hãy liên hệ đội ngũ phát triển."
            ),
        )
    user.meeting_summaries_used += 1
    db.commit()


def consume_feedback_attempt(db: Session, user_id: int | str) -> bool:
    """Reserve today's quality mode and return whether the strict gate applies."""
    user = db.execute(select(User).where(User.id == int(user_id)).with_for_update()).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")

    settings = get_settings()
    quality_day = datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()
    if user.feedback_quality_day != quality_day:
        user.feedback_quality_day = quality_day
        user.feedback_attempts = 0
    db.commit()
    return user.feedback_attempts < 2


def record_feedback_quality_rejection(db: Session, user_id: int | str) -> None:
    """Count a strict quality rejection, capped at two for today's user state."""
    user = db.execute(select(User).where(User.id == int(user_id)).with_for_update()).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")

    settings = get_settings()
    quality_day = datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()
    if user.feedback_quality_day != quality_day:
        user.feedback_quality_day = quality_day
        user.feedback_attempts = 0
    user.feedback_attempts = min(2, user.feedback_attempts + 1)
    db.commit()
