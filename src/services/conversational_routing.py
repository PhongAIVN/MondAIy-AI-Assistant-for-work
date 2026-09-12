"""Resolve conversational action and referent before selecting any tool."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from src.services.source_routing import analyze_source_mentions


class ResolvedAction(StrEnum):
    READ = "READ"
    EXPLAIN = "EXPLAIN"
    RETRY = "RETRY"
    SWITCH_SOURCE = "SWITCH_SOURCE"
    ANSWER_FROM_CONTEXT = "ANSWER_FROM_CONTEXT"
    CLARIFY = "CLARIFY"


_EXPLAIN = re.compile(r"(?i)^\s*(?:tại sao|tai sao|vì sao|vi sao|sao vậy|sao vay|why)\s*[?.!]*\s*$")
_RETRY = re.compile(r"(?i)^\s*(?:thử lại|thu lai|đọc lại|doc lai|làm lại|lam lai|retry|try again)\s*[?.!]*\s*$")
_RESOURCE_URL = re.compile(
    r"https?://docs\.google\.com/(?:spreadsheets|document)/d/[a-zA-Z0-9_-]+(?:[/?#][^\s<>)]+)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConversationalRoute:
    action: ResolvedAction
    referent: str
    source: str | None
    resource_ref: str | None
    selection_basis: str
    confidence: float
    tool_policy: str
    prior_status: str | None = None
    error_code: str | None = None
    user_safe_message: str | None = None
    clarification_question: str | None = None
    resource_locator: str | None = None

    def trace(self) -> dict:
        return {
            "action": self.action.value,
            "referent": self.referent,
            "source": self.source,
            "resource_ref": self.resource_ref,
            "selection_basis": self.selection_basis,
            "confidence": self.confidence,
            "tool_policy": self.tool_policy,
            **({"prior_status": self.prior_status} if self.prior_status else {}),
            **({"error_code": self.error_code} if self.error_code else {}),
            **({"user_safe_message": self.user_safe_message} if self.user_safe_message else {}),
            **({"clarification_question": self.clarification_question} if self.clarification_question else {}),
            **({"resource_locator": self.resource_locator} if self.resource_locator else {}),
        }


def _fold_words(text: str) -> list[str]:
    import unicodedata

    folded = "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char)
    ).replace("đ", "d")
    return re.findall(r"[a-z0-9]+", folded)


def _contextual_followup(query: str) -> tuple[bool, str | None]:
    """Nhận diện fragment phụ thuộc lượt trước bằng cấu trúc câu, không bằng fixture.

    Fragment định vị ngắn ("ở ...", "còn trong ...") hoặc deictic ("cái đó",
    "bảng ấy") chưa tự mang đủ intent/source. Câu có động từ hành động độc lập
    vẫn là lượt mới để tránh session memory rò sang chủ đề khác.
    """
    words = _fold_words(query)
    if not words or len(words) > 8:
        return False, None
    discourse = {"con", "va", "vay", "the", "thi"}
    while words and words[0] in discourse:
        words = words[1:]
    if not words:
        return False, None
    independent_intents = {
        "doc", "tim", "kiem", "tra", "tom", "tat", "giai", "thich",
        "cho", "biet", "tao", "them", "sua", "xoa", "liet", "ke",
    }
    if any(word in independent_intents for word in words):
        return False, None
    locators = {"o", "trong", "tren", "tu", "ve", "cua"}
    deictics = {"do", "nay", "ay", "kia"}
    if words[0] in locators:
        tail = [word for word in words[1:] if word not in deictics]
        locator = " ".join(tail).strip() or None
        return True, locator
    if any(word in deictics for word in words):
        return True, None
    return False, None


def _source_from_current(query: str) -> tuple[str | None, str | None, bool]:
    decision = analyze_source_mentions(query)
    sources = [source for source in decision.explicit_sources if source != "all"]
    if decision.explicit_sources == ("all",):
        return None, None, False
    if len(sources) > 1:
        # Khi nhiều tên nguồn xuất hiện, cụm định vị thường nói nguồn thực thi
        # còn tên kia chỉ là chủ đề: “việc Jira trên Discord”, “deadline từ
        # Gmail”. Ưu tiên source trong cụm định vị; nếu vẫn nhiều nghĩa thì hỏi.
        locator = re.search(
            r"(?i)(?:\btrên\b|\btren\b|\btrong\b|\bở\b|\btừ\b|\bon\b|\bin\b|\bfrom\b)\s+(.+)$",
            query,
        )
        if locator:
            located = [
                source
                for source in analyze_source_mentions(locator.group(1)).explicit_sources
                if source != "all"
            ]
            if len(located) == 1:
                resource_match = _RESOURCE_URL.search(query)
                resource = resource_match.group(0).rstrip(".,;!?") if resource_match else None
                return located[0], resource, False
        return None, None, True
    source = sources[0] if sources else None
    resource = _RESOURCE_URL.search(query).group(0).rstrip(".,;!?") if _RESOURCE_URL.search(query) else None
    return source, resource, False


def _persisted_routes(history: list[dict]) -> list[dict]:
    routes: list[dict] = []
    for turn in reversed(history):
        if turn.get("role") != "assistant":
            continue
        route = (turn.get("extras") or {}).get("routing")
        if isinstance(route, dict):
            routes.append(route)
    return routes


def _nearest_user_source(history: list[dict]) -> tuple[str | None, str | None]:
    for turn in reversed(history):
        if turn.get("role") != "user":
            continue
        source, resource, ambiguous = _source_from_current(str(turn.get("content") or ""))
        if source and not ambiguous:
            return source, resource or str(turn.get("content") or "").strip()
    return None, None


def _antecedent(history: list[dict]) -> tuple[dict | None, bool]:
    routes = _persisted_routes(history)
    if not routes:
        return None, False
    nearest = routes[0]
    sources = nearest.get("sources")
    if isinstance(sources, list) and len(set(sources)) > 1:
        return nearest, True
    return nearest, False


def resolve_conversational_route(query: str, history: list[dict] | None = None) -> ConversationalRoute:
    history = history or []
    query = query.strip()
    current_source, current_resource, current_ambiguous = _source_from_current(query)
    is_explain = bool(_EXPLAIN.fullmatch(query))
    is_retry = bool(_RETRY.fullmatch(query))
    is_contextual, resource_locator = _contextual_followup(query)

    if current_ambiguous:
        return ConversationalRoute(
            ResolvedAction.CLARIFY,
            "none",
            None,
            None,
            "current_explicit",
            0.55,
            "clarify_before_tool",
            clarification_question="Bạn muốn mình xử lý nguồn nào trước?",
        )

    antecedent, antecedent_ambiguous = _antecedent(history)
    if (is_explain or is_retry) and antecedent_ambiguous:
        return ConversationalRoute(
            ResolvedAction.CLARIFY,
            "prior_result",
            None,
            None,
            "none",
            0.55,
            "clarify_before_tool",
            clarification_question="Bạn đang hỏi về kết quả của nguồn nào?",
        )

    if is_explain or is_retry:
        if antecedent:
            source = antecedent.get("source")
            resource = antecedent.get("resource_ref")
            basis = "persisted_result"
            confidence = 0.97
        else:
            source, resource = _nearest_user_source(history)
            basis = "nearest_compatible_turn" if source else "none"
            confidence = 0.82 if source else 0.40
        if not source:
            return ConversationalRoute(
                ResolvedAction.CLARIFY,
                "none",
                None,
                None,
                "none",
                confidence,
                "clarify_before_tool",
                clarification_question="Bạn đang hỏi ‘tại sao’ về kết quả nào?",
            )
        action = ResolvedAction.EXPLAIN if is_explain else ResolvedAction.RETRY
        return ConversationalRoute(
            action,
            "prior_error" if antecedent and antecedent.get("status") == "error" else "prior_result",
            str(source),
            str(resource) if resource else None,
            basis,
            confidence,
            "no_new_tool" if is_explain else "selected_source_only",
            prior_status=str(antecedent.get("status")) if antecedent and antecedent.get("status") else None,
            error_code=str(antecedent.get("error_code")) if antecedent and antecedent.get("error_code") else None,
            user_safe_message=(
                str(antecedent.get("user_safe_message")) if antecedent and antecedent.get("user_safe_message") else None
            ),
        )

    if current_source:
        previous_source = antecedent.get("source") if antecedent else None
        action = (
            ResolvedAction.SWITCH_SOURCE
            if previous_source and previous_source != current_source
            else ResolvedAction.READ
        )
        return ConversationalRoute(
            action,
            "resource" if current_resource else "conversation_topic",
            current_source,
            current_resource or query,
            "current_explicit",
            0.97,
            "selected_source_only",
        )

    if is_contextual and antecedent and antecedent.get("source"):
        source = str(antecedent["source"])
        resource = antecedent.get("resource_ref")
        return ConversationalRoute(
            ResolvedAction.READ,
            "prior_error" if antecedent.get("status") == "error" else "prior_result",
            source,
            str(resource) if resource else None,
            "persisted_result",
            0.92,
            "selected_source_only",
            prior_status=str(antecedent.get("status")) if antecedent.get("status") else None,
            resource_locator=resource_locator,
        )

    return ConversationalRoute(
        ResolvedAction.ANSWER_FROM_CONTEXT,
        "conversation_topic" if history else "none",
        None,
        None,
        "none",
        0.75,
        "no_new_tool",
    )
