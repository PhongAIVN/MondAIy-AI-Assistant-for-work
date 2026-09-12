"""Endpoint lịch tuần merge sự kiện feed tier A chưa lên Google.

Đảm bảo không nhân bản: row feed đã push (có marker trong payload) KHÔNG được
merge nữa — nó sẽ hiện qua đường Google thường của user.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from src.db import SessionLocal
from src.models.calendar_event import CalendarEvent
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.services.tier_a_feed import FEED_CALENDAR_ID


def _unique_email() -> str:
    return f"tier-a-api-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _seed(db, user_id: str) -> None:
    scope = SourceScope(provider="discord", external_id=f"chan-{uuid.uuid4().hex[:8]}", name="Kênh A", tier="A")
    db.add(scope)
    db.flush()
    db.add(SourceScopeAccess(user_id=user_id, scope_id=scope.id, status="confirmed"))
    db.add(Connection(user_id=user_id, provider="google", status="connected_ready", scopes=""))
    base = datetime.now(UTC).replace(hour=9, minute=0, second=0, microsecond=0)
    db.add(
        CalendarEvent(
            user_id=user_id,
            calendar_id=FEED_CALENDAR_ID,
            event_id="evt-pending@program",
            title="Khai giảng",
            description="",
            starts_at=base,
            ends_at=base + timedelta(hours=2),
            all_day=False,
            status="active",
            payload={},
        )
    )
    db.add(
        CalendarEvent(
            user_id=user_id,
            calendar_id=FEED_CALENDAR_ID,
            event_id="evt-pushed@program",
            title="Đã lên Google",
            description="",
            starts_at=base + timedelta(hours=3),
            ends_at=base + timedelta(hours=4),
            all_day=False,
            status="active",
            payload={"tier_a_google_event_id": "google-1"},
        )
    )
    db.commit()


@pytest.mark.asyncio
async def test_calendar_events_merges_pending_feed_events_only(client, monkeypatch):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        _seed(db, user_id)
    finally:
        db.close()

    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)

    window_start = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    window_end = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    async def fake_search(db, uid, time_from, time_to, query="", calendar_id=None):
        return {
            "calendars": [{"id": "primary", "name": "Lịch chính"}],
            "events": [
                {
                    "id": "google-event-1",
                    "title": "Việc trên Google",
                    "start_at": window_start,
                    "end_at": None,
                    "all_day": False,
                    "status": "confirmed",
                    "source_id": "primary",
                }
            ],
        }

    with patch("src.services.calendar_tools.search_calendar_events", side_effect=fake_search):
        response = await client.get(
            "/api/v1/tasks/calendar-events",
            params={"timeFrom": window_start, "timeTo": window_end},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    event_ids = [event["id"] for event in body["events"]]
    # Sự kiện chưa push được merge vào lưới lịch ngay.
    assert "evt-pending@program" in event_ids
    # Sự kiện đã có trên Google thì KHÔNG merge nữa — tránh nhân bản.
    assert "evt-pushed@program" not in event_ids
    assert "google-event-1" in event_ids
    calendar_ids = [calendar["id"] for calendar in body["calendars"]]
    assert FEED_CALENDAR_ID in calendar_ids


@pytest.mark.asyncio
async def test_calendar_events_skips_feed_for_non_tier_a_user(client, monkeypatch):
    _, token = await _register(client)

    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)

    window_start = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    window_end = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    async def fake_search(db, uid, time_from, time_to, query="", calendar_id=None):
        return {"calendars": [{"id": "primary", "name": "Lịch chính"}], "events": []}

    with patch("src.services.calendar_tools.search_calendar_events", side_effect=fake_search):
        response = await client.get(
            "/api/v1/tasks/calendar-events",
            params={"timeFrom": window_start, "timeTo": window_end},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["events"] == []
    assert all(calendar["id"] != FEED_CALENDAR_ID for calendar in body["calendars"])
