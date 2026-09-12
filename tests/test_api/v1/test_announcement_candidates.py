"""Quyền Type A và idempotency của luồng nạp thông báo Discord."""

import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy import delete, func, select

from src.config import get_settings
from src.db import SessionLocal
from src.models.announcement_candidate import AnnouncementCandidate
from src.models.calendar_event import CalendarEvent, CalendarOperation
from src.models.program_information import ProgramInformationItem, ProgramInformationVersion
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.telemetry import AuditEvent
from src.models.user import User
from src.services import announcement_candidates as announcement_service
from src.services.program_information import search_published_information

ADMIN_PREFIX = "/api/v1/admin/discord-announcements"
LEARNER_PREFIX = "/api/v1/announcement-candidates"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(
    client,
    *,
    role: str = "participant",
    access_level: str = "C",
) -> tuple[int, str]:
    get_settings().app_secret_key = "announcement-candidate-test-secret"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"announcement-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct-horse-1",
        },
    )
    assert response.status_code == 201
    body = response.json()
    user_id = int(body["userId"])
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.role = role
        user.program_access_level = access_level
        db.commit()
    return user_id, body["accessToken"]


@pytest.fixture
def cohort(monkeypatch):
    slug = f"announcement-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(get_settings(), "program_cohort_slug", slug, raising=False)
    yield slug

    with SessionLocal() as db:
        candidates = list(
            db.scalars(
                select(AnnouncementCandidate).where(
                    AnnouncementCandidate.cohort_slug == slug,
                )
            )
        )
        information_ids = [row.information_item_id for row in candidates if row.information_item_id is not None]
        tasks = list(db.scalars(select(Task).where(Task.cluster_key.like("announcement-%"))))
        task_ids = [task.id for task in tasks]
        if task_ids:
            db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
            db.execute(delete(Task).where(Task.id.in_(task_ids)))
        db.execute(
            delete(AnnouncementCandidate).where(
                AnnouncementCandidate.cohort_slug == slug,
            )
        )
        if information_ids:
            db.execute(
                delete(ProgramInformationVersion).where(
                    ProgramInformationVersion.item_id.in_(information_ids),
                )
            )
            db.execute(
                delete(ProgramInformationItem).where(
                    ProgramInformationItem.id.in_(information_ids),
                )
            )
            db.execute(
                delete(AuditEvent).where(
                    AuditEvent.object_type == "program_information",
                    AuditEvent.object_id.in_([str(item_id) for item_id in information_ids]),
                )
            )
        db.execute(delete(User).where(User.email.like("announcement-%@example.com")))
        db.commit()


@pytest.fixture(autouse=True)
def fake_announcement_llm(monkeypatch):
    class Structured:
        async def ainvoke(self, _messages):
            return {
                "title": "Nộp hồ sơ",
                "category": "submission",
                "aliases": ["deadline hồ sơ", "hạn nộp hồ sơ"],
            }

    llm = Mock()
    llm.with_structured_output.return_value = Structured()
    get_llm = Mock(return_value=llm)
    monkeypatch.setattr(announcement_service, "get_llm", get_llm)
    return get_llm


@pytest.mark.asyncio
async def test_non_admin_cannot_preview(client, cohort):
    _, token = await _register(client, access_level="A")

    response = await client.post(
        f"{ADMIN_PREFIX}/preview",
        json={"rawText": "Deadline 24/08/2026 23:59"},
        headers=_auth(token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_only_type_a_can_claim_published_action_idempotently(client, cohort, fake_announcement_llm):
    _, admin_token = await _register(client, role="admin")
    learner_id, learner_token = await _register(client, access_level="A")
    _, level_b_token = await _register(client, access_level="B")
    payload = {
        "rawText": "[REMINDER] Nộp hồ sơ lúc 23:59 hôm nay (24/08/2026)",
        "deepLink": "https://discord.com/channels/program/announcement/1",
        "referenceDate": "2026-08-24T09:39:00+07:00",
    }

    first_preview = await client.post(
        f"{ADMIN_PREFIX}/preview",
        json=payload,
        headers=_auth(admin_token),
    )
    second_preview = await client.post(
        f"{ADMIN_PREFIX}/preview",
        json=payload,
        headers=_auth(admin_token),
    )
    assert first_preview.status_code == 200, first_preview.text
    assert second_preview.json()["id"] == first_preview.json()["id"]
    fake_announcement_llm.assert_called_once_with(lane="work_response")
    candidate_id = first_preview.json()["id"]

    assert first_preview.json()["status"] == "draft"
    assert first_preview.json()["preview"]["category"] == "submission"
    assert first_preview.json()["preview"]["aliases"] == ["deadline hồ sơ", "hạn nộp hồ sơ"]
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProgramInformationItem)
                .where(ProgramInformationItem.cohort_slug == cohort)
            )
            == 0
        )

    first_publish = await client.post(
        f"{ADMIN_PREFIX}/{candidate_id}/publish",
        json={
            "title": "Tiêu đề admin đã sửa",
            "category": "policy",
            "aliases": ["hồ sơ bắt buộc", "quy định hồ sơ"],
            "items": [
                {
                    "title": "Action đã sửa",
                    "kind": "calendar",
                    "dueAt": "2026-08-31T10:00:00+07:00",
                    "allDay": True,
                }
            ],
        },
        headers=_auth(admin_token),
    )
    second_publish = await client.post(
        f"{ADMIN_PREFIX}/{candidate_id}/publish",
        headers=_auth(admin_token),
    )
    assert first_publish.status_code == 200, first_publish.text
    assert second_publish.json()["informationItemId"] == first_publish.json()["informationItemId"]

    denied = await client.get(LEARNER_PREFIX, headers=_auth(level_b_token))
    assert denied.status_code == 403

    visible = await client.get(LEARNER_PREFIX, headers=_auth(learner_token))
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()["items"]] == [candidate_id]

    with SessionLocal() as db:
        information_item = db.get(ProgramInformationItem, first_publish.json()["informationItemId"])
        assert information_item is not None
        assert information_item.category == "policy"
        information_version = db.scalar(
            select(ProgramInformationVersion).where(
                ProgramInformationVersion.item_id == information_item.id,
                ProgramInformationVersion.version == 1,
            )
        )
        assert information_version is not None
        assert information_version.title == "Tiêu đề admin đã sửa"
        assert information_version.body == "[REMINDER] Nộp hồ sơ lúc 23:59 hôm nay (24/08/2026)"
        assert information_version.aliases == ["hồ sơ bắt buộc", "quy định hồ sơ"]
        matches = search_published_information(
            db,
            cohort_slug=cohort,
            allowed_visibilities=frozenset({"program"}),
            query="quy định hồ sơ",
        )
        assert [match.item.id for match in matches] == [information_item.id]
        calendar_before = db.scalar(
            select(func.count())
            .select_from(CalendarEvent)
            .where(
                CalendarEvent.user_id == str(learner_id),
            )
        )
        operations_before = db.scalar(
            select(func.count())
            .select_from(CalendarOperation)
            .where(
                CalendarOperation.user_id == str(learner_id),
            )
        )

    first_task = await client.post(
        f"{LEARNER_PREFIX}/{candidate_id}/actions/0/add-task",
        headers=_auth(learner_token),
    )
    second_task = await client.post(
        f"{LEARNER_PREFIX}/{candidate_id}/actions/0/add-task",
        headers=_auth(learner_token),
    )
    assert first_task.status_code == 200, first_task.text
    assert second_task.json()["taskId"] == first_task.json()["taskId"]

    with SessionLocal() as db:
        task = db.get(Task, first_task.json()["taskId"])
        assert task is not None
        assert task.status == "proposed"
        assert task.title == "Action đã sửa"
        assert task.all_day is True
        assert task.due_at is not None
        assert task.due_at.isoformat().startswith("2026-08-31T10:00:00")
        evidence = list(db.scalars(select(TaskEvidence).where(TaskEvidence.task_id == task.id)))
        assert len(evidence) == 1
        assert evidence[0].deep_link.startswith("https://discord.com/")
        assert (
            db.scalar(
                select(func.count())
                .select_from(CalendarEvent)
                .where(
                    CalendarEvent.user_id == str(learner_id),
                )
            )
            == calendar_before
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(CalendarOperation)
                .where(
                    CalendarOperation.user_id == str(learner_id),
                )
            )
            == operations_before
        )


@pytest.mark.asyncio
async def test_publish_rejects_invalid_review_and_non_admin(client, cohort):
    _, admin_token = await _register(client, role="admin")
    _, learner_token = await _register(client, access_level="A")
    preview_response = await client.post(
        f"{ADMIN_PREFIX}/preview",
        json={"rawText": "Nộp hồ sơ lúc 23:59 hôm nay 24/08/2026"},
        headers=_auth(admin_token),
    )
    assert preview_response.status_code == 200, preview_response.text
    candidate_id = preview_response.json()["id"]

    invalid = await client.post(
        f"{ADMIN_PREFIX}/{candidate_id}/publish",
        json={"category": "deadline", "aliases": []},
        headers=_auth(admin_token),
    )
    empty_items = await client.post(
        f"{ADMIN_PREFIX}/{candidate_id}/publish",
        json={"category": "submission", "aliases": [], "items": []},
        headers=_auth(admin_token),
    )
    denied = await client.post(
        f"{ADMIN_PREFIX}/{candidate_id}/publish",
        json={"category": "submission", "aliases": []},
        headers=_auth(learner_token),
    )

    assert invalid.status_code == 422
    assert empty_items.status_code == 422
    assert denied.status_code == 403
    with SessionLocal() as db:
        candidate = db.get(AnnouncementCandidate, candidate_id)
        assert candidate is not None
        assert candidate.status == "draft"
        assert candidate.information_item_id is None
