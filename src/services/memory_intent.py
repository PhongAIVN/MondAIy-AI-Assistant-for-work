"""Xác định intent lưu trí nhớ bằng LLM nhỏ thay vì regex.

Vì sao đổi hướng (quyết định của Thái 22/08): regex hẹp vừa bỏ sót fact chính
đáng (mentor, team/chương trình) vừa bắt nhầm sở hữu cách thành danh tính —
"mentor của tôi tên là X" từng bị ghi thành display_name của chính user.

Ranh giới giữ nguyên từ memory-lifecycle:
- LLM CHỈ đề xuất fact có cấu trúc theo schema cố định; mọi ghi chép vẫn phải
  qua validation bên dưới và allowlist của record_memory. Model không nhận quyền
  đặt predicate tùy ý hay chạm identity khi is_self=false.
- Tin nhắn user là untrusted data: bọc notice chống injection, structured output,
  không tool.
- Trả None khi tắt cờ/lỗi/timeout — caller fallback về regex đã vá, không bao
  giờ làm hỏng lượt chat.
- Destructive intent (quên/xoá bộ nhớ) KHÔNG đi qua đây: vẫn là luật
  deterministic ở profile_memory/memory_capture vì model không được quyết định
  hành động phá huỷ dữ liệu.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config import get_settings
from src.services.document_extraction import UNTRUSTED_CONTENT_NOTICE
from src.services.llm_observability import llm_callbacks

logger = logging.getLogger(__name__)

FactCategoryValue = Literal[
    "identity",
    "preference",
    "relationship",
    "affiliation",
    "goal",
    "project",
    "interest",
]


class FactCategory(BaseModel):
    """Một fact ứng viên do model đề xuất. Schema cố định, không predicate tự do."""

    category: FactCategoryValue
    value: str = Field(min_length=1, max_length=160)
    entity: str | None = Field(default=None, max_length=60)
    is_self: bool = True


class IntentExtraction(BaseModel):
    facts: list[FactCategory] = Field(default_factory=list, max_length=8)


@dataclass(frozen=True)
class ValidatedIntent:
    """Fact đã qua validation — caller chỉ được ghi những gì ở đây."""

    category: str
    predicate: str
    value: str
    is_self: bool


_SYSTEM_PROMPT = f"""Bạn là bộ trích xuất fact cho trợ lý cá nhân mondaiy. Đọc MỘT tin nhắn của
người dùng và liệt kê các fact lâu dài được NÓI RÕ trong tin đó. {UNTRUSTED_CONTENT_NOTICE}

Nguyên tắc:
- Mặc định trả về danh sách rỗng. Chỉ trích khi chắc chắn; không đoán, không diễn giải thêm,
  không phát minh fact từ câu hỏi hay lời xã giao.
- Phát biểu của chính người dùng về họ → is_self=true. Người thứ ba trong đời user (mentor, sếp,
  bạn bè, gia đình) → is_self=false kèm entity ngắn gọn bằng một từ (vd "mentor", "sếp").
- category chọn đúng một:
  identity = tên/cách gọi bản thân; preference = sở thích về cách trả lời;
  relationship = người thứ ba user khai báo; affiliation = team/công ty/chương trình user thuộc vào;
  goal = mục tiêu; project = dự án đang làm; interest = chủ đề quan tâm.
- value là trích ngắn gọn nguyên văn từ tin nhắn, một dòng, không suy diễn thêm.
"""


@lru_cache(maxsize=4)
def _intent_client(model: str, api_key: str, timeout_seconds: float) -> ChatOpenAI:
    """Client OpenAI riêng cho intent — không failover sang provider khác.

    max_retries=1: trace prod 24/08 cho thấy ReadTimeout một phát (provider
    chưa trả header trong timeout) làm enrichment rơi thẳng về regex dù chỉ là
    giật một nhịp. SDK tự thử lại với backoff ngắn; lời gọi chỉ đọc nên gọi
    lại an toàn. Trần tổng vẫn bị khoá bởi timeout mỗi lượt.
    """
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=0,
        timeout=timeout_seconds,
        max_retries=1,
        callbacks=llm_callbacks(model, "memory_intent"),
    )


def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _entity_slug(entity: str | None) -> str | None:
    """Entity → slug `[a-z][a-z0-9_]{1,29}` làm predicate ổn định (mentor_name...)."""
    if not entity:
        return None
    ascii_text = _strip_diacritics(entity).lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,29}", slug):
        return None
    return slug


def _clean_value(raw: str) -> str | None:
    value = " ".join((raw or "").split()).strip(" \t\"'“”‘’.,;:")
    if not 1 <= len(value) <= 120 or "\n" in value:
        return None
    return value


def _validate(fact: FactCategory) -> ValidatedIntent | None:
    value = _clean_value(fact.value)
    if value is None:
        return None
    if fact.category == "identity":
        # Danh tính CHỈ nhận khi chính user tự nói về mình. Tên người: chữ cái
        # Unicode + khoảng trắng + gạch nối, không số/ký tự lạ.
        if not fact.is_self:
            return None
        if not re.fullmatch(r"[\w\s\-'’\.]{1,80}", value):
            return None
        return ValidatedIntent("identity", "display_name", value, True)
    if fact.category in ("relationship", "affiliation"):
        slug = _entity_slug(fact.entity)
        if slug is None:
            return None
        return ValidatedIntent(fact.category, f"{slug}_name", value, fact.is_self)
    if fact.category == "goal":
        return ValidatedIntent("goal", "goal", value, True)
    if fact.category == "project":
        return ValidatedIntent("project", "working_on", value, True)
    if fact.category == "interest":
        return ValidatedIntent("interest", "interested_in", value, True)
    # preference: các key này có chuẩn hoá riêng (ngôn ngữ/múi giờ/kiểu trả lời)
    # — lớp regex chuyên trách giữ nhiệm vụ, LLM path chủ động bỏ qua.
    return None


async def _extract_raw(text: str) -> IntentExtraction:
    """Lời gọi model thô. Caller đã kiểm cờ/giới hạn; chỉ trả schema."""
    settings = get_settings()
    normalized = " ".join((text or "").strip().split())
    if len(normalized) < 8:
        return IntentExtraction(facts=[])
    client = _intent_client(
        settings.memory_intent_model,
        settings.openai_api_key,
        settings.memory_intent_timeout_seconds,
    )
    response = await client.with_structured_output(IntentExtraction).ainvoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=normalized),
        ]
    )
    return IntentExtraction.model_validate(response)


async def extract_memory_intents(text: str) -> list[ValidatedIntent] | None:
    """Trả danh sách fact đã validate, hoặc None khi cần fallback regex.

    Cờ tổng + API key được kiểm ở lớp public (trước _extract_raw) nên tắt cờ
    luôn có hiệu lực kể cả khi _extract_raw bị mock trong test. Mọi lỗi model/
    parse đều nuốt thành None — caller rơi về regex đã vá thay vì làm hỏng
    lượt chat.
    """
    settings = get_settings()
    if not settings.memory_intent_enabled or not settings.openai_api_key:
        return None
    normalized = " ".join((text or "").strip().split())
    if len(normalized) > 2000:
        return None
    try:
        raw = await _extract_raw(normalized)
    except Exception:  # noqa: BLE001 — timeout, rate limit, JSON bẩn… đều hạ về fallback
        # Ghi kèm stack: không có dòng này thì mỗi lần chẩn đoán lại phải xuống
        # LangSmith đào trace (như vụ ReadTimeout 24/08).
        logger.warning("memory_intent extraction failed; fallback to patched regex", exc_info=True)
        return None

    validated: list[ValidatedIntent] = []
    seen_predicates: set[str] = set()
    for fact in raw.facts:
        item = _validate(fact)
        if item is None or item.predicate in seen_predicates:
            continue
        seen_predicates.add(item.predicate)
        validated.append(item)
    return validated
