"""Test luồng phát hiện task/sự kiện trùng nhau và gợi ý ưu tiên."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.db import SessionLocal
from src.models.calendar_event import CalendarEvent
from src.models.schedule_conflict import ScheduleConflict
from src.models.task import Task
from src.services import schedule_conflicts as service

WINDOW_START = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 8, 24, 0, 0, tzinfo=UTC)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _user_id() -> str:
    return f"user-conflict-{uuid.uuid4().hex[:12]}"


def _add_task(
    db,
    user_id: str,
    *,
    title: str = "Nộp báo cáo milestone 2",
    due_at: datetime | None = None,
    status: str = "confirmed",
    all_day: bool = False,
    ambiguous: bool = False,
    source_count: int = 2,
    signal_strength: float = 0.66,
    reminder_dismiss_count: int = 0,
    calendar_event_id: str | None = None,
) -> Task:
    task = Task(
        user_id=user_id,
        cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
        title=title,
        detail="",
        due_at=due_at or datetime(2026, 8, 18, 14, 0, tzinfo=UTC),
        all_day=all_day,
        ambiguous=ambiguous,
        status=status,
        source_count=source_count,
        signal_strength=signal_strength,
        reminder_dismiss_count=reminder_dismiss_count,
        calendar_event_id=calendar_event_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _add_event(
    db,
    user_id: str,
    *,
    title: str = "Mentor office hours",
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    all_day: bool = False,
    status: str = "active",
    event_id: str | None = None,
) -> CalendarEvent:
    starts_at = starts_at or datetime(2026, 8, 18, 14, 15, tzinfo=UTC)
    event = CalendarEvent(
        user_id=user_id,
        calendar_id="primary",
        event_id=event_id or f"evt-{uuid.uuid4().hex[:12]}",
        title=title,
        starts_at=starts_at,
        ends_at=ends_at if ends_at is not None else starts_at + timedelta(hours=1),
        all_day=all_day,
        status=status,
        deep_link="https://calendar.google.com/event?eid=abc",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _detect(db, user_id: str) -> list[ScheduleConflict]:
    return service.detect_conflicts(db, user_id, time_from=WINDOW_START, time_to=WINDOW_END)


def test_timed_task_overlapping_event_is_time_overlap(db):
    user_id = _user_id()
    _add_task(db, user_id, title="Nộp báo cáo milestone 2")
    _add_event(db, user_id, title="Mentor office hours")

    conflicts = _detect(db, user_id)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "time_overlap"
    # Task chiếm 14:00–14:30, sự kiện 14:15–15:15 -> chồng 15 phút.
    assert conflicts[0].overlap_minutes == 15


def test_long_event_started_before_candidate_buffer_is_still_detected(db):
    user_id = _user_id()
    _add_task(db, user_id, title="Nộp báo cáo milestone 2")
    _add_event(
        db,
        user_id,
        title="Khoá workshop dài ngày",
        starts_at=datetime(2026, 8, 15, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 18, 14, 30, tzinfo=UTC),
    )

    conflicts = _detect(db, user_id)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "time_overlap"
    assert conflicts[0].overlap_minutes == 30


def test_similar_title_and_close_start_is_same_item_not_overlap(db):
    user_id = _user_id()
    _add_task(db, user_id, title="Nộp báo cáo milestone 2")
    _add_event(db, user_id, title="Nộp báo cáo Milestone 2")

    conflicts = _detect(db, user_id)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "same_item"


def test_no_conflict_when_windows_do_not_touch(db):
    user_id = _user_id()
    _add_task(db, user_id, due_at=datetime(2026, 8, 18, 9, 0, tzinfo=UTC))
    _add_event(db, user_id, starts_at=datetime(2026, 8, 18, 14, 0, tzinfo=UTC))

    assert _detect(db, user_id) == []


def test_all_day_event_does_not_block_a_timed_task(db):
    user_id = _user_id()
    _add_task(db, user_id, title="Nộp báo cáo", due_at=datetime(2026, 8, 18, 14, 0, tzinfo=UTC))
    _add_event(
        db,
        user_id,
        title="Nghỉ lễ toàn trường",
        starts_at=datetime(2026, 8, 18, 0, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 19, 0, 0, tzinfo=UTC),
        all_day=True,
    )

    assert _detect(db, user_id) == []


def test_task_already_synced_to_that_event_is_not_a_conflict(db):
    user_id = _user_id()
    event = _add_event(db, user_id, title="Nộp báo cáo milestone 2")
    _add_task(db, user_id, title="Nộp báo cáo milestone 2", calendar_event_id=event.event_id)

    assert _detect(db, user_id) == []


def test_deleted_event_is_ignored(db):
    user_id = _user_id()
    _add_task(db, user_id)
    _add_event(db, user_id, status="stale")

    assert _detect(db, user_id) == []


def test_dismissed_task_is_ignored(db):
    user_id = _user_id()
    _add_task(db, user_id, status="dismissed")
    _add_event(db, user_id)

    assert _detect(db, user_id) == []


def test_rerunning_detect_does_not_duplicate_rows(db):
    user_id = _user_id()
    _add_task(db, user_id)
    _add_event(db, user_id)

    first = _detect(db, user_id)
    second = _detect(db, user_id)

    assert [row.id for row in first] == [row.id for row in second]
    assert len(service.list_conflicts(db, user_id)) == 1


def test_moving_the_deadline_supersedes_the_old_row(db):
    user_id = _user_id()
    task = _add_task(db, user_id)
    _add_event(db, user_id, starts_at=datetime(2026, 8, 18, 14, 15, tzinfo=UTC))
    old_row_id = _detect(db, user_id)[0].id

    # Hạn chót dời sang giữa sự kiện -> vẫn trùng, nhưng là một lần trùng khác.
    task.due_at = datetime(2026, 8, 18, 14, 30, tzinfo=UTC)
    db.commit()
    new_rows = _detect(db, user_id)

    assert len(new_rows) == 1
    assert new_rows[0].id != old_row_id
    old_row = db.get(ScheduleConflict, old_row_id)
    assert old_row.status == "superseded"


def test_open_row_goes_stale_when_conflict_disappears(db):
    user_id = _user_id()
    task = _add_task(db, user_id)
    _add_event(db, user_id)
    row_id = _detect(db, user_id)[0].id

    task.due_at = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)
    db.commit()

    assert _detect(db, user_id) == []
    assert db.get(ScheduleConflict, row_id).status == "stale"


def test_open_row_goes_stale_when_task_is_cancelled_outside_the_window(db):
    user_id = _user_id()
    task = _add_task(db, user_id)
    _add_event(db, user_id)
    row_id = _detect(db, user_id)[0].id

    task.status = "cancelled"
    db.commit()
    # Quét một tuần khác hẳn: task đã huỷ vẫn phải đóng được dòng treo lại.
    service.detect_conflicts(
        db,
        user_id,
        time_from=datetime(2026, 9, 1, tzinfo=UTC),
        time_to=datetime(2026, 9, 8, tzinfo=UTC),
    )

    assert db.get(ScheduleConflict, row_id).status == "stale"


def test_resolved_row_is_not_reopened_by_a_later_detect(db):
    user_id = _user_id()
    _add_task(db, user_id)
    _add_event(db, user_id)
    row = _detect(db, user_id)[0]
    service.resolve_conflict(db, row, "accept_both")

    assert _detect(db, user_id) == []
    assert db.get(ScheduleConflict, row.id).status == "resolved"


def test_conflicts_are_scoped_to_their_owner(db):
    owner, other = _user_id(), _user_id()
    _add_task(db, owner)
    _add_event(db, owner)
    _detect(db, owner)

    assert service.list_conflicts(db, other) == []


def test_suggestion_prefers_event_when_task_time_is_ambiguous(db):
    user_id = _user_id()
    _add_task(db, user_id, ambiguous=True, signal_strength=1.0)
    _add_event(db, user_id)

    row = _detect(db, user_id)[0]

    assert row.suggestion == "prioritize_event"
    assert row.suggestion_reasons == ["task_time_ambiguous"]


def test_suggestion_prefers_event_when_reminders_keep_being_dismissed(db):
    user_id = _user_id()
    _add_task(db, user_id, reminder_dismiss_count=2, signal_strength=1.0)
    _add_event(db, user_id)

    row = _detect(db, user_id)[0]

    assert row.suggestion == "prioritize_event"
    assert row.suggestion_reasons == ["task_repeatedly_dismissed"]


def test_suggestion_prefers_task_when_multiple_sources_confirm_the_deadline(db):
    user_id = _user_id()
    _add_task(db, user_id, status="confirmed", signal_strength=1.0)
    _add_event(db, user_id)

    row = _detect(db, user_id)[0]

    assert row.suggestion == "prioritize_task"
    assert row.suggestion_reasons == ["task_multi_source"]


def test_suggestion_abstains_when_evidence_is_thin(db):
    user_id = _user_id()
    _add_task(db, user_id, status="confirmed", source_count=1, signal_strength=0.33)
    _add_event(db, user_id)

    row = _detect(db, user_id)[0]

    assert row.suggestion == "undecided"
    assert row.suggestion_reasons == ["evidence_tie"]


def test_same_item_suggestion_prefers_the_event_for_a_proposed_task(db):
    user_id = _user_id()
    _add_task(db, user_id, title="Nộp báo cáo milestone 2", status="proposed")
    _add_event(db, user_id, title="Nộp báo cáo milestone 2")

    row = _detect(db, user_id)[0]

    assert row.conflict_type == "same_item"
    assert row.suggestion == "prioritize_event"
    assert row.suggestion_reasons == ["event_already_on_calendar"]


def test_resolving_same_item_towards_the_event_dismisses_the_duplicate_task(db):
    user_id = _user_id()
    task = _add_task(db, user_id, title="Nộp báo cáo milestone 2", status="proposed")
    event = _add_event(db, user_id, title="Nộp báo cáo milestone 2")
    row = _detect(db, user_id)[0]

    service.resolve_conflict(db, row, "prioritize_event")

    db.refresh(task)
    assert task.status == "dismissed"
    assert task.calendar_event_id == event.event_id
    # Bản trùng đã xử lý thì lần quét sau không được báo lại.
    assert _detect(db, user_id) == []


def test_resolving_same_item_towards_the_task_keeps_the_task_alive(db):
    user_id = _user_id()
    task = _add_task(db, user_id, title="Nộp báo cáo milestone 2", status="confirmed")
    event = _add_event(db, user_id, title="Nộp báo cáo milestone 2")
    row = _detect(db, user_id)[0]

    service.resolve_conflict(db, row, "prioritize_task")

    db.refresh(task)
    assert task.status == "confirmed"
    assert task.calendar_event_id == event.event_id


def test_resolving_time_overlap_never_touches_the_task(db):
    user_id = _user_id()
    task = _add_task(db, user_id, title="Nộp báo cáo milestone 2")
    _add_event(db, user_id, title="Mentor office hours")
    row = _detect(db, user_id)[0]

    service.resolve_conflict(db, row, "prioritize_event")

    db.refresh(task)
    assert task.status == "confirmed"
    assert task.calendar_event_id is None


def test_resolving_twice_is_rejected(db):
    user_id = _user_id()
    _add_task(db, user_id)
    _add_event(db, user_id)
    row = _detect(db, user_id)[0]
    service.resolve_conflict(db, row, "accept_both")

    with pytest.raises(ValueError):
        service.resolve_conflict(db, row, "prioritize_task")


def test_unknown_resolution_is_rejected(db):
    user_id = _user_id()
    _add_task(db, user_id)
    _add_event(db, user_id)
    row = _detect(db, user_id)[0]

    with pytest.raises(ValueError):
        service.resolve_conflict(db, row, "delete_event")


def test_detect_for_task_scans_around_its_own_due_date(db):
    user_id = _user_id()
    task = _add_task(db, user_id, due_at=datetime(2026, 12, 1, 14, 0, tzinfo=UTC))
    _add_event(db, user_id, starts_at=datetime(2026, 12, 1, 14, 15, tzinfo=UTC))

    conflicts = service.detect_for_task(db, task)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "time_overlap"


def test_detect_for_task_without_due_date_does_nothing(db):
    user_id = _user_id()
    task = _add_task(db, user_id)
    task.due_at = None
    db.commit()

    assert service.detect_for_task(db, task) == []
