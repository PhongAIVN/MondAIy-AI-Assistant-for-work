from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from src.config import Settings
from src.connectors.base import Source
from src.connectors.calendar import CalendarConnector, CalendarReadOnlyError
from src.services.connections import google


def _event(event_id="e1"):
    return {
        "id": event_id,
        "status": "confirmed",
        "summary": "Mentor sync",
        "description": "Discuss project milestone",
        "location": "Room 2",
        "start": {"dateTime": "2026-08-12T09:00:00+07:00"},
        "end": {"dateTime": "2026-08-12T10:00:00+07:00"},
        "organizer": {"email": "mentor@example.com"},
        "attendees": [{"email": "user@example.com"}],
        "htmlLink": "https://calendar.google.com/calendar/event?eid=e1",
        "updated": "2026-08-01T00:00:00Z",
    }


def test_google_oauth_requests_calendar_read_and_explicit_event_write_scopes(monkeypatch):
    monkeypatch.setattr(
        google,
        "get_settings",
        lambda: SimpleNamespace(
            google_client_id="client-id",
            google_redirect_uri="https://api.example/google/callback",
            google_scopes=(
                "openid email https://www.googleapis.com/auth/gmail.readonly "
                "https://www.googleapis.com/auth/calendar.readonly "
                "https://www.googleapis.com/auth/calendar.events"
            ),
        ),
    )

    scopes = parse_qs(urlsplit(google.build_authorize_url("signed-state")).query)["scope"][0].split()

    assert "https://www.googleapis.com/auth/calendar.readonly" in scopes
    assert "https://www.googleapis.com/auth/calendar.events" in scopes


def test_default_google_oauth_includes_sheets_read_only_scope():
    assert "https://www.googleapis.com/auth/spreadsheets.readonly" in Settings().google_scopes


def test_calendar_normalize_preserves_time_and_evidence():
    item = CalendarConnector(None, None).normalize(_event(), Source(id="primary", name="Primary"))
    assert item["id"] == "e1"
    assert item["title"] == "Mentor sync"
    assert item["start_at"] == "2026-08-12T09:00:00+07:00"
    assert item["end_at"] == "2026-08-12T10:00:00+07:00"
    assert item["all_day"] is False
    assert item["sent_at"] == datetime(2026, 8, 12, 2, 0, tzinfo=UTC)
    assert item["evidence"]["source_url"].startswith("https://calendar.google.com/")
    assert "project milestone" in item["normalized_text"]


def test_calendar_normalize_converts_utc_event_to_app_timezone_for_display(monkeypatch):
    monkeypatch.setattr(
        "src.connectors.calendar.get_settings",
        lambda: type("Settings", (), {"app_timezone": "Asia/Ho_Chi_Minh"})(),
    )
    event = {
        "id": "utc-event",
        "summary": "Lý thuyết AI thực chiến",
        "start": {"dateTime": "2026-08-12T02:00:00Z"},
        "end": {"dateTime": "2026-08-12T06:00:00Z"},
    }

    item = CalendarConnector(None, None).normalize(event, Source(id="primary", name="Primary"))

    assert item["start_at"] == "2026-08-12T09:00:00+07:00"
    assert item["end_at"] == "2026-08-12T13:00:00+07:00"
    assert item["sent_at"] == datetime(2026, 8, 12, 2, 0, tzinfo=UTC)


def test_calendar_normalize_supports_all_day_events():
    event = {"id": "e2", "summary": "Holiday", "start": {"date": "2026-08-15"}, "end": {"date": "2026-08-16"}}
    item = CalendarConnector(None, None).normalize(event, Source(id="primary", name="Primary"))
    assert item["all_day"] is True
    assert item["start_at"] == "2026-08-15"
    assert item["sent_at"] == datetime(2026, 8, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_calendar_fetch_is_bounded_paged_and_skips_cancelled(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    pages = iter(
        [
            {"items": [{**_event(), "status": "cancelled"}, _event("e2")], "nextPageToken": "next"},
            {"items": [_event("e3")], "nextPageToken": None},
        ]
    )
    calls = []

    async def fake_get(client, path, params=None):
        calls.append((path, params))
        return next(pages)

    monkeypatch.setattr(connector, "_get", fake_get)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    events = await connector.fetch_range(
        Source(id="primary", name="Primary"), datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
    )

    assert [event["id"] for event in events] == ["e2", "e3"]
    assert len(calls) == 2
    assert calls[0][1]["singleEvents"] == "true"
    assert calls[0][1]["timeMin"].startswith("2026-08-01")


@pytest.mark.asyncio
async def test_calendar_create_event_posts_user_confirmed_task(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            assert url.endswith("/calendars/primary/events")
            assert json["summary"] == "Submit project report"
            assert json["start"]["dateTime"] == "2026-08-12T09:00:00+00:00"
            assert json["end"]["dateTime"] == "2026-08-12T09:30:00+00:00"
            return type(
                "Response",
                (),
                {
                    "status_code": 201,
                    "json": staticmethod(
                        lambda: {
                            "id": "google-event-1",
                            "htmlLink": "https://calendar.google.com/calendar/event?eid=1",
                        }
                    ),
                },
            )()

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    created = await connector.create_event(
        calendar_id="primary",
        title="Submit project report",
        description="From Gmail\nhttps://mail.google.com/mail/u/0/#inbox/abc",
        starts_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 12, 9, 30, tzinfo=UTC),
    )

    assert created["id"] == "google-event-1"


@pytest.mark.asyncio
async def test_calendar_create_event_includes_attendees_as_google_email_objects(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            assert json["attendees"] == [{"email": "lan@gmail.com"}, {"email": "minh@gmail.com"}]
            return type(
                "Response",
                (),
                {
                    "status_code": 201,
                    "json": staticmethod(lambda: {"id": "google-event-2", "htmlLink": "https://calendar.test/2"}),
                },
            )()

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    created = await connector.create_event(
        calendar_id="primary",
        title="Họp rà soát tiến độ",
        description="",
        starts_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 29, 9, 0, tzinfo=UTC),
        attendees=["lan@gmail.com", "minh@gmail.com"],
    )

    assert created["id"] == "google-event-2"


@pytest.mark.asyncio
async def test_calendar_create_event_omits_attendees_key_when_none_given(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            assert "attendees" not in json
            return type(
                "Response",
                (),
                {
                    "status_code": 201,
                    "json": staticmethod(lambda: {"id": "google-event-3", "htmlLink": "https://calendar.test/3"}),
                },
            )()

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    await connector.create_event(
        calendar_id="primary",
        title="Không có ai được mời",
        description="",
        starts_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 29, 9, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_calendar_create_event_reuses_client_id_after_retry_conflict(monkeypatch):
    requested: list[tuple[str, dict | None]] = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            requested.append((url, json))
            assert json["id"] == "abcdef0123456789"
            return type("Response", (), {"status_code": 409})()

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    async def fake_get(client, path, params=None):
        requested.append((path, params))
        return {"id": "abcdef0123456789", "htmlLink": "https://calendar.test/existing"}

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr(connector, "_get", fake_get)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    created = await connector.create_event(
        calendar_id="primary",
        title="Workshop",
        description="",
        starts_at=datetime(2026, 8, 12, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 12, 10, 0, tzinfo=UTC),
        event_id="abcdef0123456789",
    )

    assert created["id"] == "abcdef0123456789"
    assert requested[1][0].endswith("/events/abcdef0123456789")


@pytest.mark.asyncio
async def test_list_sources_marks_subscribed_calendars_as_read_only(monkeypatch):
    """Lịch ngày lễ nằm trong danh sách nhưng không ghi được.

    Bỏ `accessRole` đi chính là lý do giao diện từng hiện nút Xoá trên sự kiện
    ngày lễ rồi ăn 403 từ Google.
    """

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    async def fake_get(client, path, params=None):
        return {
            "items": [
                {"id": "primary", "summary": "Lịch của tôi", "accessRole": "owner"},
                {"id": "team@group.calendar.google.com", "summary": "Lịch nhóm", "accessRole": "writer"},
                {"id": "vi.vietnamese#holiday@group.v.calendar.google.com",
                 "summary": "Ngày lễ tại Việt Nam", "accessRole": "reader"},
                {"id": "busy@example.com", "summary": "Lịch bận", "accessRole": "freeBusyReader"},
            ]
        }

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr(connector, "_get", fake_get)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    sources = await connector.list_sources()

    assert {source.id: source.writable for source in sources} == {
        "primary": True,
        "team@group.calendar.google.com": True,
        "vi.vietnamese#holiday@group.v.calendar.google.com": False,
        "busy@example.com": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("thao_tac", ["delete", "update"])
async def test_write_to_read_only_calendar_raises_read_only_error(monkeypatch, thao_tac):
    """403 phải thành `CalendarReadOnlyError`, không phải lỗi Google chung.

    Phân biệt này quyết định mã HTTP: 409 (người dùng không có quyền, thử lại vô
    ích) thay vì 502 (Google hỏng, thử lại có thể được).
    """

    class FakeResponse:
        status_code = 403
        text = "forbidden"

        def json(self):
            return {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def delete(self, *args, **kwargs):
            return FakeResponse()

        async def patch(self, *args, **kwargs):
            return FakeResponse()

    connector = CalendarConnector(None, None)

    async def fake_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_token)
    monkeypatch.setattr("src.connectors.calendar.httpx.AsyncClient", lambda **kwargs: FakeClient())

    with pytest.raises(CalendarReadOnlyError) as loi:
        if thao_tac == "delete":
            await connector.delete_event(calendar_id="holiday@group.v.calendar.google.com", event_id="e1")
        else:
            await connector.update_event(
                calendar_id="holiday@group.v.calendar.google.com",
                event_id="e1",
                title="Đổi tên",
            )

    assert "chỉ đọc" in str(loi.value)
