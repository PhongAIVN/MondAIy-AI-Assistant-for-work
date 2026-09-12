import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from src.db import SessionLocal
from src.models.app_rating import AppRating
from src.models.calendar_event import CalendarEvent
from src.models.cluster import Cluster, ClusterMessage
from src.models.connection import Connection
from src.models.conversation import Conversation
from src.models.meeting_note import MeetingNote
from src.models.message import Message
from src.models.program_information import ProgramInformationRequest
from src.models.reminder import Reminder
from src.models.routine import Routine
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.user import User
from src.services import account_deletion
from src.services.connections import google
from src.services.crypto import encrypt_token


def _unique_email() -> str:
    return f"delete-me-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _seed_full_footprint(user_id: str) -> None:
    """Rải dữ liệu vào các bảng đại diện — bảng có FK cascade thật (task_evidence,
    cluster_messages, reminders qua task_id) VÀ bảng chỉ có user_id rời (connection,
    conversation, meeting_note, routine, app_rating, calendar_event, reminder
    kind=daily_brief không gắn task)."""
    db = SessionLocal()
    try:
        message = Message(
            user_id=user_id,
            provider="google",
            source_id="inbox",
            external_id=f"ext-{uuid.uuid4().hex[:8]}",
            text="noi dung test",
            sent_at=datetime.now(UTC),
            deep_link="https://mail.google.com/mail/u/0/#all/x",
        )
        db.add(message)
        db.flush()

        cluster = Cluster(user_id=user_id, cluster_key=f"ck-{uuid.uuid4().hex[:8]}")
        db.add(cluster)
        db.flush()
        db.add(ClusterMessage(cluster_id=cluster.id, message_id=message.id))

        task = Task(user_id=user_id, cluster_key=cluster.cluster_key, title="Task test", detail="")
        db.add(task)
        db.flush()
        cluster.task_id = task.id

        db.add(
            TaskEvidence(
                task_id=task.id, message_id=message.id, provider="google", evidence_quote="q", deep_link="https://x"
            )
        )
        db.add(
            Reminder(
                task_id=task.id, user_id=user_id, kind="task_due", milestone="1_day",
                scheduled_at=datetime.now(UTC),
            )
        )
        db.add(
            Reminder(
                task_id=None, user_id=user_id, kind="daily_brief", milestone="", scheduled_at=datetime.now(UTC)
            )
        )
        db.add(
            Connection(
                user_id=user_id, provider="google", account_label="a@b.com",
                access_token_encrypted=encrypt_token("plain-access-token"),
            )
        )
        db.add(Conversation(user_id=user_id, title="Conv test"))
        db.add(MeetingNote(user_id=user_id, title="Note test"))
        db.add(Routine(user_id=user_id, name="Routine test", instructions="lam gi do"))
        db.add(AppRating(user_id=user_id, rating=5))
        db.add(
            ProgramInformationRequest(
                requester_id=int(user_id),
                cohort_slug="ai20k-cohort-3",
                shared_question="Lịch chương trình thay đổi thế nào?",
                consented_at=datetime.now(UTC),
            )
        )
        db.add(
            CalendarEvent(
                user_id=user_id, calendar_id="primary", event_id="evt-1", title="Event test",
                starts_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()


def _count_all_footprint_rows(user_id: str) -> dict[str, int]:
    db = SessionLocal()
    try:
        counts = {}
        for model in account_deletion._TABLES_WITHOUT_USER_FK:
            counts[model.__tablename__] = db.execute(
                select(model).where(model.user_id == user_id)
            ).scalars().all().__len__()
        counts["connections"] = len(
            db.execute(select(Connection).where(Connection.user_id == user_id)).scalars().all()
        )
        counts["program_information_requests"] = len(
            db.execute(
                select(ProgramInformationRequest).where(
                    ProgramInformationRequest.requester_id == int(user_id)
                )
            ).scalars().all()
        )
        counts["messages"] = len(db.execute(select(Message).where(Message.user_id == user_id)).scalars().all())
        counts["task_evidence"] = len(
            db.execute(
                select(TaskEvidence).join(Task, TaskEvidence.task_id == Task.id).where(Task.user_id == user_id)
            ).scalars().all()
        )
        return counts
    finally:
        db.close()


@pytest.mark.asyncio
async def test_delete_account_wipes_every_table_and_the_user_row(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_full_footprint(user_id)

    before = _count_all_footprint_rows(user_id)
    assert before["messages"] == 1
    assert before["task_evidence"] == 1
    assert before["connections"] == 1
    assert before["conversations"] == 1
    assert before["meeting_notes"] == 1
    assert before["routines"] == 1
    assert before["app_ratings"] == 1
    assert before["calendar_events"] == 1
    assert before["reminders"] == 2
    assert before["program_information_requests"] == 1

    async def fake_revoke_token(_access_token: str) -> None:
        pass

    monkeypatch.setattr(google, "revoke_token", fake_revoke_token)

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "correct-horse-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    after = _count_all_footprint_rows(user_id)
    assert all(count == 0 for count in after.values()), after

    db = SessionLocal()
    try:
        assert db.get(User, int(user_id)) is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_delete_account_revokes_connection_tokens_before_deleting(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_full_footprint(user_id)

    revoked_with: list[str] = []

    async def fake_revoke_token(access_token: str) -> None:
        revoked_with.append(access_token)

    monkeypatch.setattr(google, "revoke_token", fake_revoke_token)

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "correct-horse-1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert revoked_with == ["plain-access-token"]


@pytest.mark.asyncio
async def test_delete_account_rejects_wrong_password_and_deletes_nothing(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_full_footprint(user_id)

    response = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "sai-mat-khau"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    db = SessionLocal()
    try:
        assert db.get(User, int(user_id)) is not None
    finally:
        db.close()
    after = _count_all_footprint_rows(user_id)
    assert after["messages"] == 1


@pytest.mark.asyncio
async def test_delete_account_requires_password_when_account_has_one(client):
    _user_id, token = await _register(client)

    response = await client.request(
        "DELETE", "/api/v1/auth/me", json={}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_account_requires_auth(client):
    response = await client.request("DELETE", "/api/v1/auth/me", json={})
    assert response.status_code == 401
