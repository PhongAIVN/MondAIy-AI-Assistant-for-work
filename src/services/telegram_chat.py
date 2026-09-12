"""Chat tự do trên Telegram — nối thẳng vào agent pipeline của web chat.

Trước đây webhook trả lời câu hỏi tự do bằng một câu từ chối cố định. Từ
2026-08-22, mọi text không phải lệnh được chạy qua cùng đường ống với
conversations.py (bộ nhớ ngắn/dài hạn, hồ sơ người dùng, search scope, quota
hỏi trong ngày) để user hỏi việc ngay trong Telegram mà không mất ngữ cảnh.

Lịch sử chat Telegram nằm trong Conversation riêng có tiêu đề cố định, tách
khỏi các phiên trên web để không trộn lẫn hai kênh.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.api.conversations import (
    _CALENDAR_DRAFT_REQUEST,
    _confirm_task_from_conversation,
    _message_extras,
    _pending_approval_from_confirmation,
    _pending_productivity_action,
    _task_drafts_from_agent_result,
)
from src.models.conversation import Conversation, ConversationMessage
from src.services.memory_capture import capture_long_term_memory
from src.services.memory_store import arecall, to_prompt_payload
from src.services.profile_memory import load_user_profile
from src.services.scope import apply_search_scope, reset_agent_scope
from src.services.usage_quota import consume_llm_question
from src.services.working_memory import (
    VERBATIM_TURNS,
    build_working_memory,
    load_recent_turns,
    refresh_conversation_summary,
)

logger = logging.getLogger(__name__)

# Tiêu đề đóng vai trò định danh phiên Telegram của mỗi user. Không dùng id
# chat Telegram làm title: title là dữ liệu user nhìn thấy, còn ánh xạ
# (user -> phiên) đã đủ bởi user_id + tiêu đề này.
TELEGRAM_CONVERSATION_TITLE = "Chat Telegram"

# Số fact dài hạn kèm mỗi lượt — giữ đồng bộ với conversations.py.
_SO_MEMORY_DAI_HAN = 8

_QUOTA_REPLY = (
    "Bạn đã hết lượt hỏi trong hôm nay rồi. Góp ý cải thiện sản phẩm để nhận "
    "thêm 5 lượt dùng nhé."
)


def get_or_create_telegram_conversation(db: Session, user_id: str) -> Conversation:
    """Phiên chat Telegram của một user — không có thì tạo mới.

    Lấy bản mới nhất theo updated_at phòng trường hợp lịch sử tạo nhiều dòng
    (vd. sau khi user xoá phiên cũ rồi chat lại).
    """
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.title == TELEGRAM_CONVERSATION_TITLE)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    if conversation is not None:
        return conversation
    conversation = Conversation(
        user_id=user_id, title=TELEGRAM_CONVERSATION_TITLE, created_at=datetime.now(UTC)
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


async def handle_free_message(db: Session, user_id: str, text: str) -> str:
    """Một lượt hỏi đáp tự do; trả về câu trả lời để webhook gửi đi.

    Lỗi agent KHÔNG nuốt ở đây: ném tiếp cho webhook rollback và nhả claim
    receipt để Telegram retry được (cùng hành vi với endpoint /messages của
    web). Chỉ lỗi quota là biến thành lời nhắn thân thiện vì nó là trạng thái
    bình thường của user, không phải sự cố hệ thống.
    """
    conversation = get_or_create_telegram_conversation(db, user_id)

    bo_nho_ngan_han = build_working_memory(db, conversation)
    lich_su = bo_nho_ngan_han.turns
    confirmation_history = load_recent_turns(db, conversation.id, VERBATIM_TURNS)
    pending_approval = _pending_approval_from_confirmation(text, confirmation_history)
    confirmation = (
        None
        if pending_approval is not None
        else _confirm_task_from_conversation(db, user_id, text, confirmation_history)
    )

    # Câu "oke/xác nhận" là UI action có ngữ cảnh: không gọi LLM, không trừ hạn mức.
    if confirmation is None and pending_approval is None:
        try:
            consume_llm_question(db, user_id)
        except HTTPException as exc:
            detail = str(exc.detail) if exc.status_code == 429 else _QUOTA_REPLY
            logger.info(
                "Telegram free chat bị chặn quota cho user %s (%s)", user_id, exc.status_code
            )
            return detail

    luc_hoi = datetime.now(UTC)
    luot_nguoi = ConversationMessage(
        conversation_id=conversation.id, role="user", content=text, created_at=luc_hoi
    )
    db.add(luot_nguoi)

    if pending_approval is not None:
        luc_tra_loi = datetime.now(UTC)
        luot_tra_loi = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="Action này đang chờ duyệt. Mở Mondaiy để xem lại chi tiết và bấm Chấp nhận.",
            extras={"productivityAction": pending_approval},
            created_at=luc_tra_loi,
        )
        db.add(luot_tra_loi)
        conversation.updated_at = luc_tra_loi.created_at
        db.commit()
        return luot_tra_loi.content

    if confirmation is not None:
        response_text, task_drafts = confirmation
        luc_tra_loi = datetime.now(UTC)
        luot_tra_loi = ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text,
            extras={"taskDrafts": task_drafts},
            created_at=luc_tra_loi,
        )
        db.add(luot_tra_loi)
        conversation.updated_at = luc_tra_loi.created_at
        db.commit()
        return response_text

    # Chốt lượt user trước khi gọi agent — lỗi trợ lý không được làm mất câu hỏi.
    db.commit()
    db.refresh(luot_nguoi)

    user_profile = load_user_profile(db, user_id)
    bo_nho_dai_han = to_prompt_payload(
        await arecall(db, user_id, text, limit=_SO_MEMORY_DAI_HAN)
    )
    pending_action = _pending_productivity_action(lich_su)
    apply_search_scope(
        user_id,
        db,
        action_request_id=f"telegram:{conversation.id}:{uuid.uuid4()}",
        current_query=text,
        pending_action=pending_action,
    )
    try:
        ket_qua = await agent.ainvoke(
            {
                "query": text,
                "image_data": "",
                "history": lich_su,
                "conversation_summary": bo_nho_ngan_han.summary,
                "long_term_memories": bo_nho_dai_han,
                "user_profile": user_profile,
                "pending_productivity_action": pending_action,
            }
        )
    finally:
        reset_agent_scope()

    loi = ket_qua.get("error")
    if loi:
        db.rollback()
        raise RuntimeError(f"Agent hỏng ở chat Telegram: {loi}")

    task_selection = _task_drafts_from_agent_result(
        db,
        user_id,
        ket_qua,
        calendar_requested=bool(_CALENDAR_DRAFT_REQUEST.search(text)),
    )
    task_drafts = task_selection.drafts
    response_text = ket_qua.get("response", "")
    luot_tra_loi = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        analysis=ket_qua.get("analysis") or None,
        extras=_message_extras(
            ket_qua,
            task_drafts,
            task_backlog_count=task_selection.backlog_count,
        ),
        created_at=datetime.now(UTC),
    )
    db.add(luot_tra_loi)
    db.flush()
    capture_long_term_memory(
        db,
        user_id,
        text,
        source_conversation_id=conversation.id,
        source_message_id=luot_nguoi.id,
    )
    conversation.updated_at = luot_tra_loi.created_at
    db.commit()

    try:
        await refresh_conversation_summary(db, conversation.id, user_id)
    except Exception:
        logger.exception("Không nén được tóm tắt hội thoại Telegram %s", conversation.id)

    if task_drafts and response_text:
        response_text += "\n\nMở Mondaiy để xem và xác nhận các thẻ việc vừa tạo."
    return response_text
