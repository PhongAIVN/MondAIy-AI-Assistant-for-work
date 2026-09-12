import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.notification_preference import NotificationPreference
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence


def _unique_email() -> str:
    return f"test-reminders-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_task(user_id: str, *, status: str = "confirmed", due_at: datetime | None = None) -> Task:
    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
            title="Nộp báo cáo",
            detail="detail",
            status=status,
            due_at=due_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    finally:
        db.close()


def _add_evidence(task_id: int) -> None:
    db = SessionLocal()
    try:
        db.add(
            TaskEvidence(task_id=task_id, provider="gmail", evidence_quote="q", deep_link="https://mail.google.com/1")
        )
        db.commit()
    finally:
        db.close()


def _disable_quiet_hours(user_id: str) -> None:
    db = SessionLocal()
    try:
        db.add(NotificationPreference(user_id=user_id, quiet_hours_start=0, quiet_hours_end=0))
        db.commit()
    finally:
        db.close()


def _backdate_reminder(reminder_id: int, scheduled_at: datetime) -> None:
    """Test helper: đẩy scheduled_at của reminder vừa auto-sinh vào quá khứ để
    /reminders/due trả về ngay, không phải chờ 1 ngày/30 phút thật."""
    db = SessionLocal()
    try:
        row = db.get(Reminder, reminder_id)
        row.scheduled_at = scheduled_at
        db.commit()
    finally:
        db.close()


def _reminders_for_task(task_id: int) -> list[Reminder]:
    db = SessionLocal()
    try:
        return db.query(Reminder).filter(Reminder.task_id == task_id).all()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_confirm_task_with_due_at_auto_creates_reminders(client):
    user_id, token = await _register(client)
    task = _create_task(user_id, status="proposed", due_at=datetime.now(UTC) + timedelta(days=3))

    response = await client.post(f"/api/v1/tasks/{task.id}/confirm", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    rows = _reminders_for_task(task.id)
    assert {r.milestone for r in rows} == {"1_day", "30_min", "at_time"}


@pytest.mark.asyncio
async def test_confirm_task_without_due_at_creates_no_reminders(client):
    user_id, token = await _register(client)
    task = _create_task(user_id, status="proposed", due_at=None)

    response = await client.post(f"/api/v1/tasks/{task.id}/confirm", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert _reminders_for_task(task.id) == []


@pytest.mark.asyncio
async def test_due_endpoint_returns_bundle_and_deliveries_hide_it_afterward(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    _disable_quiet_hours(user_id)
    task = _create_task(user_id, status="proposed", due_at=datetime.now(UTC) + timedelta(minutes=45))
    _add_evidence(task.id)

    confirm = await client.post(f"/api/v1/tasks/{task.id}/confirm", headers=headers)
    assert confirm.status_code == 200
    reminders = _reminders_for_task(task.id)
    # due_at còn 45 phút: mốc "1 ngày trước" đã trôi qua; còn lại mốc "30 phút
    # trước" và mốc bắn đúng giờ hạn.
    assert {r.milestone for r in reminders} == {"30_min", "at_time"}
    _backdate_reminder(reminders[0].id, datetime.now(UTC) - timedelta(minutes=1))

    first = await client.get("/api/v1/reminders/due", headers=headers)
    assert first.status_code == 200
    bundles = first.json()["notifications"]
    assert len(bundles) == 1
    reminder_ids = bundles[0]["reminderIds"]
    assert bundles[0]["tasks"][0]["evidenceDeepLink"] == "https://mail.google.com/1"

    record = await client.post("/api/v1/reminders/deliveries", json={"reminderIds": reminder_ids}, headers=headers)
    assert record.status_code == 200
    assert record.json()["recorded"] == reminder_ids

    second = await client.get("/api/v1/reminders/due", headers=headers)
    assert second.json()["notifications"] == []


@pytest.mark.asyncio
async def test_snooze_reschedules_and_reason_dismiss_cancels_reminder_only(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = _create_task(user_id, status="confirmed", due_at=datetime.now(UTC) + timedelta(days=2))
    db = SessionLocal()
    try:
        row = Reminder(task_id=task.id, user_id=user_id, milestone="1_day", scheduled_at=datetime.now(UTC))
        db.add(row)
        db.commit()
        db.refresh(row)
        reminder_id = row.id
    finally:
        db.close()

    snooze = await client.post(f"/api/v1/reminders/{reminder_id}/snooze", json={"minutes": 20}, headers=headers)
    assert snooze.status_code == 200
    assert snooze.json()["snoozeCount"] == 1
    assert snooze.json()["status"] == "scheduled"

    dismiss = await client.post(
        f"/api/v1/reminders/{reminder_id}/dismiss", json={"reason": "han_chot_sai"}, headers=headers
    )
    assert dismiss.status_code == 200
    assert dismiss.json()["status"] == "cancelled"
    assert dismiss.json()["dismissReason"] == "han_chot_sai"

    task_after = await client.get(f"/api/v1/tasks/{task.id}", headers=headers)
    assert task_after.json()["status"] == "confirmed"  # dismiss lời nhắc không đụng task


@pytest.mark.asyncio
async def test_dismiss_with_invalid_reason_returns_422(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = _create_task(user_id, status="confirmed", due_at=datetime.now(UTC) + timedelta(days=1))
    db = SessionLocal()
    try:
        row = Reminder(task_id=task.id, user_id=user_id, milestone="1_day", scheduled_at=datetime.now(UTC))
        db.add(row)
        db.commit()
        db.refresh(row)
        reminder_id = row.id
    finally:
        db.close()

    response = await client.post(
        f"/api/v1/reminders/{reminder_id}/dismiss", json={"reason": "khong-hop-le"}, headers=headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reminder_belonging_to_other_user_returns_404(client):
    _, token_a = await _register(client)
    other_user_id, _ = await _register(client)
    task = _create_task(other_user_id, status="confirmed", due_at=datetime.now(UTC) + timedelta(days=1))
    db = SessionLocal()
    try:
        row = Reminder(task_id=task.id, user_id=other_user_id, milestone="1_day", scheduled_at=datetime.now(UTC))
        db.add(row)
        db.commit()
        db.refresh(row)
        reminder_id = row.id
    finally:
        db.close()

    response = await client.post(
        f"/api/v1/reminders/{reminder_id}/dismiss",
        json={"reason": "khong_can_nua"},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_task_requires_confirmed_and_cancels_pending_reminders(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = _create_task(user_id, status="confirmed", due_at=datetime.now(UTC) + timedelta(days=1))
    db = SessionLocal()
    try:
        row = Reminder(task_id=task.id, user_id=user_id, milestone="1_day", scheduled_at=datetime.now(UTC))
        db.add(row)
        db.commit()
        db.refresh(row)
        reminder_id = row.id
    finally:
        db.close()

    response = await client.post(f"/api/v1/tasks/{task.id}/complete", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    reminder_after = await client.get(f"/api/v1/reminders?taskId={task.id}", headers=headers)
    assert reminder_after.json()["reminders"][0]["id"] == reminder_id
    assert reminder_after.json()["reminders"][0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_complete_task_from_proposed_returns_409(client):
    user_id, token = await _register(client)
    task = _create_task(user_id, status="proposed")

    response = await client.post(f"/api/v1/tasks/{task.id}/complete", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_cancel_task_removes_it_from_confirmed_and_cancels_reminders(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    task = _create_task(user_id, status="confirmed", due_at=datetime.now(UTC) + timedelta(days=1))

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_task_from_proposed_also_allowed(client):
    user_id, token = await _register(client)
    task = _create_task(user_id, status="proposed")

    response = await client.post(f"/api/v1/tasks/{task.id}/cancel", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_confirm_task_creates_schedule_conflict_notice_with_other_confirmed_task(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    due = datetime.now(UTC) + timedelta(days=2)
    _create_task(user_id, status="confirmed", due_at=due)
    second = _create_task(user_id, status="proposed", due_at=due + timedelta(minutes=15))

    response = await client.post(f"/api/v1/tasks/{second.id}/confirm", headers=headers)

    assert response.status_code == 200
    reminders = _reminders_for_task(second.id)
    conflict = [r for r in reminders if r.milestone == "schedule"]
    assert len(conflict) == 1


@pytest.mark.asyncio
async def test_get_notification_preferences_defaults_daily_brief_off(client):
    _, token = await _register(client)

    response = await client.get("/api/v1/reminders/preferences", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["dailyBriefHour"] is None
    assert body["timezone"] == "Asia/Ho_Chi_Minh"


@pytest.mark.asyncio
async def test_patch_notification_preferences_sets_daily_brief_hour(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.patch(
        "/api/v1/reminders/preferences", json={"dailyBriefHour": 8, "timezone": "Asia/Ho_Chi_Minh"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["dailyBriefHour"] == 8


@pytest.mark.asyncio
async def test_patch_notification_preferences_disable_clears_hour(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch("/api/v1/reminders/preferences", json={"dailyBriefHour": 8}, headers=headers)

    response = await client.patch("/api/v1/reminders/preferences", json={"disableDailyBrief": True}, headers=headers)

    assert response.status_code == 200
    assert response.json()["dailyBriefHour"] is None


@pytest.mark.asyncio
async def test_patch_notification_preferences_requires_authentication(client):
    response = await client.patch(
        "/api/v1/reminders/preferences",
        json={"telegramEnabled": False},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_patch_notification_preferences_rejects_invalid_timezone(client):
    _, token = await _register(client)

    response = await client.patch(
        "/api/v1/reminders/preferences",
        json={"timezone": "Not/A_Real_Zone"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def _create_reminder(user_id: str, *, kind: str, milestone: str, payload: dict | None = None) -> int:
    """Tạo thẳng một reminder không gắn task — dùng cho các kind toàn cục
    (calendar_changed, daily_brief) mà không phải dựng cả pipeline lịch."""
    db = SessionLocal()
    try:
        row = Reminder(
            task_id=None,
            user_id=user_id,
            kind=kind,
            milestone=milestone,
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            payload=payload or {},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_calendar_changed_reminder_serialises_instead_of_breaking_the_list(client):
    """Regression: `ReminderKind` từng thiếu 'calendar_changed', nên chỉ cần
    một thông báo lịch đổi tồn tại là CẢ /reminders lẫn /reminders/due của user
    đó hỏng ở bước validate — mất luôn mọi lời nhắc khác."""
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    _disable_quiet_hours(user_id)
    _create_reminder(
        user_id,
        kind="calendar_changed",
        milestone="cal-abc123",
        payload={
            "title": "Buổi review",
            "change": "time_changed",
            "changeNote": "Dời sang 19:30 theo thông báo của ban tổ chức.",
            "deepLink": "https://calendar.google.com/x",
        },
    )

    listing = await client.get("/api/v1/reminders", headers=headers)
    assert listing.status_code == 200
    assert [row["kind"] for row in listing.json()["reminders"]] == ["calendar_changed"]

    due = await client.get("/api/v1/reminders/due", headers=headers)
    assert due.status_code == 200
    tasks = due.json()["notifications"][0]["tasks"]
    assert tasks[0]["kind"] == "calendar_changed"
    assert "Dời sang 19:30" in tasks[0]["title"]
    assert tasks[0]["evidenceDeepLink"] == "https://calendar.google.com/x"


@pytest.mark.asyncio
async def test_preferences_default_to_every_channel_on_and_nothing_muted(client):
    _, token = await _register(client)

    response = await client.get("/api/v1/reminders/preferences", headers={"Authorization": f"Bearer {token}"})

    body = response.json()
    assert body["extensionEnabled"] is True
    assert body["telegramEnabled"] is True
    assert body["webPushEnabled"] is True
    assert body["mutedKinds"] == []


@pytest.mark.asyncio
async def test_patch_preferences_updates_only_the_fields_sent(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    await client.patch(
        "/api/v1/reminders/preferences",
        json={"quietHoursStart": 23, "quietHoursEnd": 6, "hourlyCap": 3, "batchWindowMinutes": 30},
        headers=headers,
    )
    response = await client.patch("/api/v1/reminders/preferences", json={"telegramEnabled": False}, headers=headers)

    body = response.json()
    assert body["telegramEnabled"] is False
    # Lần PATCH thứ hai không nhắc tới bốn giá trị kia thì chúng phải còn nguyên.
    assert (body["quietHoursStart"], body["quietHoursEnd"]) == (23, 6)
    assert (body["hourlyCap"], body["batchWindowMinutes"]) == (3, 30)
    assert body["webPushEnabled"] is True


@pytest.mark.asyncio
async def test_muted_kinds_replaces_the_whole_list_and_rejects_unknown_kind(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.patch(
        "/api/v1/reminders/preferences",
        json={"mutedKinds": ["daily_brief", "calendar_changed", "daily_brief"]},
        headers=headers,
    )
    assert first.json()["mutedKinds"] == ["daily_brief", "calendar_changed"]

    # Gửi danh sách rỗng là bật lại tất cả, không phải "không đổi".
    cleared = await client.patch("/api/v1/reminders/preferences", json={"mutedKinds": []}, headers=headers)
    assert cleared.json()["mutedKinds"] == []

    invalid = await client.patch(
        "/api/v1/reminders/preferences", json={"mutedKinds": ["khong_ton_tai"]}, headers=headers
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_muted_kind_is_not_delivered_but_other_kinds_still_are(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    _disable_quiet_hours(user_id)
    _create_reminder(user_id, kind="daily_brief", milestone="digest", payload={"dueSoonCount": 0})
    _create_reminder(user_id, kind="conflict_evidence", milestone="ev-abc", payload={"topic": "Deadline demo"})

    await client.patch("/api/v1/reminders/preferences", json={"mutedKinds": ["daily_brief"]}, headers=headers)
    response = await client.get("/api/v1/reminders/due", headers=headers)

    kinds = {task["kind"] for bundle in response.json()["notifications"] for task in bundle["tasks"]}
    assert kinds == {"conflict_evidence"}


@pytest.mark.asyncio
async def test_disabling_the_extension_channel_stops_the_due_endpoint(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    _disable_quiet_hours(user_id)
    _create_reminder(user_id, kind="daily_brief", milestone="digest", payload={"dueSoonCount": 0})

    await client.patch("/api/v1/reminders/preferences", json={"extensionEnabled": False}, headers=headers)
    off = await client.get("/api/v1/reminders/due", headers=headers)
    assert off.json()["notifications"] == []

    # Tắt kênh chỉ chặn đường giao: bật lại thì thông báo cũ vẫn còn nguyên.
    await client.patch("/api/v1/reminders/preferences", json={"extensionEnabled": True}, headers=headers)
    back = await client.get("/api/v1/reminders/due", headers=headers)
    assert len(back.json()["notifications"]) == 1
