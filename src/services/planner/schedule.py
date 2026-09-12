"""Xếp task vào nhịp ngày xác định, không gọi LLM (ADR-018 QĐ-1)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol

from src.services.planner.estimate import HistoricalTask, estimate_minutes
from src.services.planner.score import NEUTRAL_JOB_SIZE_MIN, rank_tasks


class SchedulableTask(Protocol):
    id: int | None
    user_id: str
    title: str
    due_at: datetime | None
    signal_strength: float
    source_count: int
    reminder_dismiss_count: int
    stated_priority: str | None
    estimate_low_min: int | None
    estimate_high_min: int | None
    energy: str | None
    detail: str
    expected_output: str | None
    acceptance_criteria: str | None
    context_input: str | None
    constraints: str | None
    execution_tool: str | None
    execution_method: str | None
    stakeholders: list[str] | None
    deliver_to: str | None


@dataclass(frozen=True)
class DailyCadence:
    workday_start: time
    lunch_start: time
    afternoon_start: time
    dinner_start: time
    evening_start: time
    day_end: time

    def __post_init__(self) -> None:
        boundaries = (
            self.workday_start,
            self.lunch_start,
            self.afternoon_start,
            self.dinner_start,
            self.evening_start,
            self.day_end,
        )
        if any(value.tzinfo is not None for value in boundaries):
            raise ValueError("Mốc nhịp ngày phải là giờ địa phương không kèm timezone")
        if any(left >= right for left, right in zip(boundaries, boundaries[1:])):
            raise ValueError("Các mốc nhịp ngày phải tăng nghiêm ngặt")


@dataclass(frozen=True)
class ScheduledBlock:
    task_id: int
    title: str
    start: datetime
    end: datetime
    minutes: int
    energy: str
    estimate_confidence: str
    why: str
    communication: str | None = None


@dataclass(frozen=True)
class DeferredTask:
    task_id: int
    title: str
    start: datetime | None
    end: datetime | None
    minutes: int
    energy: str
    estimate_confidence: str
    why: str


@dataclass(frozen=True)
class DaySchedule:
    now: datetime
    blocks: tuple[ScheduledBlock, ...]
    deferred_to_tomorrow: tuple[DeferredTask, ...]
    rest_reminder: str | None
    notes: tuple[str, ...]


@dataclass(frozen=True)
class _TaskPlan:
    task: SchedulableTask
    minutes: int
    energy: str
    estimate_confidence: str


@dataclass(frozen=True)
class _TaskView:
    """Chuẩn hoá timestamp DB trước khi đưa vào score.py."""

    id: int | None
    user_id: str
    title: str
    due_at: datetime | None
    signal_strength: float
    source_count: int
    reminder_dismiss_count: int
    stated_priority: str | None
    estimate_low_min: int | None
    estimate_high_min: int | None
    energy: str | None
    detail: str
    expected_output: str | None
    acceptance_criteria: str | None
    context_input: str | None
    constraints: str | None
    execution_tool: str | None
    execution_method: str | None
    stakeholders: list[str] | None
    deliver_to: str | None


@dataclass(frozen=True)
class _Slot:
    start: datetime
    end: datetime
    accepts_deep: bool
    label: str


def cadence_from_settings(settings) -> DailyCadence:
    """Đọc nhịp ngày từ Settings; scheduler không tự lấy default ngầm."""
    return DailyCadence(
        workday_start=settings.planner_workday_start,
        lunch_start=settings.planner_lunch_start,
        afternoon_start=settings.planner_afternoon_start,
        dinner_start=settings.planner_dinner_start,
        evening_start=settings.planner_evening_start,
        day_end=settings.planner_day_end,
    )


def _slots(
    day: date,
    timezone,
    cadence: DailyCadence,
    protected_windows: Sequence[tuple[time, time, str]] = (),
    busy_windows: Sequence[tuple[datetime, datetime, str]] = (),
) -> tuple[_Slot, ...]:
    """Trả các khoảng làm việc còn lại sau khi trừ các block người dùng bảo vệ.

    ``protected_windows`` là hợp đồng thời gian cứng của người dùng (ví dụ nghỉ
    trưa hoặc Happy Time), không phải gợi ý để bộ xếp lịch có thể ghi đè.
    """
    def at(value: time) -> datetime:
        return datetime.combine(day, value, tzinfo=timezone)

    base_slots = (
        _Slot(at(cadence.workday_start), at(cadence.lunch_start), True, "làm việc sâu buổi sáng"),
        _Slot(at(cadence.afternoon_start), at(cadence.dinner_start), True, "làm việc buổi chiều"),
        _Slot(at(cadence.evening_start), at(cadence.day_end), False, "việc nhẹ buổi tối"),
    )
    protected = [(at(start), at(end), label) for start, end, label in protected_windows if start < end]
    # Lịch cá nhân và lịch chương trình được chuyển thành mốc tuyệt đối. Chỉ
    # lấy phần giao với ngày đang xếp để event xuyên ngày cũng chặn đúng slot.
    protected.extend(
        (start.astimezone(timezone), end.astimezone(timezone), label)
        for start, end, label in busy_windows
        if start < end and start.astimezone(timezone).date() <= day <= end.astimezone(timezone).date()
    )
    available: list[_Slot] = []
    for slot in base_slots:
        fragments = [(slot.start, slot.end)]
        for blocked_start, blocked_end, _label in protected:
            next_fragments = []
            for start, end in fragments:
                if blocked_end <= start or blocked_start >= end:
                    next_fragments.append((start, end))
                    continue
                if start < blocked_start:
                    next_fragments.append((start, blocked_start))
                if blocked_end < end:
                    next_fragments.append((blocked_end, end))
            fragments = next_fragments
        available.extend(
            _Slot(start, end, slot.accepts_deep, slot.label)
            for start, end in fragments
            if start < end
        )
    return tuple(available)


def _task_view(task: SchedulableTask, timezone) -> _TaskView:
    due_at = task.due_at
    if due_at is not None:
        # SQLite bỏ timezone khỏi DateTime(timezone=True); dữ liệu Task lưu UTC.
        if due_at.tzinfo is None or due_at.utcoffset() is None:
            due_at = due_at.replace(tzinfo=UTC)
        due_at = due_at.astimezone(timezone)
    return _TaskView(
        id=task.id,
        user_id=task.user_id,
        title=task.title,
        due_at=due_at,
        signal_strength=task.signal_strength,
        source_count=task.source_count,
        reminder_dismiss_count=task.reminder_dismiss_count,
        stated_priority=task.stated_priority,
        estimate_low_min=task.estimate_low_min,
        estimate_high_min=task.estimate_high_min,
        energy=task.energy,
        detail=str(getattr(task, "detail", "") or ""),
        expected_output=getattr(task, "expected_output", None),
        acceptance_criteria=getattr(task, "acceptance_criteria", None),
        context_input=getattr(task, "context_input", None),
        constraints=getattr(task, "constraints", None),
        execution_tool=getattr(task, "execution_tool", None),
        execution_method=getattr(task, "execution_method", None),
        stakeholders=getattr(task, "stakeholders", None),
        deliver_to=getattr(task, "deliver_to", None),
    )


def _resolved_plan(task: SchedulableTask, estimate: tuple[int, int] | None) -> _TaskPlan:
    if task.id is None:
        raise ValueError("Task phải có id trước khi xếp lịch")
    if task.energy not in (None, "deep", "shallow"):
        raise ValueError(f"Task {task.id} có energy không hợp lệ: {task.energy!r}")

    if estimate is None:
        if not NEUTRAL_JOB_SIZE_MIN.is_integer():
            raise ValueError("NEUTRAL_JOB_SIZE_MIN phải là số phút nguyên")
        minutes = int(NEUTRAL_JOB_SIZE_MIN)
        confidence = "neutral_fallback"
        high = minutes
    else:
        low, high = estimate
        if low <= 0 or high <= 0 or low > high:
            raise ValueError(f"Task {task.id} có khoảng ước lượng không hợp lệ: {estimate!r}")
        # Dùng cận trên để lịch không hứa một khung ngắn hơn khoảng đã ước lượng.
        minutes = high
        confidence = "estimated"

    energy = task.energy or ("deep" if high > 45 else "shallow")
    return _TaskPlan(task=task, minutes=minutes, energy=energy, estimate_confidence=confidence)


def _why(plan: _TaskPlan, slot: _Slot) -> str:
    if slot.accepts_deep and plan.energy == "deep":
        reason = f"Việc deep được xếp vào khung {slot.label}."
    elif slot.accepts_deep:
        reason = f"Việc shallow được xếp vào khung {slot.label} còn trống."
    else:
        reason = "Việc shallow phù hợp với khung việc nhẹ buổi tối."
    if plan.estimate_confidence == "neutral_fallback":
        reason += f" Chưa ước lượng được; dùng mốc trung tính {plan.minutes} phút."
    brief_fields = (
        plan.task.expected_output,
        plan.task.acceptance_criteria,
        plan.task.context_input,
        plan.task.constraints,
        plan.task.execution_tool,
        plan.task.execution_method,
        plan.task.deliver_to,
    )
    brief_count = sum(bool(str(value or "").strip()) for value in brief_fields)
    if brief_count:
        reason += f" Dựa trên brief đã có {brief_count} phần cụ thể để chuẩn bị/làm việc."
    return reason


def _communication(task: SchedulableTask) -> str | None:
    """Nêu rõ cam kết trao đổi đã có trên task, không suy đoán người nhận."""
    deliver_to = str(getattr(task, "deliver_to", "") or "").strip()
    stakeholders = [str(item).strip() for item in (getattr(task, "stakeholders", None) or []) if str(item).strip()]
    if deliver_to:
        return f"Chuẩn bị/gửi đầu ra tới {deliver_to}."
    if stakeholders:
        return f"Cần trao đổi hoặc cập nhật với: {', '.join(stakeholders)}."
    return None


def _pack(
    plans: Sequence[_TaskPlan],
    slots: tuple[_Slot, ...],
    *,
    not_before: datetime,
) -> tuple[list[tuple[_TaskPlan, _Slot, datetime, datetime]], list[_TaskPlan]]:
    cursors = [max(slot.start, not_before) for slot in slots]
    packed: list[tuple[_TaskPlan, _Slot, datetime, datetime]] = []
    remaining: list[_TaskPlan] = []

    for plan in plans:
        placed = False
        duration = timedelta(minutes=plan.minutes)
        for index, slot in enumerate(slots):
            if plan.energy == "deep" and not slot.accepts_deep:
                continue
            start = cursors[index]
            end = start + duration
            if start < slot.start or end > slot.end:
                continue
            packed.append((plan, slot, start, end))
            cursors[index] = end
            placed = True
            break
        if not placed:
            remaining.append(plan)
    return packed, remaining


def build_day_schedule(
    tasks: Sequence[SchedulableTask],
    history: list[HistoricalTask],
    *,
    now: datetime,
    cadence: DailyCadence,
    protected_windows: Sequence[tuple[time, time, str]] = (),
    busy_windows: Sequence[tuple[datetime, datetime, str]] = (),
) -> DaySchedule:
    """Xếp toàn bộ task đã rank vào hôm nay, phần thừa dự kiến cho ngày mai."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now phải là datetime có timezone")

    task_views = [_task_view(task, now.tzinfo) for task in tasks]
    estimates = [estimate_minutes(task, history) for task in task_views]
    plans_by_id = {
        task.id: _resolved_plan(task, estimate)
        for task, estimate in zip(task_views, estimates)
    }
    ranked = rank_tasks(task_views, now, estimates)
    plans = [plans_by_id[task.id] for task, _score in ranked]

    # Việc tới hạn HÔM NAY được nhét trước, giữ nguyên thứ tự rank bên trong mỗi
    # nhóm. Không đụng tới WSJF — chỉ thêm một ràng buộc mà WSJF không biết tới.
    #
    # WSJF là giá trị chia khối lượng, nên một việc lớn hạn hôm nay luôn thua
    # nhiều việc nhỏ hạn tuần sau: đo thật với 1 báo cáo 90 phút hạn hôm nay và
    # 14 việc nhẹ 25 phút hạn ngày mai, báo cáo bị đẩy hết xuống và DỜI SANG MAI,
    # tức lỡ hạn. Với một bản kế hoạch trong ngày thì đó là hỏng, dù công thức
    # xếp hạng vẫn đúng như ADR-018 chốt.
    #
    # "Hôm nay" tính theo ngày địa phương của `now`, và quá hạn cũng vào nhóm này.
    today = now.date()

    def _due_today_or_overdue(plan: _TaskPlan) -> bool:
        due = plan.task.due_at
        return due is not None and due.astimezone(now.tzinfo).date() <= today

    plans = [p for p in plans if _due_today_or_overdue(p)] + [
        p for p in plans if not _due_today_or_overdue(p)
    ]

    today_slots = _slots(now.date(), now.tzinfo, cadence, protected_windows, busy_windows)
    packed_today, deferred = _pack(plans, today_slots, not_before=now)
    blocks = tuple(
        ScheduledBlock(
            task_id=plan.task.id,
            title=plan.task.title,
            start=start,
            end=end,
            minutes=plan.minutes,
            energy=plan.energy,
                estimate_confidence=plan.estimate_confidence,
                why=_why(plan, slot),
                communication=_communication(plan.task),
        )
        for plan, slot, start, end in sorted(packed_today, key=lambda item: item[2])
    )

    tomorrow = now.date() + timedelta(days=1)
    tomorrow_slots = _slots(tomorrow, now.tzinfo, cadence, protected_windows, busy_windows)
    if tomorrow_slots:
        tomorrow_start = tomorrow_slots[0].start
        packed_tomorrow, beyond_tomorrow = _pack(deferred, tomorrow_slots, not_before=tomorrow_start)
    else:
        # Người dùng có thể bảo vệ toàn bộ ngày. Không được lỗi 500 hoặc đánh
        # rơi task; tất cả phải hiện là chưa tìm được khung phù hợp.
        packed_tomorrow, beyond_tomorrow = [], list(deferred)
    tomorrow_by_id = {
        plan.task.id: (slot, start, end)
        for plan, slot, start, end in packed_tomorrow
    }
    beyond_ids = {plan.task.id for plan in beyond_tomorrow}
    deferred_items = []
    for plan in deferred:
        placement = tomorrow_by_id.get(plan.task.id)
        if placement is None:
            why = "Không còn khung tương thích trong ngày mai; task vẫn được giữ để lên kế hoạch tiếp."
            start = end = None
        else:
            slot, start, end = placement
            why = f"Hôm nay không còn đủ chỗ; dự kiến làm trong khung {slot.label} ngày mai."
            if plan.estimate_confidence == "neutral_fallback":
                why += f" Chưa ước lượng được; dùng mốc trung tính {plan.minutes} phút."
        deferred_items.append(
            DeferredTask(
                task_id=plan.task.id,
                title=plan.task.title,
                start=start,
                end=end,
                minutes=plan.minutes,
                energy=plan.energy,
                estimate_confidence=plan.estimate_confidence,
                why=why,
            )
        )

    has_evening = any(block.start.time() >= cadence.evening_start for block in blocks)
    rest_reminder = (
        "Bạn có việc nhẹ buổi tối; hãy dừng trước 22:00 và dành thời gian nghỉ ngơi."
        if has_evening
        else None
    )
    notes = []
    fallback_count = sum(plan.estimate_confidence == "neutral_fallback" for plan in plans)
    if fallback_count:
        notes.append(f"{fallback_count} việc chưa ước lượng được, đang dùng mốc trung tính.")
    if deferred:
        notes.append(f"{len(deferred)} việc không còn chỗ hôm nay và đã được dời sang ngày mai.")
    if beyond_ids:
        notes.append(f"{len(beyond_ids)} việc chưa có khung phù hợp trong ngày mai.")

    return DaySchedule(
        now=now,
        blocks=blocks,
        deferred_to_tomorrow=tuple(deferred_items),
        rest_reminder=rest_reminder,
        notes=tuple(notes),
    )
