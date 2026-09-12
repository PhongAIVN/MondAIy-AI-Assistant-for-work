"""Public, read-only shared conversation pages."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_db
from src.models.conversation import Conversation, ConversationMessage
from src.models.schemas import ConversationTurn, SharedConversationResponse

router = APIRouter(prefix="/shared-chat", tags=["shared-chat"])


@router.get("/{token}", response_model=SharedConversationResponse)
def get_shared_chat(token: str, db: Session = Depends(get_db)) -> SharedConversationResponse:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.share_token == token,
            Conversation.share_visibility == "public",
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đoạn chat được chia sẻ.")

    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
    ).all()
    return SharedConversationResponse(
        title=conversation.title,
        messages=[
            ConversationTurn(
                id=message.id,
                role=message.role,
                content=message.content,
                # Public links expose rendered conversation text only; internal
                # routing, provenance and productivity metadata stay private.
                extras=None,
                feedback=None,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )
