from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy.orm import Session

from src.connectors.base import Source
from src.connectors.calendar import CalendarConnector
from src.services.connections import preferred_connection

_MAX_CALENDARS_PER_SEARCH = 50
_MAX_EVENTS_PER_SEARCH = 500


async def search_calendar_events(
    db: Session,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
    query: str = "",
    calendar_id: str | None = None,
) -> dict:
    """Bounded read tool used by intent execution; returns evidence, not prose.

    With no explicit ``calendar_id``, search every visible calendar in the
    authenticated account. Google users commonly keep the primary calendar
    empty and put school/work schedules in secondary calendars.
    """
    connection = preferred_connection(db, user_id, "google")
    if connection is None:
        raise ValueError("Chưa có kết nối Google Calendar cho người dùng này.")
    if time_from >= time_to:
        raise ValueError("Khoảng Calendar không hợp lệ: time_from phải sớm hơn time_to.")

    connector = CalendarConnector(connection, db)
    if calendar_id:
        sources = [Source(id=calendar_id, name=calendar_id)]
    else:
        sources = (await connector.list_sources())[:_MAX_CALENDARS_PER_SEARCH]
        if not sources:
            sources = [Source(id="primary", name="Lịch chính")]

    # Đọc song song mọi calendar thay vì tuần tự — tài khoản Google thật hay có
    # hàng chục calendar (lịch môn học, ngày lễ, lịch phụ...), mỗi lệnh gọi
    # httpx tới Google có timeout riêng 15s (connectors/calendar.py). Tuần tự
    # thì N calendar cộng dồn tới N×15s, vượt xa timeout 15s phía frontend
    # (apiClient.ts) và làm cả trang treo dù không có calendar nào thật sự lỗi.
    fetches = await asyncio.gather(
        *(connector.fetch_range(source, time_from, time_to, max_events=_MAX_EVENTS_PER_SEARCH) for source in sources)
    )

    normalized: list[dict] = []
    searched_calendars: list[dict[str, str]] = []
    for source, events in zip(sources, fetches, strict=True):
        searched_calendars.append({"id": source.id, "name": source.name})
        for raw_event in events:
            if len(normalized) >= _MAX_EVENTS_PER_SEARCH:
                break
            event = connector.normalize(raw_event, source)
            event["calendar_name"] = source.name
            event["evidence"]["calendar_name"] = source.name
            normalized.append(event)

    if query:
        query_folded = query.casefold()
        normalized = [event for event in normalized if query_folded in event["text"].casefold()]
    normalized.sort(key=lambda event: event["sent_at"])
    return {
        "tool": "calendar_search_events",
        "calendar_id": calendar_id or "all_visible",
        "calendars": searched_calendars,
        "time_from": time_from.isoformat(),
        "time_to": time_to.isoformat(),
        "events": normalized,
        "evidence_count": len(normalized),
    }
