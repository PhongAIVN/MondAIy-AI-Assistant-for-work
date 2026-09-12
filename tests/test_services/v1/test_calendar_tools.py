import asyncio
import time
from datetime import datetime

import pytest

from src.connectors.base import Source
from src.services import calendar_tools


@pytest.mark.asyncio
async def test_calendar_search_tool_returns_normalized_evidence(monkeypatch):
    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return object()

    class DB:
        def query(self, model):
            return Query()

        def scalars(self, statement):
            # preferred_connection chuyển sang Session.scalars khi thêm
            # multi-account fallback (order_by connected_at); stub phải theo.
            return Query()

    raw = [{"id": "e1", "summary": "Project review", "start": {"date": "2026-08-20"}, "end": {"date": "2026-08-21"}}]

    async def fake_sources(self):
        return [Source(id="primary", name="Lịch chính")]

    async def fake_fetch(self, source, time_from, time_to, *, max_events=None):
        return raw

    monkeypatch.setattr(calendar_tools.CalendarConnector, "list_sources", fake_sources)
    monkeypatch.setattr(calendar_tools.CalendarConnector, "fetch_range", fake_fetch)

    result = await calendar_tools.search_calendar_events(
        DB(), "user-1", datetime(2026, 8, 1), datetime(2026, 9, 1), query="review"
    )
    assert result["tool"] == "calendar_search_events"
    assert result["evidence_count"] == 1
    assert result["events"][0]["evidence"]["event_id"] == "e1"
    assert result["events"][0]["evidence"]["calendar_name"] == "Lịch chính"


@pytest.mark.asyncio
async def test_calendar_search_includes_events_from_secondary_calendars(monkeypatch):
    """Regression: production account keeps events outside its empty primary calendar."""

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return object()

    class DB:
        def query(self, model):
            return Query()

        def scalars(self, statement):
            # preferred_connection chuyển sang Session.scalars khi thêm
            # multi-account fallback (order_by connected_at); stub phải theo.
            return Query()

    async def fake_sources(self):
        return [
            Source(id="primary", name="Lịch chính"),
            Source(id="school-id", name="School"),
        ]

    async def fake_fetch(self, source, time_from, time_to, *, max_events=None):
        if source.id == "primary":
            return []
        return [
            {
                "id": "lesson-1",
                "summary": "Lịch học",
                "start": {"dateTime": "2026-08-11T08:00:00+07:00"},
                "end": {"dateTime": "2026-08-11T09:00:00+07:00"},
            }
        ]

    monkeypatch.setattr(calendar_tools.CalendarConnector, "list_sources", fake_sources)
    monkeypatch.setattr(calendar_tools.CalendarConnector, "fetch_range", fake_fetch)

    result = await calendar_tools.search_calendar_events(
        DB(),
        "user-1",
        datetime(2026, 8, 11),
        datetime(2026, 8, 12),
    )

    assert result["calendar_id"] == "all_visible"
    assert result["evidence_count"] == 1
    assert result["events"][0]["title"] == "Lịch học"
    assert result["events"][0]["calendar_name"] == "School"


@pytest.mark.asyncio
async def test_calendar_search_fetches_every_calendar_concurrently_not_sequentially(monkeypatch):
    """Regression: tài khoản thật có hàng chục calendar (môn học, ngày lễ...).

    Tuần tự thì N calendar cộng dồn N lần độ trễ mỗi lần gọi Google, dễ vượt
    timeout 15s phía frontend (apiClient.ts DEFAULT_TIMEOUT_MS) và treo cả
    trang Tasks dù không calendar nào thật sự lỗi. Test này giả lập mỗi lần
    gọi Google mất 0.2s — 10 calendar chạy song song phải xong trong khoảng
    1 lần 0.2s (+ dư biên độ), không phải 10 lần cộng dồn (~2s)."""

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return object()

    class DB:
        def query(self, model):
            return Query()

        def scalars(self, statement):
            # preferred_connection chuyển sang Session.scalars khi thêm
            # multi-account fallback (order_by connected_at); stub phải theo.
            return Query()

    calendar_count = 10
    per_call_delay = 0.2

    async def fake_sources(self):
        return [Source(id=f"cal-{i}", name=f"Calendar {i}") for i in range(calendar_count)]

    async def fake_fetch(self, source, time_from, time_to, *, max_events=None):
        await asyncio.sleep(per_call_delay)
        return []

    monkeypatch.setattr(calendar_tools.CalendarConnector, "list_sources", fake_sources)
    monkeypatch.setattr(calendar_tools.CalendarConnector, "fetch_range", fake_fetch)

    started = time.monotonic()
    await calendar_tools.search_calendar_events(DB(), "user-1", datetime(2026, 8, 1), datetime(2026, 9, 1))
    elapsed = time.monotonic() - started

    # Tuần tự sẽ mất >= calendar_count * per_call_delay (~2s). Song song chỉ
    # mất khoảng 1 lần per_call_delay — chừa biên độ rộng cho máy CI chậm.
    assert elapsed < per_call_delay * (calendar_count / 2)


@pytest.mark.asyncio
async def test_calendar_search_tool_rejects_missing_connection():
    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return None

    class DB:
        def query(self, model):
            return Query()

        def scalars(self, statement):
            # preferred_connection chuyển sang Session.scalars khi thêm
            # multi-account fallback (order_by connected_at); stub phải theo.
            return Query()

    with pytest.raises(ValueError, match="kết nối Google Calendar"):
        await calendar_tools.search_calendar_events(DB(), "missing", datetime.now(), datetime.now())
