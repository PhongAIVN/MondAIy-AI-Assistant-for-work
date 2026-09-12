"""4 loai thong bao moi chay chung 1 pipe voi task_due (xem test_reminders.py):
task_proposed, conflict_schedule, conflict_evidence, daily_brief."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.agents.briefing.evidence import Evidence, fuse_and_rank
from src.db import SessionLocal
from src.models.notification_preference import NotificationPreference
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.services import reminders as reminders_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _task(db, *, due_at, status="confirmed", user_id=None) -> Task:
    task = Task(
        user_id=user_id or f"user-{uuid.uuid4().hex[:12]}",
        cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
        title="Nộp báo cáo",
        detail="detail",
        status=status,
        due_at=due_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _evidence(db, task: Task, deep_link="https://mail.google.com/1") -> None:
    db.add(TaskEvidence(task_id=task.id, provider="gmail", evidence_quote="quote", deep_link=deep_link))
    db.commit()


def _no_quiet_hours_pref(db, user_id: str, **overrides) -> NotificationPreference:
    defaults = {"quiet_hours_start": 0, "quiet_hours_end": 0, "hourly_cap": 10, "batch_window_minutes": 15}
    defaults.update(overrides)
    pref = NotificationPreference(user_id=user_id, **defaults)
    db.add(pref)
    db.commit()
    return pref


class TestDetectScheduleConflicts:
    def test_creates_notice_for_two_confirmed_tasks_close_in_time(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        due = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        earlier = _task(db, due_at=due, user_id=user_id)
        later = _task(db, due_at=due + timedelta(minutes=20), user_id=user_id)

        created = reminders_service.detect_schedule_conflicts(db, later)

        assert len(created) == 1
        assert created[0].kind == "conflict_schedule"
        assert created[0].task_id == later.id
        assert created[0].related_task_id == earlier.id
        assert created[0].payload["otherTaskId"] == earlier.id

    def test_ignores_tasks_outside_window(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        due = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        _task(db, due_at=due, user_id=user_id)
        later = _task(db, due_at=due + timedelta(hours=3), user_id=user_id)

        created = reminders_service.detect_schedule_conflicts(db, later)

        assert created == []

    def test_dedupes_regardless_of_which_task_confirms_second(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        due = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        task_a = _task(db, due_at=due, user_id=user_id)
        task_b = _task(db, due_at=due + timedelta(minutes=10), user_id=user_id)

        first = reminders_service.detect_schedule_conflicts(db, task_b)
        second = reminders_service.detect_schedule_conflicts(db, task_a)

        assert len(first) == 1
        assert second == []

    def test_ignores_other_users_tasks(self, db):
        due = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
        _task(db, due_at=due, user_id=f"user-{uuid.uuid4().hex[:12]}")
        later = _task(db, due_at=due + timedelta(minutes=10), user_id=f"user-{uuid.uuid4().hex[:12]}")

        created = reminders_service.detect_schedule_conflicts(db, later)

        assert created == []


class TestGenerateEvidenceConflictNotices:
    def test_creates_notice_only_for_conflicting_cluster(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        items = [
            Evidence(evidence_id="1", source="discord", content="nop de xuat du an", importance=5, due_at=datetime(2026, 1, 28, tzinfo=UTC), topic="nop-de-xuat"),
            Evidence(evidence_id="2", source="canvas", content="nop de xuat du an", importance=5, due_at=datetime(2026, 1, 29, tzinfo=UTC), topic="nop-de-xuat"),
            Evidence(evidence_id="3", source="canvas", content="hoi thao tuan 3", importance=3, due_at=datetime(2026, 1, 20, tzinfo=UTC), topic="hoi-thao"),
        ]
        clusters = fuse_and_rank(items, now=datetime(2026, 1, 1, tzinfo=UTC))
        conflicting = [c for c in clusters if c.conflict]
        assert len(conflicting) == 1  # sanity check thuật toán fuse_and_rank

        created = reminders_service.generate_evidence_conflict_notices(db, user_id, conflicting)

        assert len(created) == 1
        assert created[0].kind == "conflict_evidence"
        assert created[0].task_id is None
        assert created[0].payload["topic"] == "nop-de-xuat"
        assert len(created[0].payload["items"]) == 2

    def test_dedupes_by_topic_when_still_scheduled(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        items = [
            Evidence(evidence_id="1", source="discord", content="x", importance=5, due_at=datetime(2026, 1, 28, tzinfo=UTC), topic="t"),
            Evidence(evidence_id="2", source="canvas", content="x", importance=5, due_at=datetime(2026, 1, 29, tzinfo=UTC), topic="t"),
        ]
        clusters = [c for c in fuse_and_rank(items, now=datetime(2026, 1, 1, tzinfo=UTC)) if c.conflict]

        first = reminders_service.generate_evidence_conflict_notices(db, user_id, clusters)
        second = reminders_service.generate_evidence_conflict_notices(db, user_id, clusters)

        assert len(first) == 1
        assert second == []


def _daily_brief_reminders(db, user_id: str) -> list[Reminder]:
    return db.query(Reminder).filter(Reminder.user_id == user_id, Reminder.kind == "daily_brief").all()


class TestEnqueueDueDailyBriefs:
    """enqueue_due_daily_briefs() quét TOÀN BỘ user trong DB (không lọc theo 1
    user) — DB test là Postgres dev dùng chung giữa các lần chạy, nên assert
    theo user_id cụ thể thay vì tin số đếm global `created` (số đó còn tính cả
    user khác nếu DB có sẵn dữ liệu từ lần chạy trước)."""

    def test_creates_digest_at_configured_local_hour(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        db.add(NotificationPreference(user_id=user_id, timezone="UTC", daily_brief_hour=8))
        db.commit()
        _task(db, due_at=datetime(2026, 1, 1, 20, tzinfo=UTC), status="confirmed", user_id=user_id)
        now = datetime(2026, 1, 1, 8, 5, tzinfo=UTC)

        reminders_service.enqueue_due_daily_briefs(db, now=now)

        reminders = _daily_brief_reminders(db, user_id)
        assert len(reminders) == 1
        assert reminders[0].payload["dueSoonCount"] == 1

    def test_skips_users_without_hour_set(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        db.add(NotificationPreference(user_id=user_id, timezone="UTC"))  # daily_brief_hour mac dinh None
        db.commit()

        reminders_service.enqueue_due_daily_briefs(db, now=datetime(2026, 1, 1, 8, 0, tzinfo=UTC))

        assert _daily_brief_reminders(db, user_id) == []

    def test_does_not_duplicate_within_same_local_day(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        db.add(NotificationPreference(user_id=user_id, timezone="UTC", daily_brief_hour=8))
        db.commit()

        reminders_service.enqueue_due_daily_briefs(db, now=datetime(2026, 1, 1, 8, 0, tzinfo=UTC))
        reminders_service.enqueue_due_daily_briefs(db, now=datetime(2026, 1, 1, 8, 4, tzinfo=UTC))

        assert len(_daily_brief_reminders(db, user_id)) == 1

    def test_wrong_hour_does_not_trigger(self, db):
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        db.add(NotificationPreference(user_id=user_id, timezone="UTC", daily_brief_hour=8))
        db.commit()

        reminders_service.enqueue_due_daily_briefs(db, now=datetime(2026, 1, 1, 9, 0, tzinfo=UTC))

        assert _daily_brief_reminders(db, user_id) == []


class TestGetDueNotificationsAcrossKinds:
    def test_includes_task_proposed_with_evidence(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id)
        task = _task(db, due_at=None, status="proposed", user_id=user_id)
        _evidence(db, task)
        db.add(Reminder(task_id=task.id, user_id=user_id, kind="task_proposed", milestone="proposed", scheduled_at=now - timedelta(minutes=1)))
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 1
        assert bundles[0].tasks[0].kind == "task_proposed"
        assert bundles[0].tasks[0].evidence_deep_link == "https://mail.google.com/1"

    def test_excludes_task_proposed_once_confirmed(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id)
        task = _task(db, due_at=None, status="confirmed", user_id=user_id)  # da confirm truoc khi thong bao duoc doc
        _evidence(db, task)
        db.add(Reminder(task_id=task.id, user_id=user_id, kind="task_proposed", milestone="proposed", scheduled_at=now - timedelta(minutes=1)))
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert bundles == []

    def test_includes_conflict_schedule_with_both_task_titles(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id)
        task_a = _task(db, due_at=now + timedelta(hours=1), user_id=user_id)
        task_b = _task(db, due_at=now + timedelta(hours=1, minutes=10), user_id=user_id)
        _evidence(db, task_b)
        db.add(
            Reminder(
                task_id=task_b.id, related_task_id=task_a.id, user_id=user_id, kind="conflict_schedule",
                milestone="schedule", scheduled_at=now - timedelta(minutes=1),
                payload={"otherTaskId": task_a.id, "otherTaskTitle": task_a.title, "otherDueAt": task_a.due_at.isoformat()},
            )
        )
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 1
        item = bundles[0].tasks[0]
        assert item.kind == "conflict_schedule"
        assert task_a.title in item.title
        assert task_b.title in item.title

    def test_includes_conflict_evidence_without_task(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id)
        db.add(
            Reminder(
                task_id=None, user_id=user_id, kind="conflict_evidence", milestone="ev-x",
                scheduled_at=now - timedelta(minutes=1), payload={"topic": "hạn nộp", "items": []},
            )
        )
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 1
        item = bundles[0].tasks[0]
        assert item.kind == "conflict_evidence"
        assert item.task_id is None
        assert "hạn nộp" in item.title

    def test_includes_daily_brief_without_task(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id)
        db.add(
            Reminder(
                task_id=None, user_id=user_id, kind="daily_brief", milestone="digest",
                scheduled_at=now - timedelta(minutes=1), payload={"dueSoonCount": 3, "proposedCount": 2, "dueSoonTasks": []},
            )
        )
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 1
        item = bundles[0].tasks[0]
        assert item.kind == "daily_brief"
        assert item.task_id is None
