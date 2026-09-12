from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.db import get_db
from src.models.message import Message
from src.models.schemas import MessageListResponse, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=MessageListResponse)
@limiter.limit("60/minute")
def list_messages(
    request: Request,
    provider: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    stmt = select(Message).where(Message.user_id == user_id)
    if provider is not None:
        stmt = stmt.where(Message.provider == provider)
    stmt = stmt.order_by(Message.sent_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return MessageListResponse(messages=[MessageResponse.model_validate(row, from_attributes=True) for row in rows])


@router.get("/{message_id}", response_model=MessageResponse)
@limiter.limit("60/minute")
def get_message(
    request: Request,
    message_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> MessageResponse:
    row = db.execute(select(Message).where(Message.id == message_id, Message.user_id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy message.")
    return MessageResponse.model_validate(row, from_attributes=True)
