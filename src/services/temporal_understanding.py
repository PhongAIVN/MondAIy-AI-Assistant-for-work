"""Confidence-scored temporal understanding shared by thinking and tool planning.

This is intentionally a semantic layer, not a collection of tool-specific date
regexes. It normalizes common relative periods, computes timezone-aware bounds,
and exposes uncertainty before any source is queried.
"""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TemporalDecision:
    kind: str
    time_from: datetime | None
    time_to: datetime | None
    confidence: float
    confidence_band: str
    needs_confirmation: bool
    reason: str
    confirmation_question: str | None = None

    def trace(self) -> dict:
        return {
            "kind": self.kind,
            "time_from": self.time_from.isoformat() if self.time_from else None,
            "time_to": self.time_to.isoformat() if self.time_to else None,
            "confidence": self.confidence,
            "confidence_band": self.confidence_band,
            "needs_confirmation": self.needs_confirmation,
            "reason": self.reason,
            **({"confirmation_question": self.confirmation_question} if self.confirmation_question else {}),
        }


def _fold(text: str) -> str:
    return " ".join(
        "".join(char for char in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(char))
        .replace("đ", "d")
        .split()
    )


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(now: datetime, year: int, month: int) -> datetime:
    return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_bounds(now: datetime, year: int, month: int) -> tuple[datetime, datetime]:
    start = _month_start(now, year, month)
    return start, start.replace(day=monthrange(year, month)[1]) + timedelta(days=1)


_MONTH_EXPLICIT = re.compile(r"\bthang\s+(?P<month>1[0-2]|[1-9])\s+(?:nam\s+)?(?P<year>\d{4})\b")
_MONTH_NUMERIC = re.compile(r"\b(?P<month>1[0-2]|0?[1-9])/(?P<year>\d{4})\b")
_MONTH_UNDATED = re.compile(r"\bthang\s+(?P<month>1[0-2]|[1-9])\b")


def resolve_temporal(text: str, now: datetime) -> TemporalDecision:
    """Resolve a user time phrase without silently guessing an ambiguous year."""
    folded = _fold(text)
    day = _day_start(now)
    week = day - timedelta(days=day.weekday())
    exact = {
        "hom nay": ("today", day, day + timedelta(days=1)),
        "today": ("today", day, day + timedelta(days=1)),
        "ngay mai": ("tomorrow", day + timedelta(days=1), day + timedelta(days=2)),
        "mai": ("tomorrow", day + timedelta(days=1), day + timedelta(days=2)),
        "tomorrow": ("tomorrow", day + timedelta(days=1), day + timedelta(days=2)),
        "hom qua": ("yesterday", day - timedelta(days=1), day),
        "yesterday": ("yesterday", day - timedelta(days=1), day),
        "tuan nay": ("this_week", week, week + timedelta(days=7)),
        "this week": ("this_week", week, week + timedelta(days=7)),
        "tuan sau": ("next_week", week + timedelta(days=7), week + timedelta(days=14)),
        "tuan toi": ("next_week", week + timedelta(days=7), week + timedelta(days=14)),
        "next week": ("next_week", week + timedelta(days=7), week + timedelta(days=14)),
        "tuan truoc": ("last_week", week - timedelta(days=7), week),
        "tuan vua roi": ("last_week", week - timedelta(days=7), week),
        "last week": ("last_week", week - timedelta(days=7), week),
        "thang nay": ("this_month", _month_start(now, now.year, now.month), _month_start(now, now.year + (now.month == 12), 1 if now.month == 12 else now.month + 1)),
        "this month": ("this_month", _month_start(now, now.year, now.month), _month_start(now, now.year + (now.month == 12), 1 if now.month == 12 else now.month + 1)),
    }
    for phrase, (kind, start, end) in sorted(exact.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?:^|\s){re.escape(phrase)}(?:$|\s|[?.!,])", folded):
            return TemporalDecision(kind, start, end, 0.99, "high", False, "explicit_relative_period")

    if re.search(r"(?:^|\s)(?:thang sau|next month)(?:$|\s|[?.!,])", folded):
        year = now.year + (now.month == 12)
        month = 1 if now.month == 12 else now.month + 1
        start, end = _month_bounds(now, year, month)
        return TemporalDecision("next_month", start, end, 0.98, "high", False, "explicit_relative_period")
    if re.search(r"(?:^|\s)(?:thang truoc|thang vua roi|last month)(?:$|\s|[?.!,])", folded):
        year = now.year - (now.month == 1)
        month = 12 if now.month == 1 else now.month - 1
        start, end = _month_bounds(now, year, month)
        return TemporalDecision("last_month", start, end, 0.98, "high", False, "explicit_relative_period")

    match = _MONTH_EXPLICIT.search(folded) or _MONTH_NUMERIC.search(folded)
    if match:
        month, year = int(match.group("month")), int(match.group("year"))
        start, end = _month_bounds(now, year, month)
        return TemporalDecision("explicit_month", start, end, 0.98, "high", False, "month_and_year_explicit")

    match = _MONTH_UNDATED.search(folded)
    if match:
        month = int(match.group("month"))
        question = f"Bạn muốn tra tháng {month} năm {now.year} đúng không? Mình chưa tự đoán năm để tránh đọc nhầm dữ liệu."
        return TemporalDecision(
            "month_without_year",
            None,
            None,
            0.62,
            "medium",
            True,
            "month_year_missing",
            question,
        )

    # These are deliberately conservative: a vague period must be confirmed.
    if any(phrase in folded for phrase in ("cuoi tuan", "cuối tuần", "around july", "mid month")):
        return TemporalDecision("vague_period", None, None, 0.48, "low", True, "period_boundary_unclear", "Bạn muốn khoảng ngày cụ thể nào? Mình chưa chắc cách hiểu mốc thời gian này.")
    return TemporalDecision("none", None, None, 1.0, "high", False, "no_temporal_expression")


def decision_from_trace(trace: dict) -> TemporalDecision | None:
    if not trace.get("time_from") or not trace.get("time_to"):
        return None
    try:
        start = datetime.fromisoformat(trace["time_from"])
        end = datetime.fromisoformat(trace["time_to"])
    except (TypeError, ValueError):
        return None
    return TemporalDecision(trace.get("kind", "confirmed"), start, end, 0.99, "high", False, "user_confirmed")
