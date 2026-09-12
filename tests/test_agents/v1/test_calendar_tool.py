from datetime import UTC, datetime

import pytest

from src.agents.nodes import core_nodes
from src.agents.tools.calendar_tool import (
    calendar_search_events,
    reset_calendar_scope,
    set_calendar_scope,
)
from src.services.intent_router import ToolPlanContext, plan_tool_calls


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_calendar_scope()
    yield
    reset_calendar_scope()


@pytest.mark.asyncio
async def test_calendar_tool_refuses_to_read_without_user_scope():
    result = await calendar_search_events.ainvoke({"time_from": "2026-08-10", "time_to": "2026-08-17"})
    assert "lịch của ai" in result


@pytest.mark.asyncio
async def test_calendar_tool_returns_bounded_events_with_source_links(monkeypatch):
    set_calendar_scope("user-1")
    captured = {}

    async def fake_search(db, user_id, time_from, time_to, query="", calendar_id=None):
        captured.update(
            user_id=user_id,
            time_from=time_from,
            time_to=time_to,
            query=query,
            calendar_id=calendar_id,
        )
        return {
            "events": [
                {
                    "title": "Mentor sync",
                    "start_at": "2026-08-12T09:00:00+07:00",
                    "end_at": "2026-08-12T10:00:00+07:00",
                    "deep_link": "https://calendar.google.com/calendar/event?eid=e1",
                    "calendar_name": "Lịch học",
                }
            ]
        }

    monkeypatch.setattr("src.services.calendar_tools.search_calendar_events", fake_search)
    result = await calendar_search_events.ainvoke(
        {
            "query": "mentor",
            "time_from": "2026-08-10T00:00:00+07:00",
            "time_to": "2026-08-17T00:00:00+07:00",
        }
    )

    assert captured["user_id"] == "user-1"
    assert captured["query"] == "mentor"
    assert captured["time_from"] < captured["time_to"]
    assert "Mentor sync" in result
    assert "[Lịch học]" in result
    assert "https://calendar.google.com/" in result


@pytest.mark.asyncio
async def test_calendar_tool_rejects_unbounded_or_reversed_window():
    set_calendar_scope("user-1")
    assert "Cần cả time_from" in await calendar_search_events.ainvoke({})
    result = await calendar_search_events.ainvoke({"time_from": "17/08/2026", "time_to": "10/08/2026"})
    assert "time_from phải sớm hơn" in result


def _plan(query: str, tool_calls: list[dict] | None = None) -> list[dict]:
    """Chạy luật điều hướng với mốc thời gian cố định."""
    return plan_tool_calls(
        tool_calls or [],
        ToolPlanContext(query=query, now=datetime(2026, 8, 12, 9, 0, tzinfo=UTC)),
    )


def test_calendar_question_is_forced_to_read_tool_with_current_week_bounds():
    calls = _plan("Tuần này tôi có lịch gì?")

    assert calls[0]["name"] == "calendar_search_events"
    assert calls[0]["args"]["time_from"].startswith("2026-08-10T00:00:00")
    assert calls[0]["args"]["time_to"].startswith("2026-08-17T00:00:00")


def test_calendar_question_without_diacritics_is_routed_the_same_way():
    """Regression: luật cũ khớp có dấu nên người gõ không dấu bị bỏ rơi."""
    calls = _plan("Tuan nay toi co lich gi?")

    assert calls[0]["name"] == "calendar_search_events"
    assert calls[0]["args"]["time_from"].startswith("2026-08-10T00:00:00")
    assert calls[0]["args"]["time_to"].startswith("2026-08-17T00:00:00")


def test_calendar_write_request_is_not_routed_to_read_tool():
    assert _plan("Tạo sự kiện Calendar ngày mai") == []
    assert _plan("Tao su kien Calendar ngay mai") == []


def test_calendar_model_call_missing_bounds_gets_a_bounded_window():
    calls = _plan(
        "Tôi có lịch gì tuần này?",
        [{"name": "calendar_search_events", "args": {}, "id": "model-call"}],
    )

    assert calls[0]["args"]["time_from"].startswith("2026-08-10")
    assert calls[0]["args"]["time_to"].startswith("2026-08-17")


def test_calendar_tool_is_bound_to_agent():
    assert "calendar_search_events" in {tool.name for tool in core_nodes._tools()}


def test_google_document_tools_are_bound_as_read_only():
    names = {tool.name for tool in core_nodes._tools()}

    assert {"google_sheets_task_proposals", "google_docs_task_proposals"} <= names
    assert {"google_sheets_task_proposals", "google_docs_task_proposals"} <= core_nodes._READ_ONLY_TOOLS
