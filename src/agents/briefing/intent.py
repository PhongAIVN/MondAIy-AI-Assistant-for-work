"""Semantic intent classification backed by the shared RAG embedding API."""
from __future__ import annotations

import logging
import math
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import lru_cache

from src.config import get_settings

logger = logging.getLogger(__name__)


class BriefIntent(StrEnum):
    SMALL_TALK = "small_talk"
    DAILY_BRIEF = "daily_brief"
    NEXT_STEPS = "next_steps"
    SCHEDULE = "schedule"
    GMAIL_FOCUS = "gmail_focus"
    TASK_STATUS = "task_status"
    EXPLICIT_ACTION = "explicit_action"
    GENERAL_WORK = "general_work"


@dataclass(frozen=True)
class IntentDecision:
    intent: BriefIntent
    score: float
    threshold: float
    margin: float
    runner_up: str | None
    runner_up_score: float | None
    backend: str
    matched_by: str
    ambiguous: bool = False

    def trace(self) -> dict[str, object]:
        result = asdict(self)
        result["intent"] = self.intent.value
        return result


# These are semantic anchors, not command patterns. Keep several natural
# paraphrases per class so the classifier does not depend on one wording.
_EXAMPLES: dict[BriefIntent, tuple[str, ...]] = {
    BriefIntent.SMALL_TALK: ("xin chào", "hello", "bạn khỏe không", "cảm ơn bạn"),
    BriefIntent.DAILY_BRIEF: (
        "tóm tắt công việc hôm nay",
        "tóm tắt nội dung công việc trong ngày",
        "hôm nay có gì cần chú ý",
        "tổng quan những việc hôm nay",
        "báo cáo công việc trong ngày",
        "summarize my work today",
        "daily brief",
    ),
    BriefIntent.NEXT_STEPS: (
        "tôi nên làm gì tiếp theo",
        "việc nào cần ưu tiên trước",
        "bây giờ cần xử lý gì",
        "next steps cho công việc",
        "cuối tuần phải làm gì",
    ),
    BriefIntent.SCHEDULE: (
        "xem lịch hôm nay",
        "cuộc họp nào sắp tới",
        "kiểm tra calendar",
        "tóm tắt lịch tháng này",
        "lịch của tôi có gì",
    ),
    BriefIntent.GMAIL_FOCUS: (
        "tìm email trong gmail",
        "đọc hộp thư",
        "email nào cần xử lý",
        "tóm tắt thư điện tử",
        "kiểm tra các email mới",
    ),
    BriefIntent.TASK_STATUS: (
        "công việc nào đang làm",
        "xem trạng thái task",
        "deadline của tôi là gì",
        "jira còn việc nào chưa xong",
        "việc nào đang chờ xử lý",
    ),
    BriefIntent.EXPLICIT_ACTION: (
        "thêm việc này vào lịch",
        "tạo event trên calendar",
        "đặt lịch cuộc họp",
        "create a calendar event",
        "tạo task mới",
    ),
    BriefIntent.GENERAL_WORK: (
        "giúp tôi xử lý công việc",
        "phân tích thông tin này",
        "tôi cần trợ giúp",
        "giải thích nội dung này",
    ),
}

_SMALL_TALK = re.compile(
    r"(?i)^\s*(?:hi|hello|hey|chào|xin chào|(?:hello[, ]+)?bạn khỏe không|khỏe không|how are you|cảm ơn|thanks?|bye)\s*[!.?,]*\s*$"
)
_ACTION = re.compile(r"(?i)(?:\b(?:add|create|schedule|make)\b|tạo|thêm|đặt|ghi|lên\s+lịch|nhắc)")
_CALENDAR = re.compile(r"(?i)(?:calendar|event|lịch|sự kiện|cuộc họp|cuộc hẹn)")


def _cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _embedding_backend():
    # Import lazily to keep intent module imports cheap and to guarantee that
    # RAG and intent use the exact same configured provider/model/key pool.
    from src.services.retrieval import embed_queries

    return embed_queries


@lru_cache(maxsize=2)
def _prototypes(model_name: str) -> tuple[tuple[BriefIntent, tuple[list[float], ...]], ...]:
    # model_name is a cache key; the shared retrieval service reads the same
    # setting and performs one batched API request for all anchors.
    del model_name
    texts: list[str] = []
    owners: list[BriefIntent] = []
    for intent, examples in _EXAMPLES.items():
        for example in examples:
            owners.append(intent)
            texts.append(example)
    vectors = _embedding_backend()(texts)
    grouped: dict[BriefIntent, list[list[float]]] = {intent: [] for intent in _EXAMPLES}
    for owner, vector in zip(owners, vectors):
        grouped[owner].append(vector)
    return tuple((intent, tuple(grouped[intent])) for intent in _EXAMPLES)


async def classify_intent_async(query: str, *, threshold: float | None = None) -> IntentDecision:
    """Như `classify_intent`, nhưng thử LLM trước khi rơi về embedding.

    Thứ tự — guardrail small-talk, rồi LLM, rồi embedding, rồi GENERAL_WORK —
    phản ánh đúng thứ đang chạy được. Đường embedding vẫn giữ nguyên chứ không
    xoá: nếu tài khoản OpenRouter được nạp credit trở lại, nó chạy lại ngay, và
    giữ nó lại rẻ hơn nhiều so với việc dựng lại sau. Xem ADR-020.

    Nhánh nào thắng đều ghi vào `backend`, nên trace nói được vì sao ra kết quả
    đó — điều mà bản cũ không làm, và đó là lý do một sự cố toàn phần sống sót
    nhiều tuần mà không ai thấy.
    """
    text = " ".join(query.split())
    settings = get_settings()
    limit = settings.intent_similarity_threshold if threshold is None else threshold

    if _SMALL_TALK.fullmatch(text):
        return IntentDecision(
            BriefIntent.SMALL_TALK, 1.0, limit, 1.0, None, None, "exact_guardrail", "exact_small_talk"
        )

    from src.agents.briefing.llm_intent import classify_with_llm

    result = await classify_with_llm(text)
    if result is not None:
        label, confidence = result
        try:
            chosen = BriefIntent(label)
        except ValueError:
            # Schema đóng lẽ ra chặn được, nhưng đừng tin điều đó một cách mù
            # quáng: một nhãn lạ phải rơi về mặc định an toàn và KÊU LÊN, chứ
            # không được lặng lẽ thành một lane nào đó.
            logger.error("intent: LLM trả nhãn lạ %r, rơi về general_work", label)
            chosen = BriefIntent.GENERAL_WORK
            confidence = 0.0
        decision = IntentDecision(
            chosen, round(confidence, 4), limit, 0.0, None, None, "llm_structured_output", "llm"
        )
        return _apply_explicit_action_guardrail(text, decision, limit)

    return classify_intent(text, threshold=threshold)


def _apply_explicit_action_guardrail(
    text: str, decision: IntentDecision, limit: float
) -> IntentDecision:
    """Nhận diện yêu cầu ghi rõ ràng. KHÔNG cấp quyền cho side effect nào.

    Tách ra thành hàm riêng vì cả đường LLM lẫn đường embedding đều phải đi qua
    nó — luật này là guardrail, không phải chi tiết của một backend.
    """
    if _ACTION.search(text) and _CALENDAR.search(text):
        return IntentDecision(
            BriefIntent.EXPLICIT_ACTION,
            max(decision.score, limit),
            limit,
            decision.margin,
            decision.runner_up,
            decision.runner_up_score,
            decision.backend,
            "explicit_action_guardrail",
            decision.ambiguous,
        )
    return decision


def classify_intent(query: str, *, threshold: float | None = None) -> IntentDecision:
    """Classify fairly across all anchors and return an auditable trace.

    ``threshold`` is the minimum cosine score for a named intent. A close
    runner-up marks the result ambiguous, but does not hide the best match;
    downstream can use that signal to broaden retrieval or ask a clarification.
    """
    text = " ".join(query.split())
    settings = get_settings()
    limit = settings.intent_similarity_threshold if threshold is None else threshold
    ambiguity_margin = settings.intent_ambiguity_margin

    if _SMALL_TALK.fullmatch(text):
        decision = IntentDecision(BriefIntent.SMALL_TALK, 1.0, limit, 1.0, None, None, "exact_guardrail", "exact_small_talk")
    else:
        try:
            vectors = _embedding_backend()([text])
            query_vector = vectors[0]
            ranked = sorted(
                ((intent, max(_cosine(query_vector, anchor) for anchor in anchors)) for intent, anchors in _prototypes(settings.embedding_model)),
                key=lambda item: item[1],
                reverse=True,
            )
            best, best_score = ranked[0]
            runner, runner_score = ranked[1]
            margin = best_score - runner_score
            ambiguous = best_score >= limit and margin < ambiguity_margin
            chosen = best if best_score >= limit else BriefIntent.GENERAL_WORK
            matched_by = "embedding" if chosen == best else "below_threshold"
            decision = IntentDecision(chosen, round(best_score, 4), limit, round(margin, 4), runner.value, round(runner_score, 4), "shared_rag_embedding", matched_by, ambiguous)
        except Exception as exc:
            # Log ở mức ERROR kèm NGUYÊN VĂN lỗi, không chỉ tên class. Bản cũ ghi
            # mỗi `type(exc).__name__` ở mức warning, nên một sự cố toàn phần —
            # nhà cung cấp embedding trả 402 "insufficient credits", tức phân loại
            # ý định CHƯA TỪNG chạy trên production — không để lại dấu vết nào đọc
            # được. Hạ cấp im lặng còn tệ hơn hỏng to: hệ thống vẫn trả lời như
            # thường và vẫn tự nhận là grounded.
            logger.error(
                "intent embedding unavailable; rơi về GENERAL_WORK. "
                "Mọi câu hỏi sẽ vào chung một lane cho tới khi sửa. Lỗi: %s: %s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            decision = IntentDecision(BriefIntent.GENERAL_WORK, 0.0, limit, 0.0, None, None, "shared_rag_embedding_unavailable", "embedding_error")

        # This only identifies an explicit write request. It never authorizes
        # the side effect; the existing approval/productivity flow still does.
        if _ACTION.search(text) and _CALENDAR.search(text):
            decision = IntentDecision(BriefIntent.EXPLICIT_ACTION, max(decision.score, limit), limit, decision.margin, decision.runner_up, decision.runner_up_score, decision.backend, "explicit_action_guardrail", decision.ambiguous)

    logger.info(
        "intent classified intent=%s score=%.4f threshold=%.4f margin=%.4f runner_up=%s runner_score=%s ambiguous=%s backend=%s matched_by=%s",
        decision.intent.value, decision.score, decision.threshold, decision.margin, decision.runner_up, decision.runner_up_score, decision.ambiguous, decision.backend, decision.matched_by,
    )
    return decision


def recognize_intent(query: str) -> BriefIntent:
    """Backward-compatible enum-only facade."""
    return classify_intent(query).intent
