import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.notification_preference import NotificationPreference
from src.models.reminder import NotificationDelivery, Reminder
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


def _task(db, *, due_at: datetime | None, status: str = "confirmed", signal_strength: float = 0.0) -> Task:
    task = Task(
        user_id=f"user-{uuid.uuid4().hex[:12]}",
        cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
        title="Nộp báo cáo tuần",
        detail="detail",
        status=status,
        due_at=due_at,
        signal_strength=signal_strength,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _evidence(db, task: Task) -> TaskEvidence:
    row = TaskEvidence(task_id=task.id, provider="gmail", evidence_quote="quote", deep_link="https://mail.google.com/1")
    db.add(row)
    db.commit()
    return row


def _no_quiet_hours_pref(db, user_id: str, **overrides) -> NotificationPreference:
    defaults = {"quiet_hours_start": 0, "quiet_hours_end": 0, "hourly_cap": 5, "batch_window_minutes": 15}
    defaults.update(overrides)
    pref = NotificationPreference(user_id=user_id, **defaults)
    db.add(pref)
    db.commit()
    return pref


class TestGenerateDefaultReminders:
    def test_creates_1_day_30_min_and_at_time_milestones(self, db):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(days=3))

        created = reminders_service.generate_default_reminders(db, task, now=now)

        milestones = {r.milestone for r in created}
        assert milestones == {"1_day", "30_min", "at_time"}
        assert all(r.status == "scheduled" for r in created)

    def test_at_time_nhac_dung_moc_gio_khong_tru_lui(self, db):
        """Ca thật 28/08: "nhắn tôi 3h40" lúc 15:08.

        Trước khi có mốc này, người dùng xin nhắc lúc 15:40 nhưng chỉ nhận
        thông báo lúc 15:10 (mốc "30 phút trước") rồi im lặng đúng thời điểm
        họ cần. Hệ thống mô hình hoá hạn chót chứ chưa có báo thức.
        """
        now = datetime(2026, 8, 28, 8, 8, tzinfo=UTC)  # 15:08 giờ VN
        due = datetime(2026, 8, 28, 8, 40, tzinfo=UTC)  # 15:40 giờ VN
        task = _task(db, due_at=due)

        created = reminders_service.generate_default_reminders(db, task, now=now)

        theo_moc = {r.milestone: r.scheduled_at for r in created}
        assert "at_time" in theo_moc, "không có mốc nào bắn đúng giờ người dùng xin"
        assert theo_moc["at_time"].replace(tzinfo=UTC) == due
        assert "1_day" not in theo_moc, "mốc 1 ngày trước đã trôi qua, không được tạo"

    def test_qua_han_thi_khong_sinh_moc_nao(self, db):
        """`at_time` không được biến thành thông báo cho việc đã quá hạn."""
        now = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
        task = _task(db, due_at=now - timedelta(minutes=1))

        assert reminders_service.generate_default_reminders(db, task, now=now) == []

    def test_is_idempotent_on_second_call(self, db):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(days=3))

        reminders_service.generate_default_reminders(db, task, now=now)
        second = reminders_service.generate_default_reminders(db, task, now=now)

        assert second == []
        rows = db.query(Reminder).filter(Reminder.task_id == task.id).all()
        assert len(rows) == 3

    def test_skips_milestones_already_in_the_past(self, db):
        """Mốc cảnh báo sớm đã trôi qua thì bỏ — nhưng mốc đúng giờ thì không.

        Trước khi có `at_time`, task như thế này KHÔNG sinh lời nhắc nào: người
        đặt việc gấp lại là người ít được nhắc nhất.
        """
        now = datetime(2026, 1, 1, tzinfo=UTC)
        due = now + timedelta(minutes=10)  # cả 1_day lẫn 30_min đều đã trôi qua
        task = _task(db, due_at=due)

        created = reminders_service.generate_default_reminders(db, task, now=now)

        assert [r.milestone for r in created] == ["at_time"]
        assert created[0].scheduled_at.replace(tzinfo=UTC) == due

    def test_no_due_at_creates_nothing(self, db):
        task = _task(db, due_at=None)

        created = reminders_service.generate_default_reminders(db, task)

        assert created == []


class TestQuietHours:
    def test_overnight_window_flags_hour_inside(self):
        pref = NotificationPreference(user_id="u", quiet_hours_start=22, quiet_hours_end=7, timezone="UTC")
        assert reminders_service.is_quiet_hours(datetime(2026, 1, 1, 23, tzinfo=UTC), pref) is True
        assert reminders_service.is_quiet_hours(datetime(2026, 1, 1, 3, tzinfo=UTC), pref) is True
        assert reminders_service.is_quiet_hours(datetime(2026, 1, 1, 12, tzinfo=UTC), pref) is False

    def test_defer_to_active_start_pushes_forward_to_quiet_hours_end(self):
        pref = NotificationPreference(user_id="u", quiet_hours_start=22, quiet_hours_end=7, timezone="UTC")
        during_quiet = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)

        deferred = reminders_service.defer_to_active_start(during_quiet, pref)

        assert deferred == datetime(2026, 1, 2, 7, 0, tzinfo=UTC)

    def test_defer_is_noop_outside_quiet_hours(self):
        pref = NotificationPreference(user_id="u", quiet_hours_start=22, quiet_hours_end=7, timezone="UTC")
        at_noon = datetime(2026, 1, 1, 12, tzinfo=UTC)

        assert reminders_service.defer_to_active_start(at_noon, pref) == at_noon


class TestComputePriority:
    def test_closer_due_date_scores_higher(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        reminder = Reminder(kind="task_due", milestone="30_min")
        soon = Task(due_at=now + timedelta(hours=1), signal_strength=0.0, reminder_dismiss_count=0)
        far = Task(due_at=now + timedelta(days=10), signal_strength=0.0, reminder_dismiss_count=0)

        assert reminders_service.compute_priority(reminder, soon, now=now) > reminders_service.compute_priority(
            reminder, far, now=now
        )

    def test_dismiss_count_reduces_priority(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        reminder = Reminder(kind="task_due", milestone="30_min")
        clean = Task(due_at=now + timedelta(hours=1), signal_strength=0.0, reminder_dismiss_count=0)
        dismissed = Task(due_at=now + timedelta(hours=1), signal_strength=0.0, reminder_dismiss_count=3)

        assert reminders_service.compute_priority(reminder, clean, now=now) > reminders_service.compute_priority(
            reminder, dismissed, now=now
        )

    def test_conflict_evidence_and_daily_brief_use_flat_priority(self):
        now = datetime(2026, 1, 1, tzinfo=UTC)
        conflict = Reminder(kind="conflict_evidence", milestone="ev-x")
        digest = Reminder(kind="daily_brief", milestone="digest")

        assert reminders_service.compute_priority(conflict, None, now=now) == 800
        assert reminders_service.compute_priority(digest, None, now=now) == 200


class TestGetDueNotifications:
    def test_returns_bundle_with_evidence_link(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(minutes=30))
        _evidence(db, task)
        _no_quiet_hours_pref(db, task.user_id)
        reminder = Reminder(task_id=task.id, user_id=task.user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=1))
        db.add(reminder)
        db.commit()

        bundles = reminders_service.get_due_notifications(db, task.user_id, now=now)

        assert len(bundles) == 1
        assert bundles[0].reminder_ids == [reminder.id]
        assert bundles[0].tasks[0].evidence_deep_link == "https://mail.google.com/1"

    def test_excludes_reminder_without_evidence(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(minutes=30))  # không gọi _evidence
        _no_quiet_hours_pref(db, task.user_id)
        db.add(Reminder(task_id=task.id, user_id=task.user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=1)))
        db.commit()

        bundles = reminders_service.get_due_notifications(db, task.user_id, now=now)

        assert bundles == []

    def test_delivered_reminder_is_not_returned_again(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(minutes=30))
        _evidence(db, task)
        _no_quiet_hours_pref(db, task.user_id)
        reminder = Reminder(task_id=task.id, user_id=task.user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=1))
        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        reminders_service.record_deliveries(db, task.user_id, [reminder.id])
        bundles = reminders_service.get_due_notifications(db, task.user_id, now=now)

        assert bundles == []

    def test_reminders_in_same_window_are_merged_into_one_bundle(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id, batch_window_minutes=15)
        for _ in range(2):
            task = _task(db, due_at=now + timedelta(minutes=30))
            task.user_id = user_id
            db.commit()
            _evidence(db, task)
            db.add(Reminder(task_id=task.id, user_id=user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=1)))
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 1
        assert len(bundles[0].reminder_ids) == 2

    def test_hourly_cap_limits_number_of_bundles(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        user_id = f"user-{uuid.uuid4().hex[:12]}"
        _no_quiet_hours_pref(db, user_id, hourly_cap=2, batch_window_minutes=1)
        for minutes_ago in (1, 5, 9):  # 3 bucket khác nhau (window 1 phút), cap chỉ 2
            task = _task(db, due_at=now + timedelta(minutes=30))
            task.user_id = user_id
            db.commit()
            _evidence(db, task)
            db.add(
                Reminder(
                    task_id=task.id, user_id=user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=minutes_ago)
                )
            )
        db.commit()

        bundles = reminders_service.get_due_notifications(db, user_id, now=now)

        assert len(bundles) == 2

    def test_reminder_deferred_by_quiet_hours_is_not_due_yet(self, db):
        now = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)  # đang trong giờ yên lặng 22-7
        task = _task(db, due_at=now + timedelta(minutes=30))
        _evidence(db, task)
        db.add(NotificationPreference(user_id=task.user_id, quiet_hours_start=22, quiet_hours_end=7, timezone="UTC"))
        db.commit()
        db.add(Reminder(task_id=task.id, user_id=task.user_id, milestone="30_min", scheduled_at=now - timedelta(minutes=1)))
        db.commit()

        bundles = reminders_service.get_due_notifications(db, task.user_id, now=now)

        assert bundles == []


class TestSnoozeAndDismiss:
    def test_snooze_moves_scheduled_at_forward_and_clears_delivery(self, db):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        task = _task(db, due_at=now + timedelta(days=1))
        reminder = Reminder(task_id=task.id, user_id=task.user_id, milestone="1_day", scheduled_at=now - timedelta(minutes=1))
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        reminders_service.record_deliveries(db, task.user_id, [reminder.id])

        updated = reminders_service.snooze_reminder(db, reminder, minutes=15, now=now)

        # SQLite (dùng trong CI, không set DATABASE_URL) không giữ tzinfo qua
        # DateTime(timezone=True) như Postgres (dùng ở local dev) — so sánh bỏ
        # tzinfo cả 2 vế để test đúng bất kể chạy trên driver nào.
        assert updated.scheduled_at.replace(tzinfo=None) == (now + timedelta(minutes=15)).replace(tzinfo=None)
        assert updated.snooze_count == 1
        assert updated.status == "scheduled"
        assert db.query(NotificationDelivery).filter(NotificationDelivery.reminder_id == reminder.id).count() == 0

    def test_dismiss_cancels_reminder_and_increments_task_dismiss_count(self, db):
        task = _task(db, due_at=datetime(2026, 1, 2, tzinfo=UTC))
        reminder = Reminder(task_id=task.id, user_id=task.user_id, milestone="1_day", scheduled_at=datetime(2026, 1, 1, tzinfo=UTC))
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        assert task.reminder_dismiss_count == 0

        reminders_service.dismiss_reminder(db, reminder, reason="khong_can_nua")
        db.refresh(task)

        assert reminder.status == "cancelled"
        assert reminder.dismiss_reason == "khong_can_nua"
        assert task.status == "confirmed"  # ADR-007 mục 4: bỏ qua KHÔNG đụng task.status
        assert task.reminder_dismiss_count == 1

    def test_dismiss_rejects_unknown_reason(self, db):
        task = _task(db, due_at=datetime(2026, 1, 2, tzinfo=UTC))
        reminder = Reminder(task_id=task.id, user_id=task.user_id, milestone="1_day", scheduled_at=datetime(2026, 1, 1, tzinfo=UTC))
        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        with pytest.raises(ValueError, match="Lý do bỏ qua không hợp lệ"):
            reminders_service.dismiss_reminder(db, reminder, reason="ly-do-la")


class TestCancelPendingReminders:
    def test_cancels_all_scheduled_reminders_for_task(self, db):
        task = _task(db, due_at=datetime(2026, 1, 3, tzinfo=UTC))
        r1 = Reminder(task_id=task.id, user_id=task.user_id, milestone="1_day", scheduled_at=datetime(2026, 1, 2, tzinfo=UTC))
        r2 = Reminder(task_id=task.id, user_id=task.user_id, milestone="30_min", scheduled_at=datetime(2026, 1, 3, tzinfo=UTC))
        db.add_all([r1, r2])
        db.commit()

        reminders_service.cancel_pending_reminders(db, task.id)
        db.refresh(r1)
        db.refresh(r2)

        assert r1.status == "cancelled"
        assert r2.status == "cancelled"
        assert r1.dismiss_reason == "task_resolved"
