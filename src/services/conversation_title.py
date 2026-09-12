"""Đặt tên hội thoại từ câu hỏi đầu tiên bằng OpenAI gpt-4o-mini."""

from __future__ import annotations

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config import get_settings
from src.services.document_extraction import UNTRUSTED_CONTENT_NOTICE
from src.services.llm_observability import llm_callbacks

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 60


class ConversationTitle(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)


_SYSTEM_PROMPT = f"""Bạn đặt tiêu đề ngắn cho một phiên chat của trợ lý cá nhân.
{UNTRUSTED_CONTENT_NOTICE}

Tóm tắt đúng chủ đề chính của câu hỏi thành tiêu đề tiếng Việt, không quá
{MAX_TITLE_LENGTH} ký tự. Không thêm dấu ngoặc kép, dấu chấm cuối, lời mở đầu,
tên người dùng hay thông tin không có trong câu hỏi.
"""


def fallback_conversation_title(question: str) -> str:
    normalized = " ".join((question or "").split()).strip()
    return normalized[:MAX_TITLE_LENGTH] or "Hội thoại mới"


def _clean_title(raw: str) -> str | None:
    title = " ".join((raw or "").split()).strip(" \t\"'“”‘’.,;:!?-–—")
    if not title or len(title) > MAX_TITLE_LENGTH or "\n" in title:
        return None
    if re.search(r"[<>]", title):
        return None
    return title


async def suggest_conversation_title(question: str) -> str:
    """Sinh title; lỗi provider/output không được chặn việc tạo session."""
    fallback = fallback_conversation_title(question)
    normalized = " ".join((question or "").split()).strip()
    if not normalized:
        return fallback
    settings = get_settings()
    if not settings.openai_api_key:
        return fallback
    try:
        client = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=6,
            max_retries=0,
            callbacks=llm_callbacks("gpt-4o-mini", "conversation_title"),
        )
        result = await client.with_structured_output(ConversationTitle).ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=normalized[:2000]),
            ]
        )
        title = _clean_title(ConversationTitle.model_validate(result).title)
        return title or fallback
    except Exception:  # noqa: BLE001 — metadata không được làm gãy session
        logger.warning("conversation title generation failed; using question fallback")
        return fallback
