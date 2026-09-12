import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.connectors.calendar import CalendarReadOnlyError
from src.db import SessionLocal
from src.models.calendar_event import CalendarEvent, CalendarOperation
from src.models.connection import Connection

_WRITE_SCOPES = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.readonly"


def _unique_email() -> str:
    return f"test-calendar-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_google_connection(user_id: str, scopes: str = _WRITE_SCOPES) -> None:
    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready", scopes=scopes))
        db.commit()
    finally:
        db.close()


def _cache_event(
    user_id: str,
    *,
    event_id: str = "evt-1",
    calendar_id: str = "primary",
    starts_at: datetime | None = None,
    status: str = "active",
) -> int:
    """Nạp sẵn một sự kiện vào bộ nhớ đệm để test nhánh đọc không gọi Google."""
    starts_at = starts_at or datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
    db = SessionLocal()
    try:
        row = CalendarEvent(
            user_id=user_id,
            calendar_id=calendar_id,
            event_id=event_id,
            title="Họp nhóm",
            description="",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            all_day=False,
            status=status,
            payload={
                "summary": "Họp nhóm",
                "description": "",
                "start": {"dateTime": starts_at.isoformat()},
                "end": {"dateTime": (starts_at + timedelta(hours=1)).isoformat()},
            },
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _google_event(event_id: str = "evt-1", *, summary: str = "Họp nhóm", hour: int = 9) -> dict:
    start = datetime(2026, 8, 12, hour, 0, tzinfo=UTC)
    return {
        "id": event_id,
        "summary": summary,
        "description": "",
        "status": "confirmed",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(hours=1)).isoformat()},
        "htmlLink": "https://calendar.google.com/event?eid=abc",
        "updated": "2026-08-11T10:00:00Z",
    }


def _window() -> dict[str, str]:
    return {
        "timeFrom": datetime(2026, 8, 10, tzinfo=UTC).isoformat(),
        "timeTo": datetime(2026, 8, 17, tzinfo=UTC).isoformat(),
    }


@pytest.mark.asyncio
async def test_week_view_reads_cache_without_calling_google(client, monkeypatch):
    """FR-102: mở lịch lần sau phải hiện ngay từ bộ nhớ đệm, không gọi API."""
    user_id, token = await _register(client)
    _cache_event(user_id)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Nhánh mặc định không được gọi Google Calendar.")

    monkeypatch.setattr("src.services.calendar_cache.refresh_window", fail_if_called)

    response = await client.get(
        "/api/v1/calendar/events",
        params=_window(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == "cache"
    assert [event["title"] for event in body["events"]] == ["Họp nhóm"]
    assert body["lastSyncedAt"] is not None


@pytest.mark.asyncio
async def test_week_view_never_returns_other_users_events(client):
    """FR-105: ngưỡng cho rò dữ liệu giữa người dùng là 0."""
    owner_id, _ = await _register(client)
    _cache_event(owner_id, event_id="evt-owner")
    _, intruder_token = await _register(client)

    response = await client.get(
        "/api/v1/calendar/events",
        params=_window(),
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.asyncio
async def test_week_view_excludes_stale_events(client):
    """FR-104: sự kiện không còn ở nguồn bị đánh dấu, không hiện lại trên lưới."""
    user_id, token = await _register(client)
    _cache_event(user_id, event_id="evt-gone", status="stale")

    response = await client.get(
        "/api/v1/calendar/events",
        params=_window(),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["events"] == []


@pytest.mark.asyncio
async def test_refresh_reports_failed_calendars(client, monkeypatch):
    """FR-045: một lịch lỗi phải được báo ra, không im lặng coi như đủ."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)

    async def fake_refresh(db, *, user_id, connection, time_from, time_to):
        return {"calendars": [{"id": "primary", "name": "Lịch chính"}], "failed_calendars": ["work"], "synced_count": 0}

    monkeypatch.setattr("src.api.calendar.calendar_cache.refresh_window", fake_refresh)

    response = await client.get(
        "/api/v1/calendar/events",
        params={**_window(), "refresh": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["origin"] == "refreshed"
    assert body["failedCalendars"] == ["work"]


@pytest.mark.asyncio
async def test_create_event_writes_immediately_and_returns_undo_handle(client, monkeypatch):
    """FR-069: thao tác trực tiếp ghi ngay, nhưng phải hoàn tác được (BR-14)."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)

    async def fake_create(self, **kwargs):
        return _google_event("evt-new", summary=kwargs["title"])

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)

    response = await client.post(
        "/api/v1/calendar/events",
        json={
            "calendarId": "primary",
            "title": "Workshop",
            "startAt": "2026-08-12T09:00:00+00:00",
            "endAt": "2026-08-12T10:00:00+00:00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["event"]["id"] == "evt-new"
    assert body["operationId"] > 0
    assert body["undoExpiresAt"] is not None


@pytest.mark.asyncio
async def test_create_events_batch_writes_only_reviewed_items(client, monkeypatch):
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    calls: list[str] = []

    async def fake_create(self, **kwargs):
        calls.append(kwargs["title"])
        return _google_event(f"evt-{len(calls)}", summary=kwargs["title"])

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)
    response = await client.post(
        "/api/v1/calendar/events/batch",
        json={
            "calendarId": "primary",
            "events": [
                {"title": "Môn A", "startAt": "2026-08-12T09:00:00+00:00", "endAt": "2026-08-12T10:00:00+00:00"},
                {"title": "Môn B", "startAt": "2026-08-13T09:00:00+00:00", "endAt": "2026-08-13T10:00:00+00:00"},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert calls == ["Môn A", "Môn B"]
    assert len(body["created"]) == 2
    assert body["failed"] == []


@pytest.mark.asyncio
async def test_create_event_without_end_time_is_rejected(client):
    """FR-061: thời gian còn mơ hồ thì để trống, máy chủ không tự điền."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)

    response = await client.post(
        "/api/v1/calendar/events",
        json={"calendarId": "primary", "title": "Workshop", "startAt": "2026-08-12T09:00:00+00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_write_with_read_only_token_asks_for_reconnect(client):
    """Token chỉ đọc phải trả lỗi hướng dẫn kết nối lại, không thử ghi."""
    user_id, token = await _register(client)
    _create_google_connection(user_id, scopes="https://www.googleapis.com/auth/calendar.readonly")

    response = await client.post(
        "/api/v1/calendar/events",
        json={
            "calendarId": "primary",
            "title": "Workshop",
            "startAt": "2026-08-12T09:00:00+00:00",
            "endAt": "2026-08-12T10:00:00+00:00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "kết nối lại" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_event_only_sends_changed_fields(client, monkeypatch):
    """Kéo đổi giờ không được ghi đè những trường mondaiy không quản lý."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    _cache_event(user_id)
    captured: dict = {}

    async def fake_update(self, **kwargs):
        captured.update(kwargs)
        return _google_event("evt-1", hour=14)

    monkeypatch.setattr("src.api.calendar.CalendarConnector.update_event", fake_update)

    response = await client.patch(
        "/api/v1/calendar/events/evt-1",
        json={
            "calendarId": "primary",
            "startAt": "2026-08-12T14:00:00+00:00",
            "endAt": "2026-08-12T15:00:00+00:00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured["title"] is None
    assert captured["description"] is None
    assert captured["starts_at"].hour == 14


@pytest.mark.asyncio
async def test_delete_event_keeps_snapshot_for_undo(client, monkeypatch):
    """BR-14: xoá trên Google không lấy lại được, nên bản chụp phải còn."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    _cache_event(user_id)

    async def fake_delete(self, **kwargs):
        return None

    monkeypatch.setattr("src.api.calendar.CalendarConnector.delete_event", fake_delete)

    response = await client.delete(
        "/api/v1/calendar/events/evt-1?calendarId=primary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db = SessionLocal()
    try:
        row = db.query(CalendarEvent).filter_by(user_id=user_id, event_id="evt-1").one()
        assert row.status == "deleted"
        assert row.payload["summary"] == "Họp nhóm"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_delete_read_only_event_returns_conflict_without_mutating_cache(client, monkeypatch):
    """Google 403 là xung đột quyền ghi, không phải upstream outage."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    _cache_event(user_id, calendar_id="holiday")

    async def fake_delete(self, **kwargs):
        raise CalendarReadOnlyError("Lịch này chỉ đọc nên không xoá sự kiện được.")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.delete_event", fake_delete)

    response = await client.delete(
        "/api/v1/calendar/events/evt-1?calendarId=holiday",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "chỉ đọc" in response.json()["detail"]
    db = SessionLocal()
    try:
        row = db.query(CalendarEvent).filter_by(user_id=user_id, event_id="evt-1").one()
        assert row.status == "active"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_undo_delete_recreates_event_from_snapshot(client, monkeypatch):
    """Hoàn tác một lần xoá phải dựng lại sự kiện từ bản chụp đã lưu."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    _cache_event(user_id)
    created_payloads: list[dict] = []

    async def fake_delete(self, **kwargs):
        return None

    async def fake_create(self, **kwargs):
        created_payloads.append(kwargs)
        return _google_event("evt-restored", summary=kwargs["title"])

    monkeypatch.setattr("src.api.calendar.CalendarConnector.delete_event", fake_delete)
    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)

    deleted = await client.delete(
        "/api/v1/calendar/events/evt-1?calendarId=primary",
        headers={"Authorization": f"Bearer {token}"},
    )
    operation_id = deleted.json()["operationId"]

    response = await client.post(
        f"/api/v1/calendar/operations/{operation_id}/undo",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert created_payloads[0]["title"] == "Họp nhóm"
    assert response.json()["event"]["id"] == "evt-restored"


@pytest.mark.asyncio
async def test_undo_after_window_is_refused(client, monkeypatch):
    """Quá hạn hoàn tác phải nói rõ, không im lặng bỏ qua."""
    user_id, token = await _register(client)
    _create_google_connection(user_id)
    _cache_event(user_id)

    async def fake_delete(self, **kwargs):
        return None

    monkeypatch.setattr("src.api.calendar.CalendarConnector.delete_event", fake_delete)
    deleted = await client.delete(
        "/api/v1/calendar/events/evt-1?calendarId=primary",
        headers={"Authorization": f"Bearer {token}"},
    )
    operation_id = deleted.json()["operationId"]

    db = SessionLocal()
    try:
        operation = db.get(CalendarOperation, operation_id)
        operation.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    response = await client.post(
        f"/api/v1/calendar/operations/{operation_id}/undo",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "quá thời gian" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_undo_belonging_to_another_user_is_not_found(client, monkeypatch):
    """Mã thao tác của người khác không được hoàn tác dù đoán đúng số."""
    owner_id, owner_token = await _register(client)
    _create_google_connection(owner_id)
    _cache_event(owner_id)

    async def fake_delete(self, **kwargs):
        return None

    monkeypatch.setattr("src.api.calendar.CalendarConnector.delete_event", fake_delete)
    deleted = await client.delete(
        "/api/v1/calendar/events/evt-1?calendarId=primary",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    operation_id = deleted.json()["operationId"]

    _, intruder_token = await _register(client)
    response = await client.post(
        f"/api/v1/calendar/operations/{operation_id}/undo",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_window_longer_than_limit_is_rejected(client):
    user_id, token = await _register(client)

    response = await client.get(
        "/api/v1/calendar/events",
        params={
            "timeFrom": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            "timeTo": datetime(2026, 6, 1, tzinfo=UTC).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
