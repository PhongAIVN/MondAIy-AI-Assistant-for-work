"""Kiểm thử luồng đồng bộ lịch chương trình sang lịch cá nhân (ADR-009).

Trọng tâm: xem trước không ghi gì, chỉ ghi đúng mốc user đã duyệt, nguồn đổi thì
hỏi lại chứ không tự sửa, và mức B/C không đồng bộ được.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_event import ProgramEvent
from src.models.user import User
from src.services.program_calendar import import_program_calendar
from src.services.program_cohorts import configured_program_cohort_slug

_WRITE_SCOPES = "https://www.googleapis.com/auth/calendar.events"
SAMPLE = (Path(__file__).resolve().parents[2] / "fixtures" / "v1" / "program_calendar_sample.ics").read_text(
    encoding="utf-8"
)


async def _register(client) -> tuple[str, str]:
    email = f"test-program-sync-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    with SessionLocal() as db:
        user = db.get(User, int(data["userId"]))
        assert user is not None
        user.program_cohort_slug = configured_program_cohort_slug()
        db.commit()
    return data["userId"], data["accessToken"]


def _set_level(user_id: str, level: str) -> None:
    """Đặt thẳng mức truy cập.

    `reconcile_program_access` tự hạ về C khi không có kết nối Discord, nên test
    vá luôn hàm đó ở chỗ dùng; hàm này chỉ lo phần cột trong DB.
    """
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        user.program_access_level = level
        db.commit()


def _connect_google(user_id: str, scopes: str = _WRITE_SCOPES) -> None:
    with SessionLocal() as db:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready", scopes=scopes))
        db.commit()


@pytest.fixture
def cohort(monkeypatch):
    """Nạp lịch mẫu vào một cohort riêng và trỏ cấu hình về đúng cohort đó."""
    slug = f"sync-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=slug)

    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "program_cohort_slug", slug, raising=False)
    yield slug

    with SessionLocal() as db:
        event_ids = [row.id for row in db.query(ProgramEvent).filter(ProgramEvent.cohort_slug == slug)]
        if event_ids:
            db.execute(delete(ProgramCalendarSync).where(ProgramCalendarSync.program_event_id.in_(event_ids)))
        db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == slug))
        db.commit()


@pytest.fixture
def muc_a(monkeypatch):
    """Ép phân loại trả về mức A mà không cần dựng dữ liệu Discord đã cào."""
    monkeypatch.setattr("src.api.calendar.reconcile_program_access", lambda db, user_id: "A")


def _google_event(event_id: str) -> dict:
    start = datetime(2026, 7, 1, 13, 0, tzinfo=UTC)
    return {
        "id": event_id,
        "summary": "[Chương trình] WORKSHOP 01: Mo dau",
        "description": "",
        "status": "confirmed",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": (start + timedelta(hours=2)).isoformat()},
        "htmlLink": "https://calendar.google.com/event?eid=abc",
        "updated": "2026-07-01T10:00:00Z",
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_xem_truoc_khong_ghi_gi_len_google(client, monkeypatch, cohort, muc_a):
    user_id, token = await _register(client)
    _connect_google(user_id)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Bước xem trước không được ghi lên Google.")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fail_if_called)
    monkeypatch.setattr("src.api.calendar.CalendarConnector.update_event", fail_if_called)

    response = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["cohortSlug"] == cohort
    assert {item["action"] for item in body["items"]} == {"create"}


@pytest.mark.asyncio
async def test_xem_truoc_chi_doc_cohort_duoc_gan_cho_user(client, cohort, muc_a):
    user_id, token = await _register(client)
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        assert user is not None
        user.program_cohort_slug = "cohort-other"
        db.commit()

    response = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["cohortSlug"] == "cohort-other"
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_xem_truoc_user_a_chua_duoc_gan_cohort_dung_cohort_cau_hinh(client, cohort, muc_a):
    user_id, token = await _register(client)
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        assert user is not None
        user.program_cohort_slug = None
        db.commit()

    response = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["cohortSlug"] == cohort
    assert response.json()["items"]


@pytest.mark.asyncio
async def test_han_daily_khong_nam_trong_mac_dinh(client, cohort, muc_a):
    """40 mốc daily lặp mỗi ngày — mặc định đổ hết vào lịch cá nhân là phá lịch."""
    _, token = await _register(client)

    response = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    mac_dinh = {item["eventType"] for item in response.json()["items"]}

    chon_them = await client.post(
        "/api/v1/calendar/program-sync/preview",
        json={"eventTypes": ["daily_deadline"]},
        headers=_auth(token),
    )

    assert "daily_deadline" not in mac_dinh
    assert {item["eventType"] for item in chon_them.json()["items"]} == {"daily_deadline"}


@pytest.mark.asyncio
async def test_muc_b_khong_dong_bo_duoc(client, monkeypatch, cohort):
    user_id, token = await _register(client)
    _connect_google(user_id)
    _set_level(user_id, "B")
    monkeypatch.setattr("src.api.calendar.reconcile_program_access", lambda db, user_id: "B")

    xem_truoc = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    ghi = await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [1]},
        headers=_auth(token),
    )

    assert xem_truoc.status_code == 403
    assert ghi.status_code == 403
    assert "chưa khớp danh tính chương trình" in ghi.json()["detail"]


@pytest.mark.asyncio
async def test_chi_ghi_dung_moc_user_da_duyet(client, monkeypatch, cohort, muc_a):
    user_id, token = await _register(client)
    _connect_google(user_id)

    da_ghi = []

    async def fake_create(self, **kwargs):
        da_ghi.append(kwargs["title"])
        return _google_event(f"evt-{len(da_ghi)}")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)

    xem_truoc = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    items = xem_truoc.json()["items"]
    chon = [items[0]["programEventId"]]

    response = await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": chon},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    # Duyệt một mốc thì ghi đúng một mốc, dù bảng xem trước có nhiều dòng hơn.
    assert len(da_ghi) == 1
    assert da_ghi[0].startswith("[Chương trình] ")


@pytest.mark.asyncio
async def test_moc_rieng_cua_nhom_khong_ghi_duoc_du_gui_thang_id(client, monkeypatch, cohort, muc_a):
    """Không tin danh sách ID client gửi lên — lọc lại theo visibility phía máy chủ."""
    user_id, token = await _register(client)
    _connect_google(user_id)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Mốc riêng của nhóm không được ghi vào lịch cá nhân.")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fail_if_called)

    with SessionLocal() as db:
        duty_id = (
            db.query(ProgramEvent)
            .filter(ProgramEvent.cohort_slug == cohort, ProgramEvent.event_type == "mentor_duty")
            .one()
            .id
        )

    response = await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [duty_id]},
        headers=_auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["draft", "archived"])
async def test_apply_rejects_unpublished_event_ids(
    client,
    monkeypatch,
    cohort,
    muc_a,
    status,
):
    """Gửi thẳng ID không được vượt bước phát hành của trang quản trị."""
    user_id, token = await _register(client)
    _connect_google(user_id)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Mốc chưa phát hành không được ghi lên Google.")

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fail_if_called)
    with SessionLocal() as db:
        event = (
            db.query(ProgramEvent)
            .filter(
                ProgramEvent.cohort_slug == cohort,
                ProgramEvent.visibility == "program",
            )
            .first()
        )
        event.status = status
        db.commit()
        event_id = event.id

    response = await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [event_id]},
        headers=_auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dong_bo_lai_khong_nhan_ban_va_nguon_doi_thi_hoi_lai(client, monkeypatch, cohort, muc_a):
    user_id, token = await _register(client)
    _connect_google(user_id)

    async def fake_create(self, **kwargs):
        return _google_event("evt-1")

    cap_nhat = []

    async def fake_update(self, **kwargs):
        cap_nhat.append(kwargs["event_id"])
        return _google_event(kwargs["event_id"])

    monkeypatch.setattr("src.api.calendar.CalendarConnector.create_event", fake_create)
    monkeypatch.setattr("src.api.calendar.CalendarConnector.update_event", fake_update)

    xem_truoc = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    workshop = next(item for item in xem_truoc.json()["items"] if item["title"] == "WORKSHOP 01: Mo dau")
    await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [workshop["programEventId"]]},
        headers=_auth(token),
    )

    # Đồng bộ xong thì mốc đó phải chuyển sang unchanged, không đề nghị ghi lại.
    lan_hai = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    sau_khi_ghi = next(item for item in lan_hai.json()["items"] if item["programEventId"] == workshop["programEventId"])
    assert sau_khi_ghi["action"] == "unchanged"

    # BTC dời giờ sau khi user đã duyệt.
    with SessionLocal() as db:
        row = db.get(ProgramEvent, workshop["programEventId"])
        row.starts_at = row.starts_at + timedelta(hours=1)
        db.commit()

    lan_ba = await client.post("/api/v1/calendar/program-sync/preview", json={}, headers=_auth(token))
    sau_khi_doi = next(item for item in lan_ba.json()["items"] if item["programEventId"] == workshop["programEventId"])
    # BR-09: không tự sửa lịch của user, phải hiện ra để họ duyệt lại.
    assert sau_khi_doi["action"] == "update"
    assert "đổi mốc này" in sau_khi_doi["reason"]
    assert cap_nhat == []

    # Duyệt lại thì sửa đúng event cũ chứ không tạo thêm event trùng.
    await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [workshop["programEventId"]]},
        headers=_auth(token),
    )
    assert cap_nhat == ["evt-1"]

    with SessionLocal() as db:
        rows = (
            db.query(ProgramCalendarSync)
            .filter(
                ProgramCalendarSync.user_id == user_id,
                ProgramCalendarSync.program_event_id == workshop["programEventId"],
            )
            .all()
        )
    assert len(rows) == 1
    assert rows[0].reapproved_count == 1


@pytest.mark.asyncio
async def test_khong_co_quyen_ghi_thi_bao_ket_noi_lai(client, cohort, muc_a):
    user_id, token = await _register(client)
    _connect_google(user_id, scopes="https://www.googleapis.com/auth/calendar.readonly")

    response = await client.post(
        "/api/v1/calendar/program-sync/apply",
        json={"programEventIds": [1]},
        headers=_auth(token),
    )

    assert response.status_code == 409
    assert "quyền ghi" in response.json()["detail"]
