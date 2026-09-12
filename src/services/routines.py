"""Routines: automation do user tự đặt — lịch chạy + instructions tự do cho agent.

Chạy agent thật (`src/agents/graph.py`) với đúng bộ tool đã qua guardrail
(`src/guardrail/policy.py`) — chỉ tạo bản nháp local (Task proposed qua
draft_task/suggest_tasks/create_productivity_item), không ghi ra ứng dụng bên
ngoài nào (BR-13). Kết quả lưu vào `RoutineRun` để user đọc lại trong app;
không có bước ghi ngoài nào theo sau lúc này.

# TODO(OD): chỉ hỗ trợ lịch chạy (daily/weekly/monthly + giờ). Trigger theo sự
kiện (vd "khi có email mới") chưa làm — chưa có ADR/PRD định nghĩa "trigger"
nghĩa là gì và chưa có hạ tầng event-driven sau pipeline sync.
"""

from __future__ import annotations

import calendar
import logging
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.models.reminder import Reminder
from src.models.routine import Routine, RoutineRun
from src.services.memory_store import arecall, to_prompt_payload
from src.services.profile_memory import load_user_profile
from src.services.scope import apply_search_scope, reset_agent_scope

logger = logging.getLogger(__name__)

# Cùng số lượng long-term memory đã dùng khi gọi agent từ conversations.py.
_SO_MEMORY_DAI_HAN = 8


def create_routine(
    db: Session,
    user_id: str,
    *,
    name: str,
    instructions: str,
    frequency: str,
    interval_days: int = 2,
    hour: int,
    minute: int = 0,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    timezone: str = "Asia/Ho_Chi_Minh",
    notify_push: bool = True,
    notify_email: bool = False,
) -> Routine:
    routine = Routine(
        user_id=user_id,
        name=name,
        instructions=instructions,
        frequency=frequency,
        interval_days=interval_days,
        hour=hour,
        minute=minute,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        timezone=timezone,
        notify_push=notify_push,
        notify_email=notify_email,
    )
    db.add(routine)
    db.commit()
    db.refresh(routine)
    return routine


def list_routines(db: Session, user_id: str) -> list[Routine]:
    return list(
        db.execute(
            select(Routine).where(Routine.user_id == user_id).order_by(Routine.created_at.desc())
        ).scalars()
    )


def get_routine(db: Session, user_id: str, routine_id: int) -> Routine | None:
    return db.execute(
        select(Routine).where(Routine.id == routine_id, Routine.user_id == user_id)
    ).scalar_one_or_none()


def update_routine(db: Session, routine: Routine, **patch: object) -> Routine:
    """PATCH từng phần: field bỏ trống (None) nghĩa là giữ nguyên, không phải xoá."""
    for key, value in patch.items():
        if value is not None:
            setattr(routine, key, value)
    db.commit()
    db.refresh(routine)
    return routine


def delete_routine(db: Session, routine: Routine) -> None:
    db.execute(delete(RoutineRun).where(RoutineRun.routine_id == routine.id))
    db.delete(routine)
    db.commit()


def list_routine_runs(db: Session, user_id: str, routine_id: int, limit: int = 10) -> list[RoutineRun]:
    return list(
        db.execute(
            select(RoutineRun)
            .where(RoutineRun.routine_id == routine_id, RoutineRun.user_id == user_id)
            .order_by(RoutineRun.started_at.desc())
            .limit(limit)
        ).scalars()
    )


def list_recent_routine_runs(db: Session, user_id: str, limit: int = 12) -> list[tuple[RoutineRun, str]]:
    """Lấy các bản tóm tắt gần nhất của user, không chạy lại routine."""
    rows = db.execute(
        select(RoutineRun, Routine.name)
        .join(Routine, Routine.id == RoutineRun.routine_id)
        .where(RoutineRun.user_id == user_id)
        .order_by(RoutineRun.started_at.desc())
        .limit(limit)
    ).all()
    return [(run, name) for run, name in rows]


def _matches_schedule(routine: Routine, local_now: datetime) -> bool:
    """Routine có tới đúng lịch trong tick quét hiện tại hay không."""
    # Worker poll khong phai luc nao cung roi dung vao phut cau hinh; chay ngay
    # sau moc gio/phut va last_run_date se ngan chay lap trong cung ngay.
    if local_now.hour != routine.hour or local_now.minute < routine.minute:
        return False
    if routine.frequency == "daily":
        return True
    if routine.frequency == "every_other_day":
        created_at = routine.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        local_zone = ZoneInfo(routine.timezone)
        created_local = created_at.astimezone(local_zone).date()
        current_local = local_now.astimezone(local_zone).date()
        return (current_local - created_local).days % max(1, routine.interval_days) == 0
    if routine.frequency == "weekly":
        return routine.day_of_week is not None and local_now.weekday() == routine.day_of_week
    if routine.frequency == "monthly":
        if routine.day_of_month is None:
            return False
        # Tháng ngắn hơn ngày đã chọn (vd chọn 31 nhưng tháng 2) thì kẹp về
        # ngày cuối tháng, không lưu lại giá trị đã kẹp vào routine.day_of_month.
        last_day = calendar.monthrange(local_now.year, local_now.month)[1]
        target_day = min(routine.day_of_month, last_day)
        return local_now.day == target_day
    return False


async def run_routine(db: Session, routine: Routine) -> RoutineRun:
    """Chạy 1 routine ngay lập tức: gọi agent thật, ghi kết quả vào RoutineRun.

    Dùng đúng graph chat hiện có (`src/agents/graph.py`) với instructions của
    routine làm query — không tạo graph/tool mới, nên chỉ có thể tạo bản nháp
    local (Task proposed), không ghi ra ứng dụng bên ngoài. Lỗi không ném ra
    ngoài để caller (worker loop hoặc API run-now) không crash.
    """
    run = RoutineRun(routine_id=routine.id, user_id=routine.user_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        user_profile = load_user_profile(db, routine.user_id)
        long_term_memories = to_prompt_payload(
            await arecall(
                db,
                routine.user_id,
                routine.instructions,
                limit=_SO_MEMORY_DAI_HAN,
                include_candidates=False,
            )
        )
        apply_search_scope(
            routine.user_id,
            db,
            action_request_id=f"routine:{routine.id}:{uuid.uuid4()}",
            current_query=routine.instructions,
            pending_action=None,
        )
        try:
            result = await agent.ainvoke(
                {
                    "query": routine.instructions,
                    "history": [],
                    "conversation_summary": "",
                    "long_term_memories": long_term_memories,
                    "user_profile": user_profile,
                    "pending_productivity_action": None,
                }
            )
        finally:
            reset_agent_scope()

        run.status = "done"
        run.output_text = str(result.get("response") or "")
        run.output_json = (result.get("metadata") or {}).get("productivity_action")
        db.add(
            Reminder(
                user_id=routine.user_id,
                kind="daily_brief",
                milestone="briefing_ready",
                scheduled_at=run.finished_at or datetime.now(UTC),
                payload={
                    "routineId": routine.id,
                    "routineRunId": run.id,
                    "routineName": routine.name,
                    "question": routine.instructions,
                    "response": run.output_text,
                    # Email chưa có provider/outbox được Thái phê duyệt; chỉ
                    # Web Push là channel delivery thật trong lane này.
                    "deliveryChannels": ["webpush"] if routine.notify_push else [],
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Routine %s chạy lỗi", routine.id)
        run.status = "error"
        run.error_message = str(exc)
    finally:
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
    return run


async def enqueue_due_routines(db: Session, *, now: datetime | None = None) -> int:
    """Vòng quét routine tới hạn — cùng khuôn `enqueue_due_daily_briefs`.

    Khác daily_brief (chỉ tạo 1 Reminder rẻ), routine phải chạy agent thật nên
    ở đây CHẠY LUÔN, tuần tự trong vòng poll — chấp nhận block loop trong lúc
    gọi LLM, cùng mức "pilot scale" của các vòng poll khác trong repo. Không
    dùng lại hàng đợi Run/execute_run vì đó là pipeline sync riêng
    (PipelineState khác AgentState) — trộn vào không đáng cho quy mô hiện tại.
    """
    now = now or datetime.now(UTC)
    routines = db.execute(select(Routine).where(Routine.enabled.is_(True))).scalars().all()

    ran = 0
    for routine in routines:
        local_now = now.astimezone(ZoneInfo(routine.timezone))
        if not _matches_schedule(routine, local_now):
            continue
        today_str = local_now.date().isoformat()
        if routine.last_run_date == today_str:
            continue
        await run_routine(db, routine)
        routine.last_run_date = today_str
        db.commit()
        ran += 1
    return ran
