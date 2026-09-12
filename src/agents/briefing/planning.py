"""Deterministic source plans for personal-intelligence intents."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.agents.briefing.intent import BriefIntent


@dataclass(frozen=True)
class RetrievalPlan:
    source: str
    time_from: datetime
    time_to: datetime
    priority_only: bool = False


def plan_information(intent: BriefIntent, now: datetime) -> tuple[RetrievalPlan, ...]:
    """Return bounded sources/windows. Unknown work queries stay conservative."""
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    week_ahead = today + timedelta(days=7)
    if intent == BriefIntent.DAILY_BRIEF:
        return (
            RetrievalPlan("calendar", today, today + timedelta(days=1)),
            RetrievalPlan("gmail", week_ago, now, priority_only=True),
            RetrievalPlan("jira", week_ago, now, priority_only=True),
            RetrievalPlan("discord", today, now),
            RetrievalPlan("tasks", today, week_ahead, priority_only=True),
        )
    if intent == BriefIntent.NEXT_STEPS:
        return tuple(RetrievalPlan(source, week_ago if source in {"gmail", "jira", "discord"} else today, week_ahead, True) for source in ("tasks", "calendar", "gmail", "jira", "discord"))
    if intent == BriefIntent.SCHEDULE:
        return (RetrievalPlan("calendar", today, week_ahead),)
    if intent == BriefIntent.GMAIL_FOCUS:
        return (RetrievalPlan("gmail", week_ago, now, True),)
    if intent == BriefIntent.TASK_STATUS:
        return (RetrievalPlan("jira", week_ago, week_ahead, True), RetrievalPlan("tasks", today, week_ahead, True), RetrievalPlan("calendar", today, week_ahead))
    return ()
