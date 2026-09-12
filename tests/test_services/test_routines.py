import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.reminder import Reminder
from src.models.routine import Routine, RoutineRun
from src.models.user import User
from src.services import routines as routines_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _user(db) -> User:
    user = User(email=f"routines-{uuid.uuid4().hex[:12]}@example.com", display_name="Test User")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _routine(db, user_id: str, **overrides) -> Routine:
    defaults = {
        "name": "Tóm tắt email quan trọng",
        "instructions": "Đọc email hôm nay và tóm tắt việc cần trả lời.",
        "frequency": "daily",
        "hour": 8,
        "timezone": "UTC",
    }
    defaults.update(overrides)
    routine = routines_service.create_routine(db, user_id, **defaults)
    return routine


class TestRoutineCrud:
    def test_create_and_list_scoped_to_user(self, db):
        user = _user(db)
        other_user_id = str(_user(db).id)
        _routine(db, str(user.id))
        _routine(db, other_user_id)

        rows = routines_service.list_routines(db, str(user.id))

        assert len(rows) == 1
        assert rows[0].user_id == str(user.id)

    def test_update_only_changes_provided_fields(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id))

        updated = routines_service.update_routine(db, routine, hour=9)

        assert updated.hour == 9
        assert updated.name == routine.name  # không đổi vì không truyền

    def test_delete_removes_routine_and_its_runs(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id))
        db.add(RoutineRun(routine_id=routine.id, user_id=str(user.id), status="done"))
        db.commit()

        routines_service.delete_routine(db, routine)

        assert routines_service.get_routine(db, str(user.id), routine.id) is None
        assert db.query(RoutineRun).filter(RoutineRun.routine_id == routine.id).count() == 0


class TestMatchesSchedule:
    def test_daily_matches_only_at_configured_hour(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="daily", hour=8)

        assert routines_service._matches_schedule(routine, datetime(2026, 1, 1, 8, 30, tzinfo=UTC))
        assert not routines_service._matches_schedule(routine, datetime(2026, 1, 1, 9, 0, tzinfo=UTC))

    def test_weekly_requires_matching_day_of_week(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="weekly", hour=8, day_of_week=0)  # Thứ Hai

        monday = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
        tuesday = datetime(2026, 1, 6, 8, 0, tzinfo=UTC)
        assert routines_service._matches_schedule(routine, monday)
        assert not routines_service._matches_schedule(routine, tuesday)

    def test_every_other_day_uses_creation_date_as_anchor(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="every_other_day", hour=8)
        anchor = routine.created_at.replace(hour=8, minute=0, second=0, microsecond=0)
        next_day = anchor + timedelta(days=1)
        second_day = anchor + timedelta(days=2)

        assert routines_service._matches_schedule(routine, anchor)
        assert not routines_service._matches_schedule(routine, next_day)
        assert routines_service._matches_schedule(routine, second_day)

    def test_monthly_clamps_to_last_day_of_short_month(self, db):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="monthly", hour=8, day_of_month=31)

        # Tháng 2/2026 chỉ có 28 ngày -> ngày 31 kẹp về 28.
        assert routines_service._matches_schedule(routine, datetime(2026, 2, 28, 8, 0, tzinfo=UTC))
        assert not routines_service._matches_schedule(routine, datetime(2026, 2, 27, 8, 0, tzinfo=UTC))


class TestRunRoutine:
    @pytest.mark.asyncio
    async def test_writes_output_from_agent_response(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id))

        async def fake_ainvoke(state):
            assert state["query"] == routine.instructions
            return {"response": "Đã tóm tắt 2 email cần trả lời.", "metadata": {}}

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)

        run = await routines_service.run_routine(db, routine)

        assert run.status == "done"
        assert run.output_text == "Đã tóm tắt 2 email cần trả lời."
        assert run.finished_at is not None

    @pytest.mark.asyncio
    async def test_agent_error_is_captured_not_raised(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id))

        async def failing_ainvoke(state):
            raise RuntimeError("llm boom")

        monkeypatch.setattr(routines_service.agent, "ainvoke", failing_ainvoke)

        run = await routines_service.run_routine(db, routine)

        assert run.status == "error"
        assert "llm boom" in (run.error_message or "")

    @pytest.mark.asyncio
    async def test_notification_channels_follow_push_choice(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id), notify_push=True, notify_email=False)

        async def fake_ainvoke(state):
            return {"response": "ok", "metadata": {}}

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)
        await routines_service.run_routine(db, routine)
        reminder = db.query(Reminder).filter(Reminder.user_id == str(user.id)).one()
        assert reminder.payload["deliveryChannels"] == ["webpush"]

    @pytest.mark.asyncio
    async def test_no_push_does_not_create_deliverable_reminder(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id), notify_push=False, notify_email=True)

        async def fake_ainvoke(state):
            return {"response": "email-only", "metadata": {}}

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)
        await routines_service.run_routine(db, routine)
        reminder = db.query(Reminder).filter(Reminder.user_id == str(user.id)).one()
        assert reminder.payload["deliveryChannels"] == []


class TestEnqueueDueRoutines:
    @pytest.mark.asyncio
    async def test_runs_due_routine_and_stamps_last_run_date(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="daily", hour=8, timezone="UTC")

        async def fake_ainvoke(state):
            return {"response": "ok", "metadata": {}}

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)

        # DB test dùng chung engine giữa các lần chạy (giống test daily_brief) —
        # assert theo user_id cụ thể thay vì tin số đếm global.
        await routines_service.enqueue_due_routines(db, now=datetime(2026, 1, 1, 8, 5, tzinfo=UTC))

        db.refresh(routine)
        assert routine.last_run_date == "2026-01-01"
        runs = routines_service.list_routine_runs(db, str(user.id), routine.id)
        assert len(runs) == 1
        assert runs[0].status == "done"

    @pytest.mark.asyncio
    async def test_does_not_rerun_same_local_day(self, db, monkeypatch):
        user = _user(db)
        _routine(db, str(user.id), frequency="daily", hour=8, timezone="UTC")
        call_count = 0

        async def fake_ainvoke(state):
            nonlocal call_count
            call_count += 1
            return {"response": "ok", "metadata": {}}

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)

        await routines_service.enqueue_due_routines(db, now=datetime(2026, 1, 1, 8, 0, tzinfo=UTC))
        await routines_service.enqueue_due_routines(db, now=datetime(2026, 1, 1, 8, 40, tzinfo=UTC))

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_disabled_routine_never_runs(self, db, monkeypatch):
        user = _user(db)
        routine = _routine(db, str(user.id), frequency="daily", hour=8, timezone="UTC")
        routines_service.update_routine(db, routine, enabled=False)

        async def fake_ainvoke(state):
            raise AssertionError("không được gọi agent cho routine đã tắt")

        monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)

        ran = await routines_service.enqueue_due_routines(db, now=datetime(2026, 1, 1, 8, 0, tzinfo=UTC))

        assert ran == 0
