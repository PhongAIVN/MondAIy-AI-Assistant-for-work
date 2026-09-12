"""Planner workspace: plan ngày/tuần có ràng buộc do người dùng đặt."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.calendar_event import CalendarEvent
from src.models.planner_preference import PlannerPreference
from src.models.program_event import ProgramEvent
from src.models.schemas import PlannerPreviousBlock
from src.models.task import Task
from src.models.user import User
from src.services.planner.schedule import DailyCadence, build_day_schedule


def _time(value: int) -> time:
    return time(value // 60, value % 60)


def get_or_create_preferences(db: Session, user_id: str) -> PlannerPreference:
    row = db.execute(select(PlannerPreference).where(PlannerPreference.user_id == user_id)).scalar_one_or_none()
    if row is None:
        row = PlannerPreference(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def validate_preferences(pref: PlannerPreference) -> None:
    # SQLAlchemy áp ``default`` khi INSERT, nên instance mới chưa flush có thể
    # còn None. Hàm thuần vẫn phải kiểm chứng được cho test/preview.
    workday_start = pref.workday_start_minute if pref.workday_start_minute is not None else 8 * 60
    lunch_start = pref.lunch_start_minute if pref.lunch_start_minute is not None else 12 * 60
    lunch_end = pref.lunch_end_minute if pref.lunch_end_minute is not None else 14 * 60
    workday_end = pref.workday_end_minute if pref.workday_end_minute is not None else 18 * 60
    bounds = (workday_start, lunch_start, lunch_end, workday_end)
    if not all(0 <= item < 24 * 60 for item in bounds) or not bounds[0] < bounds[1] < bounds[2] < bounds[3]:
        raise ValueError("Giờ làm việc phải tăng dần: bắt đầu < nghỉ trưa < kết thúc nghỉ < kết thúc ngày.")
    happy_enabled = True if pref.happy_time_enabled is None else pref.happy_time_enabled
    happy_start = pref.happy_time_start_minute if pref.happy_time_start_minute is not None else 16 * 60
    happy_end = pref.happy_time_end_minute if pref.happy_time_end_minute is not None else 17 * 60
    if happy_enabled and not (0 <= happy_start < happy_end <= 24 * 60):
        raise ValueError("Khoảng Happy Time không hợp lệ.")


def cadence_from_preference(pref: PlannerPreference) -> DailyCadence:
    validate_preferences(pref)
    workday_start = pref.workday_start_minute if pref.workday_start_minute is not None else 8 * 60
    lunch_start = pref.lunch_start_minute if pref.lunch_start_minute is not None else 12 * 60
    lunch_end = pref.lunch_end_minute if pref.lunch_end_minute is not None else 14 * 60
    workday_end = pref.workday_end_minute if pref.workday_end_minute is not None else 18 * 60
    # Scheduler hiện có dùng 3 nhịp. Khoảng sau giờ làm không được planner lấp đầy.
    return DailyCadence(
        workday_start=_time(workday_start),
        lunch_start=_time(lunch_start),
        afternoon_start=_time(lunch_end),
        # Giữ API cadence cũ (ba pha phải tăng nghiêm ngặt) nhưng biến pha tối
        # thành hai phút rỗng thực tế: workspace không lập lịch ngoài giờ làm.
        dinner_start=_time(workday_end - 2),
        evening_start=_time(workday_end - 1),
        day_end=_time(workday_end),
    )


def protected_windows(pref: PlannerPreference) -> tuple[tuple[time, time, str], ...]:
    if pref.happy_time_enabled is False:
        return ()
    start = pref.happy_time_start_minute if pref.happy_time_start_minute is not None else 16 * 60
    end = pref.happy_time_end_minute if pref.happy_time_end_minute is not None else 17 * 60
    return ((_time(start), _time(end), "Happy Time"),)


def _aware(value: datetime, timezone: ZoneInfo) -> datetime:
    """Chuẩn hoá datetime từ SQLite/DB trước khi so slot theo giờ địa phương."""
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone)


def _calendar_context(
    db: Session,
    *,
    user_id: str,
    window_start: datetime,
    window_end: datetime,
    timezone: ZoneInfo,
) -> list[dict]:
    """Lấy snapshot lịch hiện có; Planner tuyệt đối không refresh/ghi lịch bên ngoài."""
    events: list[dict] = []
    personal = list(
        db.execute(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.status == "active",
                CalendarEvent.starts_at < window_end,
                or_(CalendarEvent.ends_at.is_(None), CalendarEvent.ends_at > window_start),
            )
        ).scalars().all()
    )
    for event in personal:
        start = _aware(event.starts_at, timezone)
        # All-day events giữ trọn ngày làm việc; event thiếu end chỉ chặn 60 phút,
        # tránh biến một dữ liệu thiếu thành "bận cả ngày" không có căn cứ.
        if event.all_day:
            end = datetime.combine(start.date() + timedelta(days=1), time.min, tzinfo=timezone)
        else:
            end = _aware(event.ends_at, timezone) if event.ends_at else start + timedelta(hours=1)
        if end > start:
            events.append({
                "title": event.title or "Lịch cá nhân",
                "start": start,
                "end": end,
                "source": "personal_calendar",
                "all_day": bool(event.all_day),
                "synced_at": _aware(event.synced_at, timezone),
            })

    user = db.get(User, int(user_id)) if str(user_id).isdigit() else None
    if user is not None and user.program_access_level == "A":
        cohort = get_settings().program_cohort_slug
        program = list(
            db.execute(
                select(ProgramEvent).where(
                    ProgramEvent.cohort_slug == cohort,
                    ProgramEvent.visibility == "program",
                    ProgramEvent.status == "published",
                    ProgramEvent.starts_at < window_end,
                    or_(ProgramEvent.ends_at.is_(None), ProgramEvent.ends_at > window_start),
                )
            ).scalars().all()
        )
        for event in program:
            start = _aware(event.starts_at, timezone)
            end = _aware(event.ends_at, timezone) if event.ends_at else start + timedelta(hours=1)
            if end > start:
                events.append({
                    "title": event.title or "Lịch chương trình",
                    "start": start,
                    "end": end,
                    "source": "program_calendar",
                    "all_day": False,
                    "synced_at": event.source_updated_at and _aware(event.source_updated_at, timezone),
                })
    return sorted(events, key=lambda item: item["start"])


def _is_urgent_today(task: Task, local_today) -> bool:
    """Urgent ở đây có nghĩa mốc hạn hôm nay hoặc đã quá hạn, không đoán từ text."""
    if task.due_at is None:
        return False
    due = task.due_at if task.due_at.tzinfo is not None else task.due_at.replace(tzinfo=UTC)
    return due.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date() <= local_today


def _refresh_insights(
    *,
    tasks: list[Task],
    blocks: list,
    at_risk: list,
    known_task_ids: list[int],
    previous_blocks: list[PlannerPreviousBlock],
    local_today,
) -> tuple[dict, list[dict]]:
    """So sánh proposal mới/cũ để giải thích việc dời, không tự ghi lịch."""
    known = set(known_task_ids)
    open_ids = {task.id for task in tasks if task.id is not None}
    new_tasks = [task for task in tasks if task.id is not None and task.id not in known]
    urgent_new = [task for task in new_tasks if _is_urgent_today(task, local_today)]
    before = {block.task_id: block for block in previous_blocks if block.task_id in open_ids}
    after = {block.task_id: block for block in blocks}
    suggestions: list[dict] = []
    reason = (
        f"Nhường chỗ cho {len(urgent_new)} việc mới có hạn hôm nay/quá hạn."
        if urgent_new else
        "Tính lại theo deadline, mức ưu tiên, thời lượng và các khoảng bận hiện tại."
    )
    for task_id, old in before.items():
        current = after.get(task_id)
        if current is not None and (current.start != old.start or current.end != old.end):
            suggestions.append({
                "task_id": task_id,
                "title": current.title,
                "from_start": old.start,
                "from_end": old.end,
                "to_start": current.start,
                "to_end": current.end,
                "reason": reason,
            })
        elif current is None:
            title = next((task.title for task in tasks if task.id == task_id), "Task đang mở")
            suggestions.append({
                "task_id": task_id,
                "title": title,
                "from_start": old.start,
                "from_end": old.end,
                "to_start": None,
                "to_end": None,
                "reason": "Không còn khung phù hợp sau khi tôn trọng deadline và thời gian bận; cần bạn quyết định.",
            })
    return (
        {
            "new_task_count": len(new_tasks),
            "new_urgent_today_count": len(urgent_new),
            "reschedule_count": len(suggestions),
            "at_risk_count": len(at_risk),
        },
        suggestions,
    )


def build_workspace_plan(
    db: Session,
    user_id: str,
    *,
    start: datetime,
    days: int,
    known_task_ids: list[int] | None = None,
    previous_blocks: list[PlannerPreviousBlock] | None = None,
) -> dict:
    if days not in (1, 7):
        raise ValueError("Chỉ hỗ trợ kế hoạch 1 ngày hoặc 7 ngày.")
    pref = get_or_create_preferences(db, user_id)
    validate_preferences(pref)
    timezone = ZoneInfo("Asia/Ho_Chi_Minh")
    local_start = start.astimezone(timezone)
    tasks = list(
        db.execute(select(Task).where(Task.user_id == user_id, Task.status.in_(("proposed", "confirmed")))).scalars().all()
    )
    history = list(
        db.execute(
            select(Task).where(Task.user_id == user_id, Task.status == "completed", Task.actual_minutes.is_not(None)).limit(500)
        ).scalars().all()
    )
    cadence = cadence_from_preference(pref)
    window_start = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=days)
    calendar_blocks = _calendar_context(
        db,
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        timezone=timezone,
    )
    busy_windows = tuple((item["start"], item["end"], item["title"]) for item in calendar_blocks)
    blocks = []
    deferred = []
    remaining = tasks
    for offset in range(days):
        point = local_start + timedelta(days=offset)
        if offset:
            point = point.replace(hour=pref.workday_start_minute // 60, minute=pref.workday_start_minute % 60, second=0, microsecond=0)
        day = build_day_schedule(
            remaining,
            history,
            now=point,
            cadence=cadence,
            protected_windows=protected_windows(pref),
            busy_windows=busy_windows,
        )
        blocks.extend(day.blocks)
        deferred = list(day.deferred_to_tomorrow)
        scheduled_ids = {block.task_id for block in day.blocks}
        remaining = [task for task in remaining if task.id not in scheduled_ids]
    calendar_note = (
        f"Đã giữ {len(calendar_blocks)} khoảng bận từ lịch cá nhân/lịch chương trình đã đồng bộ."
        if calendar_blocks else
        "Chưa có khoảng bận lịch đã đồng bộ trong khung này; kết nối hoặc làm mới Lịch để kế hoạch sát thực tế hơn."
    )
    refresh, reschedule_suggestions = _refresh_insights(
        tasks=tasks,
        blocks=blocks,
        at_risk=deferred,
        known_task_ids=known_task_ids or [],
        previous_blocks=previous_blocks or [],
        local_today=local_start.date(),
    )
    notes = [
        "Đây là bản nháp: MondAIy không tự tạo sự kiện trên Google Calendar.",
        "Happy Time và nghỉ trưa là block bảo vệ; AI không xếp việc vào đó.",
        calendar_note,
    ]
    if refresh["new_urgent_today_count"]:
        notes.append(
            f"Phát hiện {refresh['new_urgent_today_count']} việc mới có hạn hôm nay/quá hạn; xem đề xuất dời lịch trước khi theo plan mới."
        )
    return {
        "generated_at": local_start,
        "days": days,
        "blocks": blocks,
        "at_risk": deferred,
        "calendar_blocks": calendar_blocks,
        "considered_task_ids": sorted(task.id for task in tasks if task.id is not None),
        "refresh": refresh,
        "reschedule_suggestions": reschedule_suggestions,
        "notes": notes,
    }
