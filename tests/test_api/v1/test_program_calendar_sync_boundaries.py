"""Ranh giới của đồng bộ lịch chương trình — các ca ADR-009 và ADR-010 đặt ra.

Ba câu hỏi ở đây đều là câu "nếu sai thì sai im lặng": người này có đọc được
ánh xạ lịch của người kia không, mốc đã gỡ có còn chui sang lịch cá nhân không,
và khoá nhiều trường một lúc thì lần nhập feed sau còn tôn trọng đủ không.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_event import ProgramEvent
from src.models.user import User
from src.services.program_calendar import import_program_calendar
from src.services.program_calendar_sync import plan_program_sync
from src.services.program_cohorts import configured_program_cohort_slug

SAMPLE = (Path(__file__).resolve().parents[2] / "fixtures" / "v1" / "program_calendar_sample.ics").read_text(
    encoding="utf-8"
)
_WRITE_SCOPES = "https://www.googleapis.com/auth/calendar.events"


async def _register(client) -> tuple[str, str]:
    email = f"test-sync-bound-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    with SessionLocal() as db:
        user = db.get(User, int(data["userId"]))
        assert user is not None
        user.program_cohort_slug = configured_program_cohort_slug()
        db.commit()
    return data["userId"], data["accessToken"]


def _connect_google(user_id: str) -> None:
    with SessionLocal() as db:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready", scopes=_WRITE_SCOPES))
        db.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _google_event(event_id: str) -> dict:
    start = datetime(2026, 7, 1, 13, 0, tzinfo=UTC)
    return {
        "id": event_id,
        "summary": "[Chương trình] WORKSHOP 01: Mo dau",
        "description": "",
        "status": "confirmed",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": start.isoformat()},
        "htmlLink": "https://calendar.google.com/event?eid=abc",
        "updated": "2026-07-01T10:00:00Z",
    }


@pytest.fixture
def cohort(monkeypatch):
    slug = f"bound-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=slug)

    from src.config import get_settings

    monkeypatch.setattr(get_settings(), "program_cohort_slug", slug, raising=False)
    yield slug

    with SessionLocal() as db:
        ids = [row.id for row in db.query(ProgramEvent).filter(ProgramEvent.cohort_slug == slug)]
        if ids:
            db.execute(delete(ProgramCalendarSync).where(ProgramCalendarSync.program_event_id.in_(ids)))
        db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == slug))
        db.commit()


@pytest.fixture
def muc_a(monkeypatch):
    monkeypatch.setattr("src.api.calendar.reconcile_program_access", lambda db, user_id: "A")


def _event_id(cohort: str, title: str) -> int:
    with SessionLocal() as db:
        return db.query(ProgramEvent).filter(ProgramEvent.cohort_slug == cohort, ProgramEvent.title == title).one().id


@pytest.mark.asyncio
async def test_khong_doc_duoc_anh_xa_lich_cua_nguoi_khac(client, monkeypatch, cohort, muc_a):
    """PRD §4.3 đặt ngưỡng rò dữ liệu giữa người dùng là 0.

    Người A đồng bộ một mốc; người B mở cùng bảng xem trước phải thấy mốc đó ở
    trạng thái `create` — tức là hệ thống không nhìn thấy ánh xạ của người A.
    """
    a_id, a_token = await _register(client)
    _connect_google(a_id)

    async def fake_create(self, **kwargs):
        return _google_event("evt-cua-a")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)

    workshop_id = _event_id(cohort, "WORKSHOP 01: Mo dau")
    await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [workshop_id]},
        headers=_auth(a_token),
    )

    b_id, b_token = await _register(client)
    _connect_google(b_id)
    xem_cua_b = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(b_token))

    cua_b = next(item for item in xem_cua_b.json()["items"] if item["programEventId"] == workshop_id)
    assert cua_b["action"] == "create"

    with SessionLocal() as db:
        dong = db.query(ProgramCalendarSync).filter(ProgramCalendarSync.program_event_id == workshop_id)
        assert {row.user_id for row in dong} == {a_id}


@pytest.mark.asyncio
async def test_moc_da_go_khong_con_de_xuat_dong_bo(client, cohort, muc_a):
    """Quản trị gỡ một mốc thì nó phải biến khỏi bảng xem trước ngay lần sau."""
    _, token = await _register(client)
    workshop_id = _event_id(cohort, "WORKSHOP 01: Mo dau")

    truoc = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    assert any(item["programEventId"] == workshop_id for item in truoc.json()["items"])

    with SessionLocal() as db:
        db.get(ProgramEvent, workshop_id).status = "archived"
        db.commit()

    sau = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    assert all(item["programEventId"] != workshop_id for item in sau.json()["items"])


@pytest.mark.asyncio
async def test_moc_nhap_khong_de_xuat_dong_bo(client, cohort, muc_a):
    """Mốc chưa phát hành không được rò sang học viên qua đường đồng bộ."""
    _, token = await _register(client)
    workshop_id = _event_id(cohort, "WORKSHOP 01: Mo dau")
    with SessionLocal() as db:
        db.get(ProgramEvent, workshop_id).status = "draft"
        db.commit()

    xem = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))

    assert all(item["programEventId"] != workshop_id for item in xem.json()["items"])


@pytest.mark.asyncio
async def test_go_moc_sau_khi_hoc_vien_da_dong_bo_thi_bao_ro(client, monkeypatch, cohort, muc_a):
    """Mốc đã nằm trong lịch Google của học viên rồi mới bị gỡ.

    Ta không xoá hộ event trong lịch của họ (BR-09 và ADR-010 khoản 5), nên
    điều bắt buộc còn lại là ánh xạ vẫn còn để giải thích được vì sao lịch của
    họ có một buổi không còn trong chương trình.
    """
    user_id, token = await _register(client)
    _connect_google(user_id)

    async def fake_create(self, **kwargs):
        return _google_event("evt-1")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)

    workshop_id = _event_id(cohort, "WORKSHOP 01: Mo dau")
    await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [workshop_id]},
        headers=_auth(token),
    )

    with SessionLocal() as db:
        db.get(ProgramEvent, workshop_id).status = "archived"
        db.commit()

    with SessionLocal() as db:
        con_lai = (
            db.query(ProgramCalendarSync)
            .filter(
                ProgramCalendarSync.user_id == user_id,
                ProgramCalendarSync.program_event_id == workshop_id,
            )
            .one()
        )
        assert con_lai.event_id == "evt-1"

        # Và mốc đã gỡ không còn được đề xuất ghi lại lần nữa.
        ke_hoach = plan_program_sync(db, user_id=user_id, cohort_slug=cohort)
    assert all(item.program_event_id != workshop_id for item in ke_hoach)


def test_khoa_nhieu_truong_thi_lan_nhap_sau_ton_trong_du(cohort):
    """Khoá 3 trường một lúc: feed chỉ được ghi vào phần còn lại."""
    workshop_id = _event_id(cohort, "WORKSHOP 01: Mo dau")
    with SessionLocal() as db:
        row = db.get(ProgramEvent, workshop_id)
        row.title = "Tiêu đề nội bộ"
        row.host = "Người nội bộ"
        row.location_url = "https://noi-bo.test/room"
        row.locked_fields = ["title", "host", "location_url"]
        db.commit()

    doi_feed = (
        SAMPLE.replace("SUMMARY:WORKSHOP 01: Mo dau", "SUMMARY:Ten moi tu BTC")
        .replace("LOCATION:https://example.test/room/1", "LOCATION:https://phoenix.test/room/9")
        .replace("DTEND:20260701T150000Z", "DTEND:20260701T160000Z")
    )

    with SessionLocal() as db:
        ket_qua = import_program_calendar(db, doi_feed, cohort_slug=cohort)
        sau = db.get(ProgramEvent, workshop_id)

        assert sau.title == "Tiêu đề nội bộ"
        assert sau.host == "Người nội bộ"
        assert sau.location_url == "https://noi-bo.test/room"
        # Trường không khoá vẫn nhận cập nhật — đó là lý do khoá theo trường
        # chứ không theo cả dòng.
        assert sau.ends_at.hour == 16
        assert ket_qua.conflicts == 1
