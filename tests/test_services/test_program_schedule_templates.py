"""Kiểm tra sinh lịch lặp theo cohort và trạng thái phát hành."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from src.db import SessionLocal
from src.models.program_event import ProgramEvent
from src.models.program_schedule_template import ProgramScheduleTemplate
from src.models.user import User
from src.services.program_calendar import list_program_events
from src.services.program_schedule_templates import generate_template_events


def _template(cohort: str, *, published: bool = False) -> ProgramScheduleTemplate:
    return ProgramScheduleTemplate(
        cohort_slug=cohort,
        title="Khung học buổi sáng",
        description="Học tập trung",
        event_type="custom",
        weekdays="0,1,2,3,4",
        start_time="09:00",
        end_time="13:00",
        starts_on=date(2026, 1, 5),
        ends_on=date(2026, 1, 11),
        active=True,
        published=published,
        created_by="test",
    )


def _cleanup(db, cohort: str) -> None:
    db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == cohort))
    db.execute(delete(ProgramScheduleTemplate).where(ProgramScheduleTemplate.cohort_slug == cohort))
    db.commit()


def test_template_generates_weekdays_in_local_timezone_and_draft_is_hidden(monkeypatch):
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "app_timezone", "Asia/Ho_Chi_Minh", raising=False)
    cohort = f"template-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        template = _template(cohort)
        db.add(template)
        db.flush()
        generated = generate_template_events(db, template)
        assert len(generated) == 5
        assert generated[0].starts_at == datetime(2026, 1, 5, 2, 0, tzinfo=UTC)
        assert all(event.status == "draft" for event in generated)
        db.commit()
        assert list_program_events(db, cohort_slug=cohort) == []
        _cleanup(db, cohort)


def test_publishing_template_exposes_only_matching_cohort_events():
    cohort = f"template-{uuid4().hex[:8]}"
    other = f"other-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        template = _template(cohort, published=True)
        db.add(template)
        db.flush()
        generated = generate_template_events(db, template)
        db.commit()
        assert len(generated) == 5
        visible = list_program_events(db, cohort_slug=cohort)
        assert len(visible) == 5
        assert all(event.cohort_slug == cohort and event.visibility == "program" for event in visible)
        assert list_program_events(db, cohort_slug=other) == []
        _cleanup(db, cohort)


def test_template_re_generation_is_idempotent():
    cohort = f"template-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        template = _template(cohort, published=True)
        db.add(template)
        db.flush()
        first = generate_template_events(db, template)
        second = generate_template_events(db, template)
        db.commit()
        assert {event.external_id for event in first} == {event.external_id for event in second}
        assert db.scalar(select(ProgramEvent.id).where(ProgramEvent.cohort_slug == cohort)) is not None
        assert len(list(db.scalars(select(ProgramEvent).where(ProgramEvent.cohort_slug == cohort)))) == 5
        _cleanup(db, cohort)


def test_published_mentor_duty_template_remains_team_scoped():
    cohort = f"template-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        template = _template(cohort, published=True)
        template.event_type = "mentor_duty"
        db.add(template)
        db.flush()

        generated = generate_template_events(db, template)
        db.commit()

        assert generated
        assert all(event.visibility == "team" for event in generated)
        assert list_program_events(db, cohort_slug=cohort) == []
        _cleanup(db, cohort)


@pytest.mark.asyncio
async def test_admin_template_endpoint_generates_published_events(client, monkeypatch):
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "app_secret_key", "test-secret-key", raising=False)
    email = f"template-admin-{uuid4().hex[:8]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert registered.status_code == 201
    user_id = registered.json()["userId"]
    token = registered.json()["accessToken"]
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        assert user is not None
        user.role = "admin"
        db.commit()
    cohort = f"template-{uuid4().hex[:8]}"
    response = await client.post(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "cohortSlug": cohort,
            "title": "Khung 3A",
            "weekdays": [0, 1, 2, 3, 4],
            "startTime": "09:00",
            "endTime": "13:00",
            "startsOn": "2026-01-05",
            "endsOn": "2026-01-11",
            "published": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["published"] is True
    listed = await client.get(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert any(row["id"] == response.json()["id"] for row in listed.json())
    published = await client.post(
        f"/api/v1/admin/program-schedule-templates/{response.json()['id']}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert published.status_code == 200
    assert published.json()["published"] is True
    default_cohort = f"template-default-{uuid4().hex[:8]}"
    monkeypatch.setattr(settings, "program_cohort_slug", default_cohort, raising=False)
    omitted = await client.post(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Khung dùng cohort cấu hình",
            "weekdays": [0],
            "startTime": "09:00",
            "endTime": "10:00",
            "startsOn": "2026-01-05",
            "endsOn": "2026-01-05",
        },
    )
    assert omitted.status_code == 201, omitted.text
    assert omitted.json()["cohortSlug"] == default_cohort
    with SessionLocal() as db:
        rows = list(db.scalars(select(ProgramEvent).where(ProgramEvent.cohort_slug == cohort)))
        assert len(rows) == 5
        assert all(row.status == "published" for row in rows)
        _cleanup(db, cohort)
        _cleanup(db, default_cohort)
        user = db.get(User, int(user_id))
        if user is not None:
            db.delete(user)
            db.commit()


@pytest.mark.asyncio
async def test_program_schedule_template_admin_routes_reject_non_admin(client, monkeypatch):
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "app_secret_key", "test-secret-key", raising=False)
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": f"template-user-{uuid4().hex[:8]}@example.com", "password": "correct-horse-1"},
    )
    user_id = registered.json()["userId"]
    response = await client.get(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {registered.json()['accessToken']}"},
    )
    assert response.status_code == 403
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        if user is not None:
            db.delete(user)
            db.commit()


@pytest.mark.asyncio
async def test_admin_template_endpoint_rejects_invalid_cohort_and_schedule(client, monkeypatch):
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "app_secret_key", "test-secret-key", raising=False)
    email = f"template-validation-{uuid4().hex[:8]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    user_id = registered.json()["userId"]
    token = registered.json()["accessToken"]
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        assert user is not None
        user.role = "admin"
        db.commit()
    payload = {
        "cohortSlug": "INVALID cohort",
        "title": "Khung lỗi",
        "weekdays": [0],
        "startTime": "09:00",
        "endTime": "13:00",
        "startsOn": "2026-01-05",
        "endsOn": "2026-01-11",
    }
    response = await client.post(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert response.status_code == 422
    payload.update(
        {
            "cohortSlug": "cohort-valid",
            "weekdays": [0, 0],
            "startTime": "13:00",
            "endTime": "09:00",
            "startsOn": "2026-01-11",
            "endsOn": "2026-01-05",
        }
    )
    invalid_schedule = await client.post(
        "/api/v1/admin/program-schedule-templates",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert invalid_schedule.status_code == 422
    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        if user is not None:
            db.delete(user)
            db.commit()
