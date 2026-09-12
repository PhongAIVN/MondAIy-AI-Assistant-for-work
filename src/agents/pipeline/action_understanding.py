"""Small bilingual rule engine for Gmail speech-act detection.

Rules are deliberately high precision.  A message that does not match a
strong English/Vietnamese pattern is marked ``uncertain`` so the caller can
escalate only that message to the LLM.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, TypedDict

ActionType = Literal["direct_action", "commitment", "conditional_action", "waiting", "prohibition"]


class ActionHint(TypedDict):
    action_type: ActionType
    requires_user_action: bool
    condition: str
    status: str
    certainty: str
    matched_terms: list[str]


def _repair_text(text: str) -> str:
    """Accept both UTF-8 and legacy mojibake found in imported mail fixtures."""
    if any(token in text for token in ("Ã", "Â", "Ä", "Æ", "á", "â")):
        try:
            return text.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _fold(text: str) -> str:
    value = _repair_text(text)
    value = unicodedata.normalize("NFKD", value).replace("đ", "d").replace("Đ", "D")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.casefold()


def _has_any(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(rf"(?<!\w){pattern}(?!\w)", text)]


# Patterns are folded (lowercase, no accents) and use word boundaries.  Keep
# these lists explicit: broad words such as ``can``/``need`` create many false
# positives in newsletters and quoted history.
_PROHIBITION = (
    r"please do not\s+\w+", r"do not\s+\w+", r"don't\s+\w+", r"never\s+\w+",
    r"must not\s+\w+", r"should not\s+\w+", r"dung\s+\w+", r"khong duoc\s+\w+",
    r"khong nen\s+\w+", r"chua duoc\s+\w+", r"tam ngung\s+\w+",
)
_WAITING = (
    r"waiting for", r"pending", r"awaiting", r"blocked on", r"on hold",
    r"dang cho", r"cho\s+\w+", r"doi\s+\w+", r"phu thuoc vao", r"chua duoc duyet",
)
_CONDITIONAL = (
    r"if", r"unless", r"when", r"in case", r"provided that", r"as long as",
    r"neu", r"khi", r"trong truong hop", r"mien la", r"chi khi", r"tru khi",
)
_COMMITMENT = (
    r"i will", r"i'll", r"we will", r"we'll", r"i am going to", r"we are going to",
    r"committed to", r"promised to", r"plan to", r"toi se", r"em se", r"anh se",
    r"chi se", r"chung toi se", r"da hua", r"cam ket", r"du dinh",
)
_DIRECT_ACTION = (
    r"please", r"action required", r"need you to", r"you must", r"please reply",
    r"please review", r"please send", r"please confirm", r"vui long", r"hay",
    r"yeu cau", r"de nghi", r"nho\s+\w+", r"can ban\s+\w+", r"can em\s+\w+",
    r"phan hoi", r"nop", r"duyet", r"xac nhan", r"kiem tra", r"gui",
)


def _hint(action_type: ActionType, *, condition: str = "", certainty: str = "confirmed", matched_terms: list[str] | None = None) -> ActionHint:
    waiting = action_type == "waiting"
    prohibition = action_type == "prohibition"
    return {
        "action_type": action_type,
        "requires_user_action": not (waiting or prohibition),
        "condition": condition,
        "status": "waiting" if waiting else "blocked" if prohibition else "open",
        "certainty": certainty,
        "matched_terms": matched_terms or [],
    }


def infer_action_hint(text: str) -> ActionHint:
    """Return a high-precision speech-act hint for English or Vietnamese text."""
    active = _repair_text(text).strip()
    folded = _fold(active)

    # Priority matters: "If you don't send..." is a prohibition, not merely a
    # conditional action; "waiting for approval" is state, not a todo.
    matched = _has_any(folded, _PROHIBITION)
    if matched:
        return _hint("prohibition", matched_terms=matched)

    matched = _has_any(folded, _WAITING)
    if matched:
        return _hint("waiting", matched_terms=matched)

    matched = _has_any(folded, _CONDITIONAL)
    if matched:
        condition_match = re.search(
            r"(?is)\b(?:if|unless|when|in case|provided that|as long as|neu|khi|trong truong hop|mien la|chi khi|tru khi)\b.{0,240}",
            folded,
        )
        condition = ""
        if condition_match:
            start = condition_match.start()
            condition = active[start : start + len(condition_match.group(0))].strip()
        return _hint("conditional_action", condition=condition, matched_terms=matched)

    matched = _has_any(folded, _COMMITMENT)
    if matched:
        return _hint("commitment", matched_terms=matched)

    matched = _has_any(folded, _DIRECT_ACTION)
    if matched:
        return _hint("direct_action", matched_terms=matched)

    # Do not pretend an arbitrary email is a direct action.  Keep the legacy
    # enum for compatibility, but explicitly mark this case for LLM routing.
    return _hint("direct_action", certainty="uncertain")
