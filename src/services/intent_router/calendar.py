"""Định tuyến ý định Calendar bằng luật, không gọi LLM — xem package __init__.py."""

from __future__ import annotations

import re

from src.services.intent_router._shared import _fold
from src.services.intent_router.types import CalendarIntent, CalendarIntentPlan, ToolRisk

_CALENDAR = re.compile(r"(?i)\b(calendar|lịch|lich|event|sự kiện|su kien|cuộc họp|cuoc hop|meeting|schedule)\b")


def route_calendar_intent(text: str) -> CalendarIntentPlan:
    normalized = " ".join(text.strip().split())
    folded = _fold(normalized)
    if not normalized or not (_CALENDAR.search(normalized) or _CALENDAR.search(folded)):
        return CalendarIntentPlan(
            CalendarIntent.NONE, None, None, 0.99, False, ToolRisk.NONE, None, "no explicit Calendar scope"
        )
    if re.search(r"(?i)(xóa|xoa|delete|cancel|hủy|huy)", folded):
        return CalendarIntentPlan(
            CalendarIntent.DELETE,
            "calendar_delete_event",
            "delete_calendar_event",
            0.96,
            True,
            ToolRisk.DESTRUCTIVE,
            None,
            "explicit destructive Calendar request",
        )
    if re.search(r"(?i)(đổi|doi|sửa|sua|update|reschedule|dời|doi lich)", folded):
        return CalendarIntentPlan(
            CalendarIntent.UPDATE,
            "calendar_update_event",
            "update_calendar_event",
            0.94,
            True,
            ToolRisk.EXTERNAL_WRITE,
            None,
            "Calendar update requires event target and approval",
        )
    if re.search(r"(?i)(tạo|tao|đặt|dat|schedule|create|add|thêm|them)", folded):
        return CalendarIntentPlan(
            CalendarIntent.CREATE,
            "calendar_create_event",
            "create_calendar_event",
            0.94,
            True,
            ToolRisk.EXTERNAL_WRITE,
            None,
            "Calendar creation requires explicit approval",
        )
    if re.search(r"(?i)(rảnh|ranh|availability|available|trống|trong|bận|ban)", folded):
        return CalendarIntentPlan(
            CalendarIntent.AVAILABILITY,
            "calendar_get_availability",
            "search_calendar",
            0.93,
            True,
            ToolRisk.READ,
            normalized,
            "availability needs bounded time window and calendar",
        )
    if re.search(r"(?i)(đọc|doc|chi tiết|chi tiet|read|open|event id)", folded):
        return CalendarIntentPlan(
            CalendarIntent.READ_EVENT,
            "calendar_read_event",
            "read_calendar_event",
            0.90,
            True,
            ToolRisk.READ,
            None,
            "single event target is required",
        )
    if re.search(r"(?i)(tóm tắt|tom tat|tổng hợp|tong hop|summary|brief|nội dung|noi dung)", folded):
        return CalendarIntentPlan(
            CalendarIntent.SUMMARY,
            "calendar_search_events",
            "search_calendar",
            0.96,
            False,
            ToolRisk.READ,
            normalized,
            "bounded Calendar summary",
        )
    return CalendarIntentPlan(
        CalendarIntent.SEARCH,
        "calendar_search_events",
        "search_calendar",
        0.88,
        False,
        ToolRisk.READ,
        normalized,
        "explicit Calendar search",
    )
