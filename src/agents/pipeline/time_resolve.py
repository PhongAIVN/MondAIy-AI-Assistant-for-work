from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from dateutil import parser as dateutil_parser

_TZ_ABBREVIATIONS = {
    "ICT": timezone(timedelta(hours=7)),
    "GMT+7": timezone(timedelta(hours=7)),
    "UTC": UTC,
    "GMT": UTC,
}

_DATE_TOKEN = re.compile(
    r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|hôm nay|ngày mai|today|tomorrow|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"thứ hai|thứ ba|thứ tư|thứ năm|thứ sáu|thứ bảy|chủ nhật)",
    re.IGNORECASE,
)
_TIME_TOKEN = re.compile(r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(am|pm)\b|\b\d{1,2}\s*giờ\b", re.IGNORECASE)
_TZ_TOKEN = re.compile(r"\b(ict|utc|gmt(\+7)?|z)\b|[+-]\d{2}:?\d{2}\b", re.IGNORECASE)


def resolve_due_at(time_expression: str) -> datetime | None:
    """Chỉ trả due_at khi chuỗi gốc có đủ ngày, giờ VÀ timezone tường minh —
    không đoán (BR-05, PRD §9). Ambiguous/thiếu thành phần thì trả None."""
    if not time_expression:
        return None
    if not (
        _DATE_TOKEN.search(time_expression)
        and _TIME_TOKEN.search(time_expression)
        and _TZ_TOKEN.search(time_expression)
    ):
        return None

    try:
        parsed = dateutil_parser.parse(time_expression, fuzzy=True, tzinfos=_TZ_ABBREVIATIONS)
    except (ValueError, OverflowError):
        return None

    if parsed.tzinfo is None:
        return None
    return parsed
