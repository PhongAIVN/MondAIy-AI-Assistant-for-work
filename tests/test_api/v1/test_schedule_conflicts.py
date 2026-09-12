"""Test endpoint luồng task/sự kiện trùng nhau."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.calendar_event import CalendarEvent
from src.models.schedule_conflict import ScheduleConflict
from src.models.task import Task

TIME_FROM = "2026-08-17T00:00:00+00:00"
TIME_TO = "2026-08-24T00:00:00+00:00"
DUE_AT = datetime(2026, 8, 18, 14, 0, tzinfo=UTC)


async def _register(client) -> tuple[str, str]:
    email = f"test-conflicts-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _seed_conflicting_pair(user_id: str, *, task_title: str, event_title: str, task_status: str = "confirmed") -> int:
    """Tạo một task và một sự kiện chắc chắn trùng nhau, trả về task_id."""
    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
            title=task_title,
            detail="",
            due_at=DUE_AT,
            status=task_status,
            source_count=2,
            signal_strength=1.0,
        )
        db.add(task)
        db.add(
            CalendarEvent(
                user_id=user_id,
                calendar_id="primary",
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                title=event_title,
                starts_at=DUE_AT + timedelta(minutes=15),
                ends_at=DUE_AT + timedelta(minutes=75),
                status="active",
                deep_link="https://calendar.google.com/event?eid=abc",
            )
        )
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _detect(client, token: str, *, time_to: str = TIME_TO):
    """Gọi detect qua `params` để dấu + của offset múi giờ không bị hiểu là dấu cách."""
    return await client.post(
        "/api/v1/schedule-conflicts/detect",
        params={"timeFrom": TIME_FROM, "timeTo": time_to},
        headers=_auth(token),
    )


@pytest.mark.asyncio
async def test_detect_returns_the_conflict_with_both_sides(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo milestone 2", event_title="Mentor office hours")

    response = await _detect(client, token)

    assert response.status_code == 200
    body = response.json()
    assert body["openCount"] == 1
    conflict = body["conflicts"][0]
    assert conflict["conflictType"] == "time_overlap"
    assert conflict["overlapMinutes"] == 15
    assert conflict["suggestion"] == "prioritize_task"
    assert conflict["suggestionReasons"] == ["task_multi_source"]
    assert conflict["task"]["title"] == "Nộp báo cáo milestone 2"
    assert conflict["event"]["title"] == "Mentor office hours"
    assert conflict["event"]["deepLink"]


@pytest.mark.asyncio
async def test_detect_is_idempotent(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    first = await _detect(client, token)
    second = await _detect(client, token)

    assert [row["id"] for row in first.json()["conflicts"]] == [row["id"] for row in second.json()["conflicts"]]


@pytest.mark.asyncio
async def test_detect_rejects_a_naive_window(client):
    _, token = await _register(client)

    response = await client.post(
        "/api/v1/schedule-conflicts/detect",
        params={"timeFrom": "2026-08-17T00:00:00", "timeTo": "2026-08-24T00:00:00"},
        headers=_auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_detect_rejects_a_window_wider_than_the_cap(client):
    _, token = await _register(client)

    response = await _detect(client, token, time_to="2026-12-24T00:00:00+00:00")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_filters_by_status(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    await _detect(client, token)

    open_rows = await client.get("/api/v1/schedule-conflicts?status=open", headers=_auth(token))
    resolved_rows = await client.get("/api/v1/schedule-conflicts?status=resolved", headers=_auth(token))

    assert len(open_rows.json()["conflicts"]) == 1
    assert resolved_rows.json()["conflicts"] == []
    # openCount luôn đếm dòng đang chờ, không phụ thuộc bộ lọc đang xem.
    assert resolved_rows.json()["openCount"] == 1


@pytest.mark.asyncio
async def test_resolve_records_the_decision(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    detected = await _detect(client, token)
    conflict_id = detected.json()["conflicts"][0]["id"]

    response = await client.post(
        f"/api/v1/schedule-conflicts/{conflict_id}/resolve",
        json={"resolution": "prioritize_event", "note": "Họp mentor không dời được."},
        headers=_auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["resolution"] == "prioritize_event"
    assert body["resolutionNote"] == "Họp mentor không dời được."
    assert body["resolvedAt"]


@pytest.mark.asyncio
async def test_resolving_twice_returns_conflict(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    detected = await _detect(client, token)
    conflict_id = detected.json()["conflicts"][0]["id"]
    payload = {"resolution": "accept_both"}
    await client.post(f"/api/v1/schedule-conflicts/{conflict_id}/resolve", json=payload, headers=_auth(token))

    again = await client.post(f"/api/v1/schedule-conflicts/{conflict_id}/resolve", json=payload, headers=_auth(token))

    assert again.status_code == 409


@pytest.mark.asyncio
async def test_unknown_resolution_is_rejected(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    detected = await _detect(client, token)
    conflict_id = detected.json()["conflicts"][0]["id"]

    response = await client.post(
        f"/api/v1/schedule-conflicts/{conflict_id}/resolve",
        json={"resolution": "delete_event"},
        headers=_auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_another_user_cannot_read_or_resolve_a_conflict(client):
    owner_id, owner_token = await _register(client)
    _, other_token = await _register(client)
    _seed_conflicting_pair(owner_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    detected = await _detect(client, owner_token)
    conflict_id = detected.json()["conflicts"][0]["id"]

    listed = await client.get("/api/v1/schedule-conflicts", headers=_auth(other_token))
    resolve = await client.post(
        f"/api/v1/schedule-conflicts/{conflict_id}/resolve",
        json={"resolution": "accept_both"},
        headers=_auth(other_token),
    )

    assert listed.json()["conflicts"] == []
    assert resolve.status_code == 404


@pytest.mark.asyncio
async def test_endpoints_require_authentication(client):
    detect = await client.post(
        "/api/v1/schedule-conflicts/detect",
        params={"timeFrom": TIME_FROM, "timeTo": TIME_TO},
    )
    listed = await client.get("/api/v1/schedule-conflicts")

    assert detect.status_code in (401, 403)
    assert listed.status_code in (401, 403)


@pytest.mark.asyncio
async def test_confirming_a_task_detects_its_conflicts(client):
    user_id, token = await _register(client)
    task_id = _seed_conflicting_pair(
        user_id,
        task_title="Nộp báo cáo",
        event_title="Mentor office hours",
        task_status="proposed",
    )

    confirm = await client.post(f"/api/v1/tasks/{task_id}/confirm", headers=_auth(token))
    listed = await client.get("/api/v1/schedule-conflicts?status=open", headers=_auth(token))

    assert confirm.status_code == 200
    conflicts = listed.json()["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["task"]["taskId"] == task_id
    # Trạng thái bên task đọc live nên đã là confirmed ngay sau khi xác nhận.
    assert conflicts[0]["task"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_resolving_a_same_item_conflict_dismisses_the_duplicate_task(client):
    user_id, token = await _register(client)
    task_id = _seed_conflicting_pair(
        user_id,
        task_title="Nộp báo cáo milestone 2",
        event_title="Nộp báo cáo Milestone 2",
        task_status="proposed",
    )
    detected = await _detect(client, token)
    conflict = detected.json()["conflicts"][0]
    assert conflict["conflictType"] == "same_item"

    await client.post(
        f"/api/v1/schedule-conflicts/{conflict['id']}/resolve",
        json={"resolution": "prioritize_event"},
        headers=_auth(token),
    )
    task = await client.get(f"/api/v1/tasks/{task_id}", headers=_auth(token))

    assert task.json()["status"] == "dismissed"
    assert task.json()["calendarEventId"] == conflict["event"]["eventId"]


@pytest.mark.asyncio
async def test_resolved_rows_keep_their_history_after_a_later_detect(client):
    user_id, token = await _register(client)
    _seed_conflicting_pair(user_id, task_title="Nộp báo cáo", event_title="Mentor office hours")
    conflict_id = (await _detect(client, token)).json()["conflicts"][0]["id"]
    await client.post(
        f"/api/v1/schedule-conflicts/{conflict_id}/resolve",
        json={"resolution": "prioritize_task"},
        headers=_auth(token),
    )

    again = await _detect(client, token)

    assert again.json()["conflicts"] == []
    db = SessionLocal()
    try:
        assert db.get(ScheduleConflict, conflict_id).status == "resolved"
    finally:
        db.close()
