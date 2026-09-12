import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.config import get_settings
from src.connectors.calendar import CalendarAPIError, CalendarConnector, build_authuser_link
from src.db import get_db
from src.models.calendar_handoff import CalendarHandoff
from src.models.schemas import (
    CalendarEventListResponse,
    CalendarEventResponse,
    CalendarHandoffResponse,
    CalendarInfoResponse,
    CalendarSyncResponse,
    DayScheduleResponse,
    PageExtractionSuggestionItem,
    PageExtractionSummaryRequest,
    PageExtractionSummaryResponse,
    TaskBreakdownItem,
    TaskBreakdownResponse,
    TaskCompletionRequest,
    TaskEvidenceResponse,
    TaskFromSuggestionRequest,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.telemetry import AuditEvent
from src.services import calendar_tools
from src.services import reminders as reminders_service
from src.services import schedule_conflicts as schedule_conflicts_service
from src.services.calendar_handoff import build_google_calendar_url, build_ics
from src.services.connections import preferred_connection
from src.services.page_extraction import summarize_page_extraction
from src.services.task_breakdown import (
    TaskBreakdownError,
    TaskBreakdownUnavailableError,
    build_task_breakdown_from_db,
)
from src.services.task_dedup import acquire_user_lock, candidate_fingerprint, find_duplicate_task
from src.services.task_retention import purge_expired_completed_tasks
from src.services.telemetry import emit_audit
from src.services.tier_a_feed import (
    FEED_CALENDAR_ID,
    FEED_CALENDAR_NAME,
    pending_feed_events,
    should_sync_now,
    sync_tier_a_calendar,
    user_has_tier_a_access,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])
_MAX_CALENDAR_WINDOW = timedelta(days=42)
# ADR-021: trần cho thời lượng SUY RA từ started_at. Quá mốc này gần như chắc
# chắn là người dùng bấm "bắt đầu" rồi bỏ đó, không phải làm liên tục 12 tiếng.
# Ghi một con số như vậy vào actual_minutes sẽ đầu độc reference class lâu dài.
_MAX_INFERRED_WORK_MINUTES = 8 * 60
_CALENDAR_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}


def _to_response(db: Session, row: Task) -> TaskResponse:
    def as_utc(value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    evidence_rows = db.execute(select(TaskEvidence).where(TaskEvidence.task_id == row.id)).scalars().all()
    evidence = [TaskEvidenceResponse.model_validate(e, from_attributes=True) for e in evidence_rows]
    return TaskResponse.model_validate(row, from_attributes=True).model_copy(
        update={
            "due_at": as_utc(row.due_at),
            "created_at": as_utc(row.created_at),
            "completed_at": as_utc(row.completed_at),
            "updated_at": as_utc(row.updated_at),
            "evidence": evidence,
        }
    )


@router.get("", response_model=TaskListResponse)
@limiter.limit("60/minute")
def list_tasks(
    request: Request,
    status: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    purge_expired_completed_tasks(db, user_id)
    stmt = select(Task).where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.created_at.desc())
    rows = db.execute(stmt).scalars().all()
    return TaskListResponse(tasks=[_to_response(db, row) for row in rows])


@router.get("/calendar-events", response_model=CalendarEventListResponse)
@limiter.limit("20/minute")
async def list_calendar_events(
    request: Request,
    background_tasks: BackgroundTasks,
    time_from: datetime = Query(alias="timeFrom"),
    time_to: datetime = Query(alias="timeTo"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarEventListResponse:
    """Load a bounded window from every visible calendar for the week view.

    User tier A (được grant scope tier A) còn tự "cài" lịch chương trình:
    sync feed ICS chạy nền sau response này (feed → mondaiy → Google), phần
    sự kiện chưa kịp lên Google được merge thẳng vào kết quả để lưới lịch
    thấy ngay mà không nhân bản.
    """
    if time_from.tzinfo is None or time_to.tzinfo is None:
        raise HTTPException(status_code=422, detail="timeFrom và timeTo phải có múi giờ.")
    if time_from >= time_to:
        raise HTTPException(status_code=422, detail="timeFrom phải sớm hơn timeTo.")
    if time_to - time_from > _MAX_CALENDAR_WINDOW:
        raise HTTPException(status_code=422, detail="Chỉ được tải tối đa 42 ngày lịch mỗi lần.")

    try:
        result = await calendar_tools.search_calendar_events(
            db,
            user_id,
            time_from,
            time_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    def _aware(value: datetime) -> datetime:
        # SQLite/test fixture trả naive datetime; Postgres trả aware. So sánh
        # với cửa sổ truy vấn luôn aware nên phải chuẩn hoá trước (cùng luật
        # với task_tool._format_due).
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    feed_events: list[CalendarEventResponse] = []
    if get_settings().tier_a_calendar_feed_url and user_has_tier_a_access(db, user_id):
        for row in pending_feed_events(db, user_id):
            row_start = _aware(row.starts_at)
            row_end = _aware(row.ends_at or row.starts_at)
            if row_start >= time_to or row_end < time_from:
                continue
            feed_events.append(
                CalendarEventResponse(
                    id=row.event_id,
                    title=row.title,
                    # Response chuẩn của endpoint là chuỗi ISO (đường Google
                    # cũng trả string) — giữ đúng contract cho FE.
                    start_at=row_start.isoformat(),
                    end_at=row_end.isoformat() if row.ends_at else None,
                    all_day=row.all_day,
                    status="confirmed",
                    calendar_id=FEED_CALENDAR_ID,
                    calendar_name=FEED_CALENDAR_NAME,
                    deep_link=row.deep_link,
                )
            )
        if should_sync_now(user_id):
            background_tasks.add_task(_run_tier_a_sync_in_background, user_id)

    return CalendarEventListResponse(
        calendars=[CalendarInfoResponse(**calendar) for calendar in result["calendars"]]
        + ([CalendarInfoResponse(id=FEED_CALENDAR_ID, name=FEED_CALENDAR_NAME)] if feed_events else []),
        events=[
            CalendarEventResponse(
                id=event["id"],
                title=event["title"],
                start_at=event["start_at"],
                end_at=event.get("end_at"),
                all_day=event.get("all_day", False),
                status=event.get("status", "confirmed"),
                calendar_id=event["source_id"],
                calendar_name=event.get("calendar_name", event["source_id"]),
                deep_link=event.get("deep_link"),
            )
            for event in result["events"]
        ]
        + feed_events,
    )


def _run_tier_a_sync_in_background(user_id: str) -> None:
    """Sync feed tier A sau khi response đã trả về.

    Không dùng lại Session của request (đã đóng lúc task chạy) — tự mở phiên
    riêng và nuốt mọi exception: lỗi nền chỉ ghi log, không được làm đỏ request
    đã gửi cho người dùng.
    """
    import asyncio

    from src.db import SessionLocal

    db = SessionLocal()
    try:
        asyncio.run(sync_tier_a_calendar(db, user_id))
    except Exception:  # noqa: BLE001 - nền không được làm sập request
        logger.warning("Tier-A calendar sync nền lỗi cho %s", user_id, exc_info=True)
    finally:
        db.close()


def _get_owned_task(db: Session, task_id: int, user_id: str) -> Task:
    row = db.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy task.")
    return row


@router.post("/from-suggestion", response_model=TaskResponse, status_code=201)
@limiter.limit("20/minute")
def create_task_from_suggestion(
    request: Request,
    payload: TaskFromSuggestionRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Xác nhận một thẻ; gộp vào task tương tự thay vì tạo bản sao."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Tiêu đề task không được để trống.")
    detail = payload.detail.strip()
    due_at = payload.due_at.astimezone(UTC) if payload.due_at is not None else None
    source = payload.source.strip() or "suggestion"

    # Đây là điểm ghi chung của chat, ảnh, import tệp và Google source. Khoá
    # theo user giúp hai lần bấm gần nhau không cùng tạo hai task trùng.
    acquire_user_lock(db, user_id)
    decision = find_duplicate_task(
        db,
        user_id=user_id,
        title=title,
        detail=detail,
        due_at=due_at,
        all_day=payload.all_day,
    )
    merged = decision.task is not None
    if merged:
        row = decision.task
        assert row is not None
        fingerprint = candidate_fingerprint(title, detail, due_at) if due_at is not None else ""
        prior_merges = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "task_deduplicated",
                AuditEvent.object_type == "task",
                AuditEvent.object_id == str(row.id),
            )
        ).all()
        already_recorded = any(
            (event.details or {}).get("incoming_fingerprint") == fingerprint
            for event in prior_merges
        )
        if not already_recorded:
            row.source_count = int(row.source_count or 0) + 1
            row.updated_at = datetime.now(UTC)
            db.add(
                TaskEvidence(
                    task_id=row.id,
                    provider=source,
                    evidence_quote=detail or title,
                    deep_link="",
                )
            )
            settings = get_settings()
            emit_audit(
                db,
                "task_deduplicated",
                "task",
                str(row.id),
                actor_type="user",
                actor_id=user_id,
                version_label="task-dedup-v1",
                layer=decision.layer,
                similarity_score=round(float(decision.similarity_score or 0.0), 6),
                incoming_fingerprint=fingerprint,
                due_proximity_hours=settings.task_dedup_due_proximity_hours,
                fuzzy_threshold=settings.task_dedup_fuzzy_threshold,
                semantic_threshold=settings.task_dedup_semantic_threshold,
                embedding_model=settings.task_dedup_embedding_model,
            )
    else:
        digest = sha256(f"{user_id}:{uuid4()}:{title}".encode()).hexdigest()[:58]
        row = Task(
            user_id=user_id,
            cluster_key=f"agent-{digest}",
            title=title,
            detail=detail,
            due_at=due_at,
            all_day=payload.all_day,
            assignee=payload.assignee.strip() if payload.assignee else None,
            status="proposed",
            source_count=0,
            signal_strength=0.0,
            expected_output=payload.expected_output,
            acceptance_criteria=payload.acceptance_criteria,
            context_input=payload.context_input,
            constraints=payload.constraints,
            execution_tool=payload.execution_tool,
            execution_method=payload.execution_method,
            stated_priority=payload.stated_priority,
            stakeholders=payload.stakeholders if payload.stakeholders is not None else [],
            deliver_to=payload.deliver_to,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(db, row).model_copy(
        update={"deduplicated": merged, "dedup_layer": decision.layer if merged else None}
    )


@router.post("/summarize-page-extraction", response_model=PageExtractionSummaryResponse)
@limiter.limit("20/minute")
async def summarize_page_extraction_endpoint(
    request: Request,
    payload: PageExtractionSummaryRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PageExtractionSummaryResponse:
    """Tab "Lấy dữ liệu" của extension: xử lý LLM một lượt trên toàn đoạn (xem
    src/services/page_extraction.py — có đọc user_profile/long_term_memories
    để điền bối cảnh mà text không nói rõ) thành một DANH SÁCH suggestion, mỗi
    việc-cần-làm là một item riêng, kèm due_at khi resolve_due_at() parse chắc
    chắn được thời hạn. KHÔNG tạo task ở đây — người dùng xem list trong panel
    rồi bấm lưu từng cái thật qua POST /tasks/from-suggestion, tái dùng đúng
    cơ chế Task hiện có thay vì tạo pipeline lưu trữ riêng."""
    summaries = await summarize_page_extraction(
        payload.url, payload.page_title, payload.text, db, user_id, payload.source_context
    )
    return PageExtractionSummaryResponse(
        suggestions=[
            PageExtractionSuggestionItem(
                title=s.title.strip(),
                detail=s.detail.strip(),
                due_at=s.due_at,
                source_url=s.source_url,
                source_label=s.source_label,
                expected_output=s.expected_output,
                constraint=s.constraint,
                execution_steps=s.execution_steps,
                execution_tool=s.execution_tool,
                execution_method=s.execution_method,
                priority=s.priority,
                assignee=s.assignee,
                stakeholders=s.stakeholders,
                deliver_to=s.deliver_to,
            )
            for s in summaries
        ]
    )


@router.post("/breakdown", response_model=TaskBreakdownResponse)
@limiter.limit("10/minute")
async def breakdown_tasks(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskBreakdownResponse:
    """Kế hoạch hôm nay cho toàn bộ việc còn mở: thứ tự ưu tiên, việc nào cần
    tách bước, context chuẩn bị và prompt copy-paste sang AI khác. Chỉ đọc,
    không tạo hay sửa task nào."""
    try:
        plan = await build_task_breakdown_from_db(db, user_id)
    except TaskBreakdownUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TaskBreakdownError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TaskBreakdownResponse(
        generated_at=plan["generated_at"],
        summary=plan["summary"],
        items=[TaskBreakdownItem.model_validate(item) for item in plan["items"]],
        schedule=DayScheduleResponse.model_validate(plan["schedule"], from_attributes=True),
    )


@router.get("/{task_id}", response_model=TaskResponse)
@limiter.limit("60/minute")
def get_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    row = _get_owned_task(db, task_id, user_id)
    return _to_response(db, row)


@router.patch("/{task_id}", response_model=TaskResponse)
@limiter.limit("30/minute")
def update_task(
    request: Request,
    task_id: int,
    payload: TaskUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Let the owner refine a proposed or auto-confirmed task.

    Từ khi agent tự xác nhận việc gom (2026-08-22), task sinh ra đã là
    confirmed nên cửa sổ "chỉnh trước khi duyệt" không còn: cho sửa cả task
    confirmed đang mở. Đổi hạn trên task confirmed phải dời lại mốc nhắc
    task_due theo hạn mới, không thì vẫn nhắc theo giờ cũ.
    """
    row = _get_owned_task(db, task_id, user_id)
    if row.status not in {"proposed", "confirmed"}:
        raise HTTPException(
            status_code=409,
            detail=f"Task đang ở trạng thái '{row.status}', chỉ chỉnh được task còn mở.",
        )
    due_changed = False
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.detail is not None:
        row.detail = payload.detail.strip()
    if payload.due_at is not None:
        new_due = payload.due_at.astimezone(UTC)
        due_changed = row.due_at != new_due
        row.due_at = new_due
    if payload.all_day is not None:
        row.all_day = payload.all_day
    db.commit()
    db.refresh(row)
    if row.status == "confirmed" and due_changed:
        reminders_service.reschedule_due_reminders(db, row)
    return _to_response(db, row)


def _as_utc(moment: datetime) -> datetime:
    """SQLite trả datetime naive; Postgres trả aware. Chuẩn hoá trước khi trừ."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _transition(
    db: Session,
    task_id: int,
    user_id: str,
    new_status: str,
    *,
    allowed_from: set[str],
    actual_minutes: int | None = None,
) -> Task:
    row = _get_owned_task(db, task_id, user_id)
    if row.status not in allowed_from:
        raise HTTPException(
            status_code=409,
            detail=f"Task đang ở trạng thái '{row.status}', chỉ chuyển được từ {sorted(allowed_from)}.",
        )
    row.status = new_status
    row.completed_at = datetime.now(UTC) if new_status == "completed" else None
    # Đóng/mở đồng hồ lưu giữ ngay tại chỗ đổi trạng thái, để không có đường nào
    # vào "cancelled" mà quên đóng dấu thời gian — task như vậy sẽ nằm trong
    # thùng rác vĩnh viễn vì job dọn không thấy mốc nào để tính hạn.
    row.cancelled_at = datetime.now(UTC) if new_status == "cancelled" else None
    if new_status == "completed":
        if actual_minutes is not None:
            row.actual_minutes = actual_minutes
        elif row.started_at is not None and row.actual_minutes is None:
            # ADR-021: suy thời lượng từ mốc bắt đầu ĐÃ XÁC NHẬN, chỉ khi người
            # dùng không tự khai. Đây là cách duy nhất hôm nay thu được
            # actual_minutes: production có 17 task completed và 0 task có
            # actual_minutes — hộp thoại hỏi tay cho phép bỏ qua, và ai cũng bỏ qua.
            #
            # KHÔNG suy khi thiếu started_at. Lấy created_at làm mốc bắt đầu sẽ
            # cho ra những khoảng hàng ngày trời, và reference class sẽ học theo
            # chúng — một con số bịa còn tệ hơn không có số nào.
            elapsed = (datetime.now(UTC) - _as_utc(row.started_at)).total_seconds() / 60
            if 0 < elapsed <= _MAX_INFERRED_WORK_MINUTES:
                row.actual_minutes = int(round(elapsed))
    db.commit()
    db.refresh(row)
    return row


@router.post("/{task_id}/confirm", response_model=TaskResponse)
@limiter.limit("30/minute")
def confirm_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    row = _transition(db, task_id, user_id, "confirmed", allowed_from={"proposed"})
    # FR-090: task confirmed có due_at thì sinh mốc nhắc mặc định ngay — nhắc
    # việc không phụ thuộc thao tác Sync lịch riêng (calendar-sync).
    reminders_service.generate_default_reminders(db, row)
    # 2 task confirmed trùng/gần giờ nhau -> báo conflict ngay lúc task thứ 2
    # được confirm, không đợi vòng quét nền nào.
    reminders_service.detect_schedule_conflicts(db, row)
    # Quét trùng ngay lúc xác nhận: đây là thời điểm duy nhất chắc chắn người
    # dùng đang nhìn task này, nên phát hiện trùng giờ ở đây kịp cho họ quyết
    # trước khi đi sync lịch. Chỉ đọc bộ nhớ đệm lịch nên không gọi Google.
    schedule_conflicts_service.detect_for_task(db, row)
    return _to_response(db, row)


@router.post("/{task_id}/dismiss", response_model=TaskResponse)
@limiter.limit("30/minute")
def dismiss_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    row = _transition(db, task_id, user_id, "dismissed", allowed_from={"proposed"})
    return _to_response(db, row)


@router.post("/{task_id}/complete", response_model=TaskResponse)
@limiter.limit("30/minute")
def complete_task(
    request: Request,
    task_id: int,
    payload: TaskCompletionRequest | None = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """ADR-007 mục 4: 'Đã làm' đổi task.status, vào tử số PRD §4.2. Tách hẳn
    khỏi bỏ qua 1 lời nhắc (POST /reminders/{id}/dismiss)."""
    row = _transition(
        db,
        task_id,
        user_id,
        "completed",
        allowed_from={"confirmed"},
        actual_minutes=payload.actual_minutes if payload is not None else None,
    )
    reminders_service.cancel_pending_reminders(db, row.id)
    return _to_response(db, row)


@router.post("/{task_id}/start", response_model=TaskResponse)
@limiter.limit("60/minute")
def start_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Đánh dấu người dùng BẮT ĐẦU làm task. ADR-021, cảm biến thời gian làm việc.

    Vì sao cần một mốc riêng thay vì suy từ `completed_at`: người dùng thường
    không tick ngay khi xong mà để cuối buổi review một lượt. Đo trên production
    27/08 — 9/14 task tick vào 0h-1h sáng, gần như chắc chắn là giờ ngồi tick chứ
    không phải giờ làm.

    Bấm lại khi đã bắt đầu KHÔNG dời mốc: nếu dời, mỗi lần bấm nhầm sẽ cắt ngắn
    thời lượng đo được, và sai số luôn lệch về một phía.
    """
    row = _get_owned_task(db, task_id, user_id)
    if row.status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail=f"Task đang ở trạng thái '{row.status}', phải 'confirmed' mới bắt đầu được.",
        )
    if row.started_at is None:
        row.started_at = datetime.now(UTC)
        db.commit()
        db.refresh(row)
    return _to_response(db, row)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
@limiter.limit("30/minute")
def cancel_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """ADR-007 mục 4: chỉ thao tác này rút task khỏi mẫu số PRD §4.2 — bỏ qua
    lời nhắc KHÔNG được phép làm việc đó."""
    row = _transition(db, task_id, user_id, "cancelled", allowed_from={"proposed", "confirmed"})
    reminders_service.cancel_pending_reminders(db, row.id)
    return _to_response(db, row)


@router.post("/{task_id}/restore", response_model=TaskResponse)
@limiter.limit("30/minute")
def restore_task(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Lấy task khỏi thùng rác, đưa về 'proposed'.

    Thùng rác không có đường lấy lại thì không phải thùng rác — nó chỉ là xoá
    có độ trễ. Đây là thứ khiến việc xoá vĩnh viễn sau thời hạn lưu giữ trở nên
    chấp nhận được: người dùng có một cửa sổ thật để đổi ý.

    Về 'proposed' chứ không về trạng thái trước đó: hệ không lưu trạng thái
    trước khi huỷ, và đoán lại là bịa. 'proposed' là mức thấp nhất — người dùng
    duyệt lại một lần, không mất gì; đoán nhầm thành 'confirmed' thì task âm
    thầm quay lại các lời nhắc và mẫu số thống kê.
    """
    row = _transition(db, task_id, user_id, "proposed", allowed_from={"cancelled"})
    return _to_response(db, row)


def _require_confirmed_with_due_at(db: Session, task_id: int, user_id: str) -> Task:
    task = _get_owned_task(db, task_id, user_id)
    if task.status != "confirmed":
        # FR-062: không tạo lời nhắc hoặc mở ứng dụng lịch trước khi xác nhận.
        raise HTTPException(
            status_code=409,
            detail=f"Task đang ở trạng thái '{task.status}', phải 'confirmed' mới tạo được lịch.",
        )
    if task.due_at is None:
        # FR-061: thời gian còn mơ hồ phải để trống, không tự đoán, không tự tạo lịch.
        raise HTTPException(
            status_code=422,
            detail="Task chưa có thời gian rõ ràng (due_at trống) — người dùng cần tự nhập giờ trước khi tạo lịch.",
        )
    return task


def _task_evidence_dicts(db: Session, task_id: int) -> list[dict]:
    rows = db.execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).scalars().all()
    return [{"evidence_quote": r.evidence_quote, "deep_link": r.deep_link} for r in rows]


def _calendar_description(task: Task, evidence: list[dict]) -> str:
    lines = [task.detail.strip()] if task.detail.strip() else []
    lines.extend(f"Nguồn: {item['deep_link']}" for item in evidence[:5] if item.get("deep_link"))
    return "\n".join(lines)


@router.post("/{task_id}/calendar-sync", response_model=CalendarSyncResponse)
@limiter.limit("10/minute")
async def sync_task_to_calendar(
    request: Request,
    task_id: int,
    calendar_id: str = Query(default="primary", alias="calendarId", min_length=1, max_length=512),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarSyncResponse:
    """Write one confirmed task after the user's explicit Sync action."""
    task = _require_confirmed_with_due_at(db, task_id, user_id)
    if task.calendar_event_id:
        return CalendarSyncResponse(
            task_id=task.id,
            calendar_event_id=task.calendar_event_id,
            already_synced=True,
        )

    connection = preferred_connection(db, user_id, "google")
    if connection is None:
        raise HTTPException(status_code=409, detail="Google Calendar chưa được kết nối.")
    granted_scopes = set((connection.scopes or "").split())
    if not granted_scopes.intersection(_CALENDAR_WRITE_SCOPES):
        raise HTTPException(
            status_code=409,
            detail="Kết nối Google hiện chỉ có quyền đọc. Hãy kết nối lại để cấp quyền đồng bộ lịch.",
        )

    starts_at = task.due_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    ends_at = starts_at + (timedelta(days=1) if task.all_day else timedelta(minutes=30))
    try:
        created = await CalendarConnector(connection, db).create_event(
            calendar_id=calendar_id,
            title=task.title,
            description=_calendar_description(task, _task_evidence_dicts(db, task.id)),
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=task.all_day,
        )
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    task.calendar_event_id = str(created["id"])
    db.commit()
    return CalendarSyncResponse(
        task_id=task.id,
        calendar_event_id=task.calendar_event_id,
        calendar_url=build_authuser_link(created.get("htmlLink"), connection.provider_user_id),
    )


def _to_handoff_response(task_id: int, handoff: CalendarHandoff, google_calendar_url: str) -> CalendarHandoffResponse:
    settings = get_settings()
    base = settings.app_public_url.rstrip("/")
    return CalendarHandoffResponse(
        task_id=task_id,
        ics_url=f"{base}/api/v1/tasks/{task_id}/calendar-handoff.ics",
        google_calendar_url=google_calendar_url,
        opened=handoff.opened,
        opened_at=handoff.opened_at,
    )


@router.get("/{task_id}/calendar-handoff", response_model=CalendarHandoffResponse)
@limiter.limit("30/minute")
def get_calendar_handoff(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarHandoffResponse:
    task = _require_confirmed_with_due_at(db, task_id, user_id)
    evidence = _task_evidence_dicts(db, task_id)

    handoff = db.execute(select(CalendarHandoff).where(CalendarHandoff.task_id == task_id)).scalar_one_or_none()
    if handoff is None:
        handoff = CalendarHandoff(task_id=task_id)
        db.add(handoff)
        db.commit()
        db.refresh(handoff)

    # google_calendar_url phụ thuộc due_at/detail tại thời điểm gọi, không lưu
    # DB — đổi detail sau reduce lại thì link tự cập nhật lần gọi sau.
    google_calendar_url = build_google_calendar_url(task, evidence)
    return _to_handoff_response(task_id, handoff, google_calendar_url)


@router.get("/{task_id}/calendar-handoff.ics")
@limiter.limit("30/minute")
def download_calendar_handoff_ics(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    task = _require_confirmed_with_due_at(db, task_id, user_id)
    evidence = _task_evidence_dicts(db, task_id)
    content = build_ics(task, evidence)
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="task-{task_id}.ics"'},
    )


@router.post("/{task_id}/calendar-handoff/opened", response_model=CalendarHandoffResponse)
@limiter.limit("30/minute")
def mark_calendar_handoff_opened(
    request: Request,
    task_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarHandoffResponse:
    """FE gọi khi người dùng thật sự bấm mở .ics/link Google Calendar — tách
    biệt 'đã xác nhận bản nháp' khỏi 'đã mở trong ứng dụng lịch' (FR-065)."""
    task = _get_owned_task(db, task_id, user_id)
    handoff = db.execute(select(CalendarHandoff).where(CalendarHandoff.task_id == task_id)).scalar_one_or_none()
    if handoff is None:
        raise HTTPException(
            status_code=404,
            detail="Chưa gọi GET /calendar-handoff để tạo bản nháp lịch cho task này.",
        )
    handoff.opened = True
    handoff.opened_at = datetime.now(UTC)
    db.commit()
    db.refresh(handoff)

    google_calendar_url = build_google_calendar_url(task, _task_evidence_dicts(db, task_id)) if task.due_at else ""
    return _to_handoff_response(task_id, handoff, google_calendar_url)
