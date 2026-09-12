"""Deterministic query routing for the agent execution lanes."""

from __future__ import annotations

import re
from enum import StrEnum


class RouteLane(StrEnum):
    SMALL_TALK = "small_talk"
    WORK = "work"


_SMALL_TALK = re.compile(
    r"(?i)^(?:hi|hello|hey|chào(?: buổi (?:sáng|chiều|tối))?|xin chào|"
    r"thanks?(?: nha)?|thank you(?: nha)?|cảm ơn(?: nha)?|tạm biệt|bye|"
    r"kể một câu đùa(?: ngắn)?(?: đi)?|joke|haha|hehe)[!.?,\s]*$"
)
_SMALL_TALK_EXTRA = re.compile(r"(?i)^(?:how are you|what'?s up|bạn khoẻ không|khỏe không)[!.?,\s]*$")


def classify_query(query: str) -> RouteLane:
    """Select a lane without an additional LLM call.

    Ambiguous and mixed queries are deliberately sent to ``work`` because that
    lane preserves retrieval, tool guards, and authenticated scope.
    """

    normalized = " ".join(query.casefold().split())
    if normalized and (_SMALL_TALK.fullmatch(normalized) or _SMALL_TALK_EXTRA.fullmatch(normalized)):
        return RouteLane.SMALL_TALK
    return RouteLane.WORK
