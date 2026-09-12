import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence


def _unique_email() -> str:
    return f"test-tasks-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_task(user_id: str, status: str = "proposed", due_at: datetime | None = None) -> int:
    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
            title="Test task",
            detail="detail",
            status=status,
            due_at=due_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def _create_google_connection(user_id: str, scopes: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                status="connected_ready",
                scopes=scopes,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_confirm_task_from_proposed_succeeds(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="proposed")

    response = await client.post(f"/api/v1/tasks/{task_id}/confirm", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


@pytest.mark.asyncio
async def test_update_proposed_task_before_confirmation(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="proposed", due_at=datetime(2026, 8, 14, 9, tzinfo=UTC))

    response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Updated task",
            "detail": "Bring the final notes",
            "dueAt": "2026-08-15T10:30:00+07:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated task"
    assert response.json()["detail"] == "Bring the final notes"
    # "2026-08-15T10:30:00+07:00" quy đổi UTC là "2026-08-15T03:30:00Z" — cùng
    # một thời điểm, khác biểu diễn. So thẳng chuỗi local offset là bug kinh
    # điển; so bằng datetime đã parse mới đúng bất kể server trả offset nào.
    assert datetime.fromisoformat(response.json()["dueAt"].replace("Z", "+00:00")) == datetime(
        2026, 8, 15, 3, 30, tzinfo=UTC
    )


@pytest.mark.asyncio
async def test_update_confirmed_task_is_allowed(client):
    """Chính sách tự xác nhận 2026-08-22: task sinh ra đã confirmed nên cửa
    sổ "chỉnh trước khi duyệt" không còn — PATCH mở cho task confirmed đang
    mở thay vì chặn 409."""
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")

    response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Đổi tên sau tự xác nhận", "detail": "Sửa nội dung"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Đổi tên sau tự xác nhận"
    assert response.json()["detail"] == "Sửa nội dung"


@pytest.mark.asyncio
async def test_update_confirmed_task_reschedules_due_reminders(client):
    """Đổi hạn task confirmed phải dời mốc nhắc task_due theo hạn mới — mốc
    cũ còn `scheduled` sẽ nhắc theo giờ cũ dù task đã dời (rủi ro #2 mà
    Antigravity bắt trong review matrix)."""
    user_id, token = await _register(client)
    old_due = datetime.now(UTC) + timedelta(days=3)
    new_due = datetime.now(UTC) + timedelta(days=10)
    task_id = _create_task(user_id, status="confirmed", due_at=old_due)
    db = SessionLocal()
    try:
        db.add(
            Reminder(
                user_id=user_id,
                task_id=task_id,
                kind="task_due",
                milestone="1_day",
                scheduled_at=old_due - timedelta(days=1),
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"dueAt": new_due.isoformat()},
    )

    assert response.status_code == 200
    db = SessionLocal()
    try:
        rows = (
            db.execute(select(Reminder).where(Reminder.task_id == task_id))
            .scalars()
            .all()
        )
        cancelled = [row for row in rows if row.status == "cancelled"]
        assert [row.dismiss_reason for row in cancelled] == ["due_at_rescheduled"]
        fresh = [
            row
            for row in rows
            if row.milestone == "1_day" and row.status == "scheduled"
        ]
        assert len(fresh) == 1
        scheduled_at = fresh[0].scheduled_at
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=UTC)
        assert abs(scheduled_at - (new_due - timedelta(days=1))) < timedelta(minutes=1)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_create_task_from_suggestion_requires_authentication(client):
    response = await client.post(
        "/api/v1/tasks/from-suggestion",
        json={"title": "Nộp báo cáo", "detail": "Gửi PDF"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_task_from_suggestion_creates_proposed_for_current_user(client):
    user_id, token = await _register(client)

    response = await client.post(
        "/api/v1/tasks/from-suggestion",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": " Nộp báo cáo ",
            "detail": " Gửi PDF ",
            "dueAt": "2026-08-14T09:00:00+07:00",
            "allDay": False,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Nộp báo cáo"
    assert body["detail"] == "Gửi PDF"
    assert body["status"] == "proposed"
    assert len(body["clusterKey"]) <= 64
    with SessionLocal() as db:
        row = db.get(Task, body["id"])
        assert row is not None
        assert row.user_id == user_id


@pytest.mark.asyncio
async def test_create_task_from_suggestion_merges_same_title_and_nearby_deadline(client):
    """Hai nguồn xác nhận cùng việc không được tạo hai dòng task."""
    user_id, token = await _register(client)
    due_at = "2026-08-14T09:00:00+07:00"
    first = await client.post(
        "/api/v1/tasks/from-suggestion",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Nộp báo cáo", "detail": "Gửi bản PDF", "dueAt": due_at, "source": "Gmail"},
    )
    assert first.status_code == 201

    duplicate = await client.post(
        "/api/v1/tasks/from-suggestion",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Nộp báo cáo",
            "detail": "Gửi bản PDF",
            # Vẫn trong cửa sổ gần hạn 6 giờ mặc định.
            "dueAt": "2026-08-14T11:00:00+07:00",
            "source": "Ảnh chụp màn hình",
        },
    )

    assert duplicate.status_code == 201
    body = duplicate.json()
    assert body["id"] == first.json()["id"]
    assert body["deduplicated"] is True
    assert body["dedupLayer"] == "exact"
    with SessionLocal() as db:
        rows = db.scalars(select(Task).where(Task.user_id == user_id, Task.title == "Nộp báo cáo")).all()
        assert len(rows) == 1
        assert rows[0].source_count == 1
        evidence = db.scalars(select(TaskEvidence).where(TaskEvidence.task_id == rows[0].id)).all()
        assert [(item.provider, item.evidence_quote) for item in evidence] == [
            ("Ảnh chụp màn hình", "Gửi bản PDF")
        ]


@pytest.mark.asyncio
async def test_create_task_from_suggestion_round_trips_brief_fields(client, monkeypatch):
    monkeypatch.setattr("src.services.auth._secret_key", lambda: "test-only-task-brief-key-at-least-32-chars")
    _, token = await _register(client)
    brief = {
        "expectedOutput": "Bản PDF đã ký",
        "acceptanceCriteria": "Có đủ ba chữ ký",
        "contextInput": "Số liệu chốt tháng 8",
        "constraints": "Không gửi dữ liệu thô",
        "executionTool": "Google Docs",
        "executionMethod": "Review theo checklist",
        "statedPriority": "high",
        "stakeholders": ["Kế toán", "Trưởng phòng"],
        "deliverTo": "email@example.com",
    }
    created = await client.post(
        "/api/v1/tasks/from-suggestion",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Chốt báo cáo", "detail": "Chi tiết", **brief},
    )

    assert created.status_code == 201
    assert {key: created.json()[key] for key in brief} == brief

    listed = await client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200
    saved = next(task for task in listed.json()["tasks"] if task["id"] == created.json()["id"])
    assert {key: saved[key] for key in brief} == brief


@pytest.mark.asyncio
async def test_old_task_with_null_brief_fields_reads_normally(client, monkeypatch):
    monkeypatch.setattr("src.services.auth._secret_key", lambda: "test-only-task-brief-key-at-least-32-chars")
    user_id, token = await _register(client)
    task_id = _create_task(user_id)
    with SessionLocal() as db:
        row = db.get(Task, task_id)
        assert row is not None
        row.stakeholders = None
        db.commit()

    response = await client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    task = next(item for item in response.json()["tasks"] if item["id"] == task_id)
    assert task["title"] == "Test task"
    assert {key: task[key] for key in (
        "expectedOutput", "acceptanceCriteria", "contextInput", "constraints",
        "executionTool", "executionMethod", "statedPriority", "stakeholders", "deliverTo",
        "estimateLowMin", "estimateHighMin",
    )} == {
        "expectedOutput": None, "acceptanceCriteria": None, "contextInput": None,
        "constraints": None, "executionTool": None, "executionMethod": None,
        "statedPriority": None, "stakeholders": None, "deliverTo": None,
        "estimateLowMin": None, "estimateHighMin": None,
    }


@pytest.mark.asyncio
async def test_dismiss_task_from_proposed_succeeds(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="proposed")

    response = await client.post(f"/api/v1/tasks/{task_id}/dismiss", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_dismiss_already_confirmed_task_returns_409(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")

    response = await client.post(f"/api/v1/tasks/{task_id}/dismiss", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_confirm_task_belonging_to_other_user_returns_404(client):
    _, token_a = await _register(client)
    other_user_id, _ = await _register(client)
    task_id = _create_task(other_user_id, status="proposed")

    response = await client.post(f"/api/v1/tasks/{task_id}/confirm", headers={"Authorization": f"Bearer {token_a}"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_tasks_filters_by_status(client):
    user_id, token = await _register(client)
    _create_task(user_id, status="proposed")
    _create_task(user_id, status="confirmed")

    response = await client.get(
        "/api/v1/tasks", params={"status": "confirmed"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_complete_task_records_completion_and_retains_recent_history(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")

    response = await client.post(f"/api/v1/tasks/{task_id}/complete", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["completedAt"] is not None
    assert response.json()["actualMinutes"] is None


@pytest.mark.asyncio
async def test_complete_task_records_user_reported_actual_minutes(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    headers = {"Authorization": f"Bearer {token}"}

    completed = await client.post(
        f"/api/v1/tasks/{task_id}/complete", headers=headers, json={"actualMinutes": 90}
    )
    reread = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)

    assert completed.status_code == 200
    assert completed.json()["actualMinutes"] == 90
    assert reread.status_code == 200
    assert reread.json()["actualMinutes"] == 90


@pytest.mark.asyncio
@pytest.mark.parametrize("actual_minutes", [0, -15, 1441])
async def test_complete_task_rejects_invalid_actual_minutes_without_writing(client, actual_minutes):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")

    response = await client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"actualMinutes": actual_minutes},
    )

    assert response.status_code == 422
    with SessionLocal() as db:
        task = db.get(Task, task_id)
        assert task.status == "confirmed"
        assert task.actual_minutes is None


@pytest.mark.asyncio
async def test_list_tasks_purges_completed_history_after_seven_days(client):
    user_id, token = await _register(client)
    now = datetime.now(UTC)
    old_id = _create_task(user_id, status="completed")
    recent_id = _create_task(user_id, status="completed")
    with SessionLocal() as db:
        old = db.get(Task, old_id)
        recent = db.get(Task, recent_id)
        old.completed_at = now - timedelta(days=8)
        old.updated_at = now - timedelta(days=8)
        recent.completed_at = now - timedelta(days=2)
        recent.updated_at = now - timedelta(days=2)
        db.add(TaskEvidence(task_id=old_id, provider="gmail", evidence_quote="old", deep_link=""))
        db.commit()

    response = await client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["tasks"]}
    assert old_id not in ids
    assert recent_id in ids
    with SessionLocal() as db:
        assert db.get(Task, old_id) is None
        assert db.scalar(select(TaskEvidence.id).where(TaskEvidence.task_id == old_id)) is None


@pytest.mark.asyncio
async def test_calendar_handoff_requires_confirmed_status(client):
    # FR-062: không tạo lời nhắc/mở lịch trước khi xác nhận.
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="proposed", due_at=datetime(2026, 8, 14, 16, 59, tzinfo=UTC))

    response = await client.get(
        f"/api/v1/tasks/{task_id}/calendar-handoff", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_calendar_handoff_requires_due_at(client):
    # FR-061: due_at còn mơ hồ (None) phải để trống, không tự tạo lịch.
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed", due_at=None)

    response = await client.get(
        f"/api/v1/tasks/{task_id}/calendar-handoff", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_calendar_handoff_returns_ics_and_google_url_when_confirmed(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed", due_at=datetime(2026, 8, 14, 16, 59, tzinfo=UTC))

    response = await client.get(
        f"/api/v1/tasks/{task_id}/calendar-handoff", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["icsUrl"].endswith(f"/tasks/{task_id}/calendar-handoff.ics")
    assert body["googleCalendarUrl"].startswith("https://calendar.google.com/calendar/render?")
    assert body["opened"] is False
    # P0 chỉ sinh .ics/link mẫu, không có tích hợp Calendar API thật — trạng
    # thái phải là EXPORTED, không bao giờ được gọi là CALENDAR_SYNCED.
    assert body["status"] == "EXPORTED"


@pytest.mark.asyncio
async def test_calendar_handoff_ics_download_has_calendar_content_type(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed", due_at=datetime(2026, 8, 14, 16, 59, tzinfo=UTC))

    response = await client.get(
        f"/api/v1/tasks/{task_id}/calendar-handoff.ics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in response.text


@pytest.mark.asyncio
async def test_calendar_handoff_opened_without_prior_get_returns_404(client):
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed", due_at=datetime(2026, 8, 14, 16, 59, tzinfo=UTC))

    response = await client.post(
        f"/api/v1/tasks/{task_id}/calendar-handoff/opened", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_calendar_handoff_opened_marks_true_after_requested(client):
    # FR-065: phân biệt "đã xác nhận" với "đã mở trong ứng dụng lịch".
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed", due_at=datetime(2026, 8, 14, 16, 59, tzinfo=UTC))
    headers = {"Authorization": f"Bearer {token}"}

    await client.get(f"/api/v1/tasks/{task_id}/calendar-handoff", headers=headers)
    response = await client.post(f"/api/v1/tasks/{task_id}/calendar-handoff/opened", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["opened"] is True
    assert body["openedAt"] is not None


@pytest.mark.asyncio
async def test_list_calendar_events_returns_users_google_events(client, monkeypatch):
    user_id, token = await _register(client)
    captured = {}

    async def fake_search(db, requested_user_id, time_from, time_to, query="", calendar_id=None):
        captured.update(user_id=requested_user_id, time_from=time_from, time_to=time_to)
        return {
            "calendars": [{"id": "primary", "name": "My calendar"}],
            "events": [
                {
                    "id": "event-1",
                    "title": "Mentor sync",
                    "start_at": "2026-08-12T09:00:00+07:00",
                    "end_at": "2026-08-12T10:00:00+07:00",
                    "all_day": False,
                    "status": "confirmed",
                    "calendar_name": "My calendar",
                    "source_id": "primary",
                    "deep_link": "https://calendar.google.com/calendar/event?eid=1",
                }
            ],
        }

    monkeypatch.setattr("src.api.tasks.calendar_tools.search_calendar_events", fake_search)
    response = await client.get(
        "/api/v1/tasks/calendar-events",
        params={"timeFrom": "2026-08-10T00:00:00Z", "timeTo": "2026-08-17T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured["user_id"] == user_id
    assert response.json()["events"][0]["title"] == "Mentor sync"
    assert response.json()["calendars"] == [
        {"id": "primary", "name": "My calendar", "writable": True}
    ]


@pytest.mark.asyncio
async def test_list_calendar_events_rejects_oversized_window(client):
    _, token = await _register(client)

    response = await client.get(
        "/api/v1/tasks/calendar-events",
        params={"timeFrom": "2026-01-01T00:00:00Z", "timeTo": "2026-08-17T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_calendar_events_requires_timezone_offsets(client):
    _, token = await _register(client)

    response = await client.get(
        "/api/v1/tasks/calendar-events",
        params={"timeFrom": "2026-08-10T00:00:00", "timeTo": "2026-08-17T00:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_confirmed_task_creates_google_event_once(client, monkeypatch):
    user_id, token = await _register(client)
    task_id = _create_task(
        user_id,
        status="confirmed",
        due_at=datetime(2026, 8, 14, 16, 30, tzinfo=UTC),
    )
    _create_google_connection(
        user_id,
        "openid email https://www.googleapis.com/auth/calendar.events",
    )
    calls = []

    async def fake_create(self, **kwargs):
        calls.append(kwargs)
        return {
            "id": "google-event-42",
            "htmlLink": "https://calendar.google.com/calendar/event?eid=42",
        }

    monkeypatch.setattr("src.api.tasks.CalendarConnector.create_event", fake_create)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post(f"/api/v1/tasks/{task_id}/calendar-sync", headers=headers)
    second = await client.post(f"/api/v1/tasks/{task_id}/calendar-sync", headers=headers)

    assert first.status_code == 200
    assert first.json()["calendarEventId"] == "google-event-42"
    assert first.json()["alreadySynced"] is False
    assert second.status_code == 200
    assert second.json()["alreadySynced"] is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_sync_task_requires_calendar_write_scope(client):
    user_id, token = await _register(client)
    task_id = _create_task(
        user_id,
        status="confirmed",
        due_at=datetime(2026, 8, 14, 16, 30, tzinfo=UTC),
    )
    _create_google_connection(
        user_id,
        "openid email https://www.googleapis.com/auth/calendar.readonly",
    )

    response = await client.post(
        f"/api/v1/tasks/{task_id}/calendar-sync",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 409
    assert "kết nối lại" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_summarize_page_extraction_returns_200(client):
    _, token = await _register(client)

    # mock_llm=True: text "ambiguous" theo confidence_tier sẽ đi qua nhánh LLM
    # của hybrid — patch để test tất định, không phụ thuộc mạng/provider thật
    # (xem test riêng cho nhánh gọi LLM thật ở tests/test_services/test_page_extraction.py).
    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        response = await client.post(
            "/api/v1/tasks/summarize-page-extraction",
            headers={"Authorization": f"Bearer {token}"},
            json={"url": "https://example.com", "pageTitle": "Trang mẫu", "text": "Hãy gửi file trước 5h chiều"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["title"] == "Hãy gửi file trước 5h chiều"
    assert suggestion["sourceUrl"] == "https://example.com"
    assert "Nguồn" not in suggestion["detail"]


@pytest.mark.asyncio
async def test_summarize_page_extraction_includes_source_context_as_separate_field(client):
    """sourceContext (vd tên nhóm chat client tự đoán — cần cho SPA route tĩnh
    kiểu Zalo web không đổi url dù đang mở nhóm nào) trả về ở sourceLabel,
    KHÔNG còn nhét vào detail (chật/khó đọc trên panel hẹp — phản hồi người
    dùng 2026-08-26)."""
    _, token = await _register(client)

    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        response = await client.post(
            "/api/v1/tasks/summarize-page-extraction",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "url": "https://chat.zalo.me",
                "pageTitle": "Zalo",
                "text": "Hãy gửi file trước 5h chiều",
                "sourceContext": "S25-64CNTT",
            },
        )

    assert response.status_code == 200, response.text
    suggestion = response.json()["suggestions"][0]
    assert suggestion["sourceUrl"] == "https://chat.zalo.me"
    assert suggestion["sourceLabel"] == "S25-64CNTT"
    assert "S25-64CNTT" not in suggestion["detail"]


@pytest.mark.asyncio
async def test_summarize_page_extraction_response_has_extended_field_keys(client):
    """mock_llm=True đi qua rule-based fallback (không có field mở rộng) —
    test này chỉ khoá lại đúng TÊN KEY camelCase (CamelModel alias) mà
    client/extension/types/index.ts PageExtractionSuggestion đang dựa vào,
    tránh lệch tên lặng lẽ giữa hai bên."""
    _, token = await _register(client)

    settings = get_settings()
    with patch.object(settings, "mock_llm", True):
        response = await client.post(
            "/api/v1/tasks/summarize-page-extraction",
            headers={"Authorization": f"Bearer {token}"},
            json={"url": "https://example.com", "pageTitle": "Trang mẫu", "text": "Hãy gửi file trước 5h chiều"},
        )

    assert response.status_code == 200, response.text
    suggestion = response.json()["suggestions"][0]
    for key in (
        "sourceUrl",
        "sourceLabel",
        "expectedOutput",
        "constraint",
        "executionSteps",
        "executionTool",
        "executionMethod",
        "priority",
        "assignee",
        "stakeholders",
        "deliverTo",
    ):
        assert key in suggestion, f"thiếu key {key}"


@pytest.mark.asyncio
async def test_huy_task_dong_dau_thoi_gian_vao_thung_rac(client) -> None:
    """Không có mốc này thì job dọn không tính được hạn 7 ngày."""
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["cancelledAt"] is not None, (
        "Huỷ mà không đóng dấu thời gian thì task nằm trong thùng rác vĩnh viễn: "
        "job dọn bỏ qua mọi dòng có cancelled_at NULL."
    )


@pytest.mark.asyncio
async def test_khoi_phuc_task_khoi_thung_rac_va_xoa_moc_huy(client) -> None:
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/tasks/{task_id}/cancel", headers=auth)

    response = await client.post(f"/api/v1/tasks/{task_id}/restore", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "proposed", (
        "Khôi phục về 'proposed' chứ không đoán lại trạng thái trước khi huỷ — "
        "hệ không lưu nó, và đoán nhầm thành 'confirmed' thì task âm thầm quay "
        "lại các lời nhắc và mẫu số thống kê."
    )
    assert body["cancelledAt"] is None, (
        "Mốc huỷ phải được xoá, kẻo job dọn xoá vĩnh viễn một task vừa được "
        "người dùng lấy lại."
    )


@pytest.mark.asyncio
async def test_khong_khoi_phuc_duoc_task_khong_nam_trong_thung_rac(client) -> None:
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/tasks/{task_id}/restore", headers=auth)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_khong_khoi_phuc_duoc_task_cua_nguoi_khac(client) -> None:
    user_a, token_a = await _register(client)
    _, token_b = await _register(client)
    task_id = _create_task(user_a, status="confirmed")
    await client.post(f"/api/v1/tasks/{task_id}/cancel", headers={"Authorization": f"Bearer {token_a}"})

    response = await client.post(
        f"/api/v1/tasks/{task_id}/restore", headers={"Authorization": f"Bearer {token_b}"}
    )

    assert response.status_code in {403, 404}


@pytest.mark.asyncio
async def test_bat_dau_lam_ghi_moc_started_at(client) -> None:
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}

    response = await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth)

    assert response.status_code == 200
    assert response.json()["startedAt"] is not None


@pytest.mark.asyncio
async def test_bam_bat_dau_lan_hai_khong_doi_moc(client) -> None:
    """Dời mốc mỗi lần bấm sẽ cắt ngắn thời lượng đo được, và luôn lệch một phía."""
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}

    lan_dau = (await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth)).json()["startedAt"]
    lan_hai = (await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth)).json()["startedAt"]

    assert lan_dau == lan_hai


@pytest.mark.asyncio
async def test_chua_confirmed_thi_khong_bat_dau_duoc(client) -> None:
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="proposed")

    response = await client.post(
        f"/api/v1/tasks/{task_id}/start", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_hoan_thanh_suy_actual_minutes_tu_moc_bat_dau(client) -> None:
    """Đây là cách DUY NHẤT hôm nay thu được actual_minutes.

    Production 27/08: 17 task completed, 0 task có actual_minutes — hộp thoại
    hỏi tay cho phép bỏ qua, và ai cũng bỏ qua.
    """
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth)

    body = (await client.post(f"/api/v1/tasks/{task_id}/complete", headers=auth)).json()

    assert body["actualMinutes"] is not None


@pytest.mark.asyncio
async def test_khong_co_moc_bat_dau_thi_khong_suy_actual_minutes(client) -> None:
    """Suy từ created_at sẽ cho ra khoảng hàng ngày trời và đầu độc reference class."""
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")

    body = (
        await client.post(
            f"/api/v1/tasks/{task_id}/complete", headers={"Authorization": f"Bearer {token}"}
        )
    ).json()

    assert body["actualMinutes"] is None


@pytest.mark.asyncio
async def test_nguoi_dung_tu_khai_thi_thang_so_suy_ra(client) -> None:
    user_id, token = await _register(client)
    task_id = _create_task(user_id, status="confirmed")
    auth = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/tasks/{task_id}/start", headers=auth)

    body = (
        await client.post(
            f"/api/v1/tasks/{task_id}/complete", headers=auth, json={"actualMinutes": 45}
        )
    ).json()

    assert body["actualMinutes"] == 45
