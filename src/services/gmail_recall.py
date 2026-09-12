"""Recall planning for deadline-sensitive Gmail reads.

This module deliberately contains Gmail-only policy.  The general agent graph
still decides when to read Gmail; this layer decides how a brief reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class GmailSweepFamily(StrEnum):
    TARGETED = "targeted_query"
    DIRECT = "direct_to_user"
    ACTION = "action_language"
    TEMPORAL = "temporal_language"
    RELATIONSHIP = "important_relationship"
    ACTIVE = "active_thread"
    SUBJECT = "subject_domain"


@dataclass(frozen=True)
class GmailSweep:
    family: GmailSweepFamily
    query: str
    time_from: datetime
    time_to: datetime


@dataclass(frozen=True)
class GmailSweepReceipt:
    family: GmailSweepFamily
    time_from: datetime
    time_to: datetime
    message_count: int = 0
    status: str = "complete"
    error: str | None = None


_FAMILY_QUERIES = {
    GmailSweepFamily.DIRECT: "{to:me cc:me deliveredto:me}",
    GmailSweepFamily.ACTION: "{submit send edit complete review confirm reply respond}",
    GmailSweepFamily.TEMPORAL: "{deadline due by before after month week}",
    GmailSweepFamily.RELATIONSHIP: "{from:manager from:mentor from:teacher from:customer}",
    GmailSweepFamily.ACTIVE: "{is:unread is:important is:starred}",
    GmailSweepFamily.SUBJECT: "{subject:project subject:report subject:assignment subject:meeting}",
}


def build_gmail_sweep_plan(
    time_from: datetime,
    time_to: datetime,
    *,
    historical_window_days: int = 180,
    future_horizon_days: int = 180,
) -> list[GmailSweep]:
    """Build independent, bounded recall windows around the requested brief.

    The provider still enforces every range.  No family depends on the literal
    word ``deadline``; the union is a recall strategy, not verified evidence.
    """
    if time_from >= time_to:
        raise ValueError("Gmail sweep requires time_from < time_to")
    start = time_from - timedelta(days=max(1, historical_window_days))
    end = time_to + timedelta(days=max(1, future_horizon_days))
    return [
        GmailSweep(family, query, start, end)
        for family, query in _FAMILY_QUERIES.items()
    ]
