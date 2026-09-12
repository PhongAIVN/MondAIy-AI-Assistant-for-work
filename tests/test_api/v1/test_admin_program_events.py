"""Trang quản trị lịch chương trình (ADR-010).

Trọng tâm: chỉ admin vào được, nháp không lọt sang học viên, và chỉnh sửa tay
không bị lần nhập feed sau xóa mất.
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from src.db import SessionLocal
from src.models.notification_preference import NotificationPreference
from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_event import ProgramEvent
from src.models.program_event_notice import ProgramEventNotice
from src.models.reminder import Reminder
from src.models.user import User
from src.services.program_calendar import import_program_calendar, list_program_events

PREFIX = "/api/v1/admin/program-events"
SAMPLE = (Path(__file__).resolve().parents[2] / "fixtures" / "v1" / "program_calendar_sample.ics").read_text(
    encoding="utf-8"
)


async def _register(client) -> tuple[str, str]:
    email = f"admin-pe-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _promote(user_id: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        user.role = "admin"
        db.commit()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cohort(monkeypatch):
    """Nạp lịch mẫu vào một cohort riêng rồi dọn sạch sau test."""
    slug = f"admin-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=slug)
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "program_cohort_slug", slug, raising=False)
    yield slug
    with SessionLocal() as db:
        event_ids = list(db.scalars(select(ProgramEvent.id).where(ProgramEvent.cohort_slug == slug)))
        notice_rows = (
            list(db.scalars(select(ProgramEventNotice).where(ProgramEventNotice.program_event_id.in_(event_ids))))
            if event_ids
            else []
        )
        reminder_ids = [row.reminder_id for row in notice_rows if row.reminder_id is not None]
        if event_ids:
            db.execute(delete(ProgramEventNotice).where(ProgramEventNotice.program_event_id.in_(event_ids)))
            db.execute(delete(ProgramCalendarSync).where(ProgramCalendarSync.program_event_id.in_(event_ids)))
        if reminder_ids:
            db.execute(delete(Reminder).where(Reminder.id.in_(reminder_ids)))
        db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == slug))
        db.commit()


async def _admin(client) -> str:
    user_id, token = await _register(client)
    _promote(user_id)
    return token


def _create_user() -> str:
    with SessionLocal() as db:
        user = User(email=f"recipient-{uuid.uuid4().hex}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id)


def _workshop_id(cohort: str) -> int:
    with SessionLocal() as db:
        return (
            db.query(ProgramEvent)
            .filter(ProgramEvent.cohort_slug == cohort, ProgramEvent.title == "WORKSHOP 01: Mo dau")
            .one()
            .id
        )


def _make_recipient(
    user_id: str,
    event_id: int,
    *,
    level: str = "A",
    active: bool = True,
    muted: bool = False,
) -> None:
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        user.program_access_level = level
        user.is_active = active
        db.add(
            ProgramCalendarSync(
                user_id=user_id,
                program_event_id=event_id,
                calendar_id="primary",
                event_id=f"google-{user_id}-{event_id}",
                approved_content_hash="previous-revision",
                status="synced",
                approved_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        if muted:
            db.add(
                NotificationPreference(
                    user_id=user_id,
                    muted_kinds=["calendar_changed"],
                )
            )
        db.commit()


@pytest.mark.asyncio
async def test_hoc_vien_thuong_khong_vao_duoc(client, cohort):
    _, token = await _register(client)
    response = await client.get(PREFIX, params={"cohortSlug": cohort}, headers=_auth(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_liet_ke_duoc_ca_nhap_feed_va_trang_thai(client, cohort):
    token = await _admin(client)

    response = await client.get(PREFIX, params={"cohortSlug": cohort}, headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    # Mốc nhập từ feed là bản ban tổ chức đã công bố nên mặc định đã phát hành.
    assert {item["status"] for item in body["items"]} == {"published"}
    assert {item["origin"] for item in body["items"]} == {"feed"}


@pytest.mark.asyncio
async def test_moc_tu_tao_bat_dau_o_nhap_va_chua_toi_tay_hoc_vien(client, cohort):
    token = await _admin(client)
    start = datetime(2026, 7, 20, 13, 0, tzinfo=UTC)

    tao = await client.post(
        PREFIX,
        json={
            "cohortSlug": cohort,
            "title": "Buổi bù cho nhóm chậm tiến độ",
            "startAt": start.isoformat(),
            "endAt": (start + timedelta(hours=2)).isoformat(),
        },
        headers=_auth(token),
    )

    assert tao.status_code == 201
    assert tao.json()["status"] == "draft"
    assert tao.json()["origin"] == "admin"

    with SessionLocal() as db:
        hoc_vien_thay = list_program_events(db, cohort_slug=cohort, limit=50)
    assert all("Buổi bù" not in event.title for event in hoc_vien_thay)

    phat_hanh = await client.post(f"{PREFIX}/{tao.json()['id']}/publish", headers=_auth(token))
    assert phat_hanh.json()["status"] == "published"
    assert phat_hanh.json()["publishedAt"] is not None

    with SessionLocal() as db:
        sau_phat_hanh = list_program_events(db, cohort_slug=cohort, limit=50)
    assert any("Buổi bù" in event.title for event in sau_phat_hanh)


@pytest.mark.asyncio
async def test_rut_ve_nhap_thi_hoc_vien_khong_con_thay(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)

    await client.post(f"{PREFIX}/{event_id}/unpublish", headers=_auth(token))

    with SessionLocal() as db:
        con_lai = list_program_events(db, cohort_slug=cohort, limit=50)
    assert all(event.id != event_id for event in con_lai)


@pytest.mark.asyncio
async def test_sua_tay_thi_lan_nhap_feed_sau_khong_ghi_de(client, cohort):
    """Không khóa trường đã sửa thì mọi chỉnh sửa biến mất sau lần đồng bộ kế tiếp."""
    token = await _admin(client)
    event_id = _workshop_id(cohort)

    sua = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"title": "WORKSHOP 01: Kick-off (bản đã sửa)"},
        headers=_auth(token),
    )
    assert sua.status_code == 200
    assert sua.json()["lockedFields"] == ["title"]

    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=cohort)
        sau_khi_nhap = db.get(ProgramEvent, event_id)
        assert sau_khi_nhap.title == "WORKSHOP 01: Kick-off (bản đã sửa)"
        # Trường không sửa tay vẫn nhận cập nhật từ feed như thường.
        assert sau_khi_nhap.location_url == "https://example.test/room/1"


@pytest.mark.asyncio
async def test_feed_doi_dung_truong_dang_khoa_thi_bao_xung_dot(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)
    await client.patch(
        f"{PREFIX}/{event_id}",
        json={"title": "Tên do ban tổ chức nội bộ đặt"},
        headers=_auth(token),
    )

    doi_feed = SAMPLE.replace("SUMMARY:WORKSHOP 01: Mo dau", "SUMMARY:WORKSHOP 01: Ten moi tu BTC")
    with SessionLocal() as db:
        ket_qua = import_program_calendar(db, doi_feed, cohort_slug=cohort)

    assert ket_qua.conflicts == 1
    response = await client.get(PREFIX, params={"cohortSlug": cohort, "conflictsOnly": True}, headers=_auth(token))
    body = response.json()
    assert body["conflictCount"] == 1
    xung_dot = body["items"][0]
    # Bản của admin vẫn đang hiển thị; bản của BTC nằm trong feedPayload để so.
    assert xung_dot["title"] == "Tên do ban tổ chức nội bộ đặt"
    assert xung_dot["feedPayload"]["title"] == "WORKSHOP 01: Ten moi tu BTC"


@pytest.mark.asyncio
async def test_hoan_ve_ban_goc_bo_khoa_va_nhan_lai_cap_nhat(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)
    await client.patch(f"{PREFIX}/{event_id}", json={"title": "Sửa nhầm"}, headers=_auth(token))

    hoan = await client.post(f"{PREFIX}/{event_id}/revert-to-source", headers=_auth(token))

    assert hoan.status_code == 200
    assert hoan.json()["title"] == "WORKSHOP 01: Mo dau"
    assert hoan.json()["lockedFields"] == []
    assert hoan.json()["sourceConflict"] is False


@pytest.mark.asyncio
async def test_moc_tu_tao_khong_bi_lan_nhap_feed_dung_toi(client, cohort):
    token = await _admin(client)
    start = datetime(2026, 7, 21, 13, 0, tzinfo=UTC)
    tao = await client.post(
        PREFIX,
        json={"cohortSlug": cohort, "title": "Mốc nội bộ", "startAt": start.isoformat()},
        headers=_auth(token),
    )
    event_id = tao.json()["id"]

    with SessionLocal() as db:
        ket_qua = import_program_calendar(db, SAMPLE, cohort_slug=cohort)
        con_nguyen = db.get(ProgramEvent, event_id)

    assert ket_qua.skipped_admin == 0  # mốc admin không có UID trong feed
    assert con_nguyen.title == "Mốc nội bộ"
    assert con_nguyen.origin == "admin"


@pytest.mark.asyncio
async def test_luu_vet_moi_thay_doi_vao_audit(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)

    await client.patch(f"{PREFIX}/{event_id}", json={"host": "BTC nội bộ"}, headers=_auth(token))
    await client.post(f"{PREFIX}/{event_id}/unpublish", headers=_auth(token))

    audit = await client.get("/api/v1/admin/audit", headers=_auth(token))
    actions = {row["action"] for row in audit.json()["items"]}
    assert "program_event_updated" in actions
    assert "program_event_draft" in actions


@pytest.mark.asyncio
async def test_admin_action_cannot_cross_configured_cohort(client, cohort):
    token = await _admin(client)
    with SessionLocal() as db:
        foreign = ProgramEvent(
            cohort_slug="another-cohort",
            external_id=f"foreign-{uuid.uuid4().hex}",
            event_type="custom",
            visibility="program",
            title="Mốc cohort khác",
            description="",
            starts_at=datetime(2026, 8, 20, 8, 0, tzinfo=UTC),
            content_hash="foreign",
            observed_at=datetime.now(UTC),
            status="published",
        )
        db.add(foreign)
        db.commit()
        db.refresh(foreign)
        foreign_id = foreign.id

    response = await client.patch(
        f"{PREFIX}/{foreign_id}",
        json={"title": "Không được sửa"},
        headers=_auth(token),
    )
    listing = await client.get(
        PREFIX,
        params={"cohortSlug": "another-cohort"},
        headers=_auth(token),
    )

    assert response.status_code == 404
    assert listing.status_code == 404
    with SessionLocal() as db:
        db.execute(delete(ProgramEvent).where(ProgramEvent.id == foreign_id))
        db.commit()


@pytest.mark.asyncio
async def test_update_validates_merged_time_window(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)
    with SessionLocal() as db:
        current_end = db.get(ProgramEvent, event_id).ends_at
        if current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=UTC)

    response = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"startAt": (current_end + timedelta(minutes=1)).isoformat()},
        headers=_auth(token),
    )

    assert response.status_code == 422
    assert "endAt phải sau startAt" in response.json()["detail"]


@pytest.mark.asyncio
async def test_notifications_are_explicit_scoped_and_server_derived(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)
    eligible_id = _create_user()
    revoked_id = _create_user()
    inactive_id = _create_user()
    muted_id = _create_user()
    no_sync_id = _create_user()
    _make_recipient(eligible_id, event_id)
    _make_recipient(revoked_id, event_id, level="B")
    _make_recipient(inactive_id, event_id, active=False)
    _make_recipient(muted_id, event_id, muted=True)
    with SessionLocal() as db:
        user = db.get(User, int(no_sync_id))
        user.program_access_level = "A"
        db.commit()

    silent = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"host": "BTC cập nhật"},
        headers=_auth(token),
    )
    notified = await client.patch(
        f"{PREFIX}/{event_id}",
        json={
            "startAt": datetime(2026, 7, 1, 14, 0, tzinfo=UTC).isoformat(),
            "notifyUsers": True,
            "changeNote": "Buổi học dời muộn hơn hai giờ.",
        },
        headers=_auth(token),
    )

    assert silent.status_code == 200
    assert silent.json()["notificationCount"] == 0
    assert notified.status_code == 200
    assert notified.json()["notificationCount"] == 1
    assert notified.json()["changedFields"] == ["starts_at"]
    audit = await client.get("/api/v1/admin/audit", headers=_auth(token))
    update_audit = next(
        row for row in audit.json()["items"] if row["action"] == "program_event_updated"
    )
    audit_text = str(update_audit)
    assert update_audit["details"]["after"]["notification_count"] == 1
    assert "Buổi học dời" not in audit_text
    assert "recipient" not in str(update_audit["details"]).lower()
    assert "user_id" not in str(update_audit["details"]).lower()
    assert eligible_id not in audit_text
    with SessionLocal() as db:
        reminders = [
            row
            for row in db.scalars(select(Reminder).where(Reminder.kind == "calendar_changed"))
            if row.payload.get("programEventId") == event_id
        ]
        assert [row.user_id for row in reminders] == [eligible_id]
        assert reminders[0].payload["change"] == "time_changed"
        assert datetime.fromisoformat(reminders[0].payload["previousStartsAt"]) == datetime(
            2026, 7, 1, 13, 0, tzinfo=UTC
        )


@pytest.mark.asyncio
async def test_update_rejects_stale_expected_updated_at_before_mutation(client, cohort):
    token = await _admin(client)
    event_id = _workshop_id(cohort)

    first = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"title": "Bản đầu", "expectedUpdatedAt": None},
        headers=_auth(token),
    )
    stale = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"title": "Không được ghi", "expectedUpdatedAt": None},
        headers=_auth(token),
    )
    current = await client.patch(
        f"{PREFIX}/{event_id}",
        json={
            "title": "Bản mới nhất",
            "expectedUpdatedAt": first.json()["updatedAt"],
        },
        headers=_auth(token),
    )

    assert first.status_code == 200
    assert stale.status_code == 409
    assert current.status_code == 200
    assert current.json()["title"] == "Bản mới nhất"


@pytest.mark.asyncio
async def test_publish_rejects_stale_expected_updated_at_before_status_change(client, cohort):
    token = await _admin(client)
    created = await client.post(
        PREFIX,
        json={
            "title": "Mốc chờ phát hành",
            "startAt": datetime(2026, 8, 26, 8, 0, tzinfo=UTC).isoformat(),
        },
        headers=_auth(token),
    )
    event_id = created.json()["id"]
    stale_revision = created.json()["updatedAt"]
    changed = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"description": "Người khác vừa sửa"},
        headers=_auth(token),
    )

    stale_publish = await client.post(
        f"{PREFIX}/{event_id}/publish",
        json={"expectedUpdatedAt": stale_revision},
        headers=_auth(token),
    )
    current_publish = await client.post(
        f"{PREFIX}/{event_id}/publish",
        json={"expectedUpdatedAt": changed.json()["updatedAt"]},
        headers=_auth(token),
    )

    assert stale_publish.status_code == 409
    assert current_publish.status_code == 200
    assert current_publish.json()["status"] == "published"


@pytest.mark.asyncio
async def test_publish_notice_is_idempotent_and_team_never_fans_out(client, cohort):
    token = await _admin(client)
    start = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
    created = await client.post(
        PREFIX,
        json={"title": "Thông báo lịch mới", "startAt": start.isoformat()},
        headers=_auth(token),
    )
    event_id = created.json()["id"]
    recipient_id = _create_user()
    _make_recipient(recipient_id, event_id)

    first = await client.post(
        f"{PREFIX}/{event_id}/publish",
        json={"notifyUsers": True, "changeNote": "Lịch mới đã được xác nhận."},
        headers=_auth(token),
    )
    await client.post(f"{PREFIX}/{event_id}/unpublish", headers=_auth(token))
    second = await client.post(
        f"{PREFIX}/{event_id}/publish",
        json={"notifyUsers": True, "changeNote": "Gửi lại không được nhân bản."},
        headers=_auth(token),
    )

    assert first.json()["notificationCount"] == 1
    assert second.json()["notificationCount"] == 0

    team_created = await client.post(
        PREFIX,
        json={
            "title": "Lịch riêng của nhóm",
            "visibility": "team",
            "startAt": (start + timedelta(days=1)).isoformat(),
        },
        headers=_auth(token),
    )
    team_event_id = team_created.json()["id"]
    _make_recipient(recipient_id, team_event_id)
    team_published = await client.post(
        f"{PREFIX}/{team_event_id}/publish",
        json={"notifyUsers": True},
        headers=_auth(token),
    )
    assert team_published.json()["notificationCount"] == 0


@pytest.mark.asyncio
async def test_draft_update_cannot_notify_and_archive_is_not_syncable(client, cohort):
    token = await _admin(client)
    created = await client.post(
        PREFIX,
        json={
            "title": "Mốc đang soạn",
            "startAt": datetime(2026, 8, 25, 8, 0, tzinfo=UTC).isoformat(),
        },
        headers=_auth(token),
    )
    event_id = created.json()["id"]

    denied = await client.patch(
        f"{PREFIX}/{event_id}",
        json={"title": "Vẫn là nháp", "notifyUsers": True},
        headers=_auth(token),
    )
    await client.post(f"{PREFIX}/{event_id}/publish", headers=_auth(token))
    archived = await client.post(f"{PREFIX}/{event_id}/archive", headers=_auth(token))

    assert denied.status_code == 409
    assert archived.json()["status"] == "archived"
    assert archived.json()["notificationCount"] == 0
    with SessionLocal() as db:
        from src.services.program_calendar_sync import approved_events

        assert (
            approved_events(
                db,
                user_id="untrusted",
                cohort_slug=cohort,
                program_event_ids=[event_id],
            )
            == []
        )
