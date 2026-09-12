"""Tính năng lịch chương trình tier A: feed ICS → mondaiy → Google.

Chính sách: chỉ user đang giữ grant `confirmed` tới một scope tier A mới được
cài lịch; URL feed nằm trong env (rỗng = tắt); mọi sự kiện phải đủ UID,
SUMMARY, DTSTART — thiếu thì bỏ, không tự đoán mốc.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.services import tier_a_feed
from src.services.tier_a_feed import (
    parse_ics,
    sync_tier_a_calendar,
    user_has_tier_a_access,
)


def _unique_email() -> str:
    return f"tier-a-{uuid.uuid4().hex[:12]}@example.com"


def _grant_tier(db, user_id: str, tier: str, *, valid_to=None) -> None:
    scope = SourceScope(
        provider="discord", external_id=f"chan-{uuid.uuid4().hex[:8]}", name="Kênh chương trình", tier=tier
    )
    db.add(scope)
    db.flush()
    db.add(
        SourceScopeAccess(
            user_id=user_id,
            scope_id=scope.id,
            status="confirmed",
            valid_to=valid_to,
        )
    )
    db.commit()


def _google_connection(user_id: str, scopes: str) -> None:
    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready", scopes=scopes))
        db.commit()
    finally:
        db.close()


ICS_SAMPLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Feed
BEGIN:VEVENT
UID:evt-001@program
SUMMARY:Khai giảng khoá AI
DESCRIPTION:Buổi mở đầu
DTSTART;TZID=Asia/Ho_Chi_Minh:20260901T090000
DTEND;TZID=Asia/Ho_Chi_Minh:20260901T110000
END:VEVENT
BEGIN:VEVENT
UID:evt-002@program
SUMMARY:Ngày nghỉ lễ
DTSTART;VALUE=DATE:20260902
DTEND;VALUE=DATE:20260903
END:VEVENT
BEGIN:VEVENT
UID:evt-003@program
SUMMARY:Thiếu giờ bắt đầu
END:VEVENT
BEGIN:VEVENT
SUMMARY:Thiếu UID
DTSTART:20260903T100000Z
END:VEVENT
END:VCALENDAR"""


def test_parse_ics_extracts_valid_events_and_skips_incomplete():
    events = parse_ics(ICS_SAMPLE)

    assert [event["uid"] for event in events] == ["evt-001@program", "evt-002@program"]
    first, holiday = events
    assert first["title"] == "Khai giảng khoá AI"
    assert first["starts_at"].utcoffset() == timedelta(hours=7)
    assert first["all_day"] is False
    assert holiday["all_day"] is True
    assert holiday["ends_at"] - holiday["starts_at"] == timedelta(days=1)


def test_parse_ics_unfolds_continuation_lines():
    sample = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\n"
        "UID:fold-1@program\n"
        "SUMMARY:Tiêu đề dài bị gấp\n"
        " dòng tiếp theo\n"
        "DTSTART:20260903T100000Z\n"
        "DTEND:20260903T110000Z\n"
        "END:VEVENT\n"
        "END:VCALENDAR"
    )
    events = parse_ics(sample)
    assert events[0]["title"] == "Tiêu đề dài bị gấpdòng tiếp theo"


def test_tier_access_requires_confirmed_grant_to_tier_a_scope():
    db = SessionLocal()
    user_id = _unique_email()
    try:
        _grant_tier(db, user_id, "B")
        assert user_has_tier_a_access(db, user_id) is False

        _grant_tier(db, user_id, "A")
        assert user_has_tier_a_access(db, user_id) is True
    finally:
        db.close()


def test_tier_access_expires_with_valid_to():
    db = SessionLocal()
    user_id = _unique_email()
    try:
        expired = datetime.now(UTC) - timedelta(days=1)
        _grant_tier(db, user_id, "A", valid_to=expired)
        assert user_has_tier_a_access(db, user_id) is False
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sync_disabled_without_feed_url(monkeypatch):
    db = SessionLocal()
    user_id = _unique_email()
    try:
        from src.config import get_settings

        monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "", raising=False)
        result = await sync_tier_a_calendar(db, user_id)
        assert result["status"] == "disabled"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sync_skips_user_without_tier_a(monkeypatch):
    db = SessionLocal()
    user_id = _unique_email()
    try:
        from src.config import get_settings

        monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)
        result = await sync_tier_a_calendar(db, user_id)
        assert result["status"] == "not_tier_a"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sync_imports_then_pushes_to_google(monkeypatch):
    db = SessionLocal()
    user_id = _unique_email()
    try:
        from src.config import get_settings

        monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)
        _grant_tier(db, user_id, "A")
        _google_connection(user_id, "https://www.googleapis.com/auth/calendar.events")

        created: list[dict] = []

        class FakeConnector:
            def __init__(self, connection, db):
                pass

            async def create_event(self, **kwargs):
                created.append(kwargs)
                return {"id": f"google-{len(created)}", "htmlLink": "https://cal/1"}

        async def fake_fetch(url):
            return ICS_SAMPLE

        monkeypatch.setattr(tier_a_feed, "_fetch_feed", fake_fetch)
        monkeypatch.setattr("src.connectors.calendar.CalendarConnector", FakeConnector)

        result = await sync_tier_a_calendar(db, user_id)
        assert result["status"] == "synced"
        assert result["imported"] == 2
        assert result["pushed"] == 2
        assert len(created) == 2
        # event_id trên Google phải xác định từ UID — retry không nhân bản.
        assert created[0]["event_id"].startswith("mda")

        rows = tier_a_feed.pending_feed_events(db, user_id)
        assert rows == [], "đã push hết thì không còn sự kiện pending"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sync_without_google_write_scope_imports_only(monkeypatch):
    db = SessionLocal()
    user_id = _unique_email()
    try:
        from src.config import get_settings

        monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)
        _grant_tier(db, user_id, "A")
        _google_connection(user_id, "https://www.googleapis.com/auth/calendar.readonly")

        async def fake_fetch(url):
            return ICS_SAMPLE

        monkeypatch.setattr(tier_a_feed, "_fetch_feed", fake_fetch)

        result = await sync_tier_a_calendar(db, user_id)
        assert result["status"] == "imported_no_google_write"
        assert result["imported"] == 2
        # Chưa push lên được Google → vẫn hiện trong app qua đường merge.
        assert len(tier_a_feed.pending_feed_events(db, user_id)) == 2
    finally:
        db.close()


def test_google_event_id_matches_base32hex_alphabet():
    """Google Events:insert yêu cầu id khớp ^[a-v0-9]+$ — tiền tố 'y' ngoài
    khoảng này khiến 100% lệnh push trả 400 trên production."""
    import re

    event_id = tier_a_feed._google_event_id("evt-001@program")
    assert re.fullmatch(r"[a-v0-9]{5,1024}", event_id), event_id


@pytest.mark.asyncio
async def test_second_sync_preserves_google_marker_and_skips_push(monkeypatch):
    """upsert_event ghi đè payload bằng snapshot mới — marker push phải được
    giữ lại, nếu không lần sync sau re-push toàn bộ (tốn quota + nhân bản UI)."""
    db = SessionLocal()
    user_id = _unique_email()
    try:
        from src.config import get_settings

        monkeypatch.setattr(get_settings(), "tier_a_calendar_feed_url", "https://feed.example/ics", raising=False)
        _grant_tier(db, user_id, "A")
        _google_connection(user_id, "https://www.googleapis.com/auth/calendar.events")

        created: list[dict] = []

        class FakeConnector:
            def __init__(self, connection, db):
                pass

            async def create_event(self, **kwargs):
                created.append(kwargs)
                return {"id": f"google-{len(created)}", "htmlLink": ""}

        async def fake_fetch(url):
            return ICS_SAMPLE

        monkeypatch.setattr(tier_a_feed, "_fetch_feed", fake_fetch)
        monkeypatch.setattr("src.connectors.calendar.CalendarConnector", FakeConnector)

        first = await sync_tier_a_calendar(db, user_id)
        assert first["pushed"] == 2

        second = await sync_tier_a_calendar(db, user_id)
        assert second["status"] == "synced"
        assert second["pushed"] == 0, "lần sync sau không được push lại sự kiện đã có marker"
        assert len(created) == 2
    finally:
        db.close()


def test_unescape_text_rfc5545():
    assert tier_a_feed._unescape_text("Họp\\, kết luận\\; tiếp") == "Họp, kết luận; tiếp"
    assert tier_a_feed._unescape_text("Dòng 1\\nDòng 2") == "Dòng 1\nDòng 2"


def test_should_sync_now_debounces_within_window():
    tier_a_feed._last_sync_at.clear()
    now = datetime.now(UTC)
    assert tier_a_feed.should_sync_now("u1", now=now) is True
    # Trong 15 phút không sync lại.
    assert tier_a_feed.should_sync_now("u1", now=now + timedelta(minutes=10)) is False
    # Hết cửa sổ thì được phép.
    assert tier_a_feed.should_sync_now("u1", now=now + timedelta(minutes=16)) is True
