"""Kiểu dữ liệu dùng chung cho routing/tool-planning — tách từ intent_router.py
(2026-08-15) để mỗi file dưới 800 dòng, xem __init__.py của package này."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GmailIntent(str, Enum):
    NONE = "none"
    SEARCH = "search"
    SUMMARY = "summary"
    READ_THREAD = "read_thread"
    ATTACHMENT = "attachment"
    TRIAGE = "triage"
    LABELS = "labels"
    DRAFT = "draft"
    REPLY = "reply"
    FORWARD = "forward"
    SEND = "send"
    ARCHIVE = "archive"
    DELETE = "delete"


class CalendarIntent(str, Enum):
    NONE = "none"
    SUMMARY = "summary"
    SEARCH = "search"
    READ_EVENT = "read_event"
    AVAILABILITY = "availability"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ToolRisk(str, Enum):
    NONE = "none"
    READ = "read"
    DRAFT = "draft"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class GmailIntentPlan:
    intent: GmailIntent
    tool: str | None
    fallback_tool: str | None
    confidence: float
    needs_clarification: bool
    risk: ToolRisk
    query: str | None
    reason: str


@dataclass(frozen=True)
class CalendarIntentPlan:
    intent: CalendarIntent
    tool: str | None
    fallback_tool: str | None
    confidence: float
    needs_clarification: bool
    risk: ToolRisk
    query: str | None
    reason: str
