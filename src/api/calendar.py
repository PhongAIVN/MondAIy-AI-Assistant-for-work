from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.connectors.calendar import (
    CalendarAPIError,
    CalendarConnector,
    CalendarEventNotFoundError,
    CalendarReadOnlyError,
    build_authuser_link,
)
from src.db import get_db
from src.models.calendar_event import CalendarEvent, CalendarOperation
from src.models.connection import Connection
from src.models.schemas import (
    CachedCalendarEventResponse,
    CalendarBatchFailure,
    CalendarBatchWriteRequest,
    CalendarBatchWriteResponse,
    CalendarEventWriteRequest,
    CalendarInfoResponse,
    CalendarWeekResponse,
    CalendarWriteResponse,
    ProgramSyncApplyRequest,
    ProgramSyncApplyResponse,
    ProgramSyncPlanItemResponse,
    ProgramSyncPreviewRequest,
    ProgramSyncPreviewResponse,
)
from src.models.user import User
from src.services import calendar_cache
from src.services.connections import preferred_connection
from src.services.program_access import reconcile_program_access
from src.services.program_calendar_sync import (
    approved_events,
    describe_event,
    get_sync_row,
    plan_program_sync,
    record_sync,
)
from src.services.program_cohorts import resolve_program_cohort_slug

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Lưới tuần chỉ cần 1 tuần, nhưng cho phép tải trước vài tuần khi người dùng
# lật nhanh. Trần 42 ngày giữ đúng giới hạn đã dùng ở /tasks/calendar-events.
_MAX_WINDOW = timedelta(days=42)
# Cửa sổ hoàn tác. 10 giây đủ để người dùng nhận ra mình bấm nhầm, đủ ngắn để
# không phải giữ trạng thái chờ lâu ở máy chủ (BR-14).
_UNDO_WINDOW = timedelta(seconds=10)
# Hạn chót trong lịch chương trình chỉ có một mốc. Ghi sang Google với
# DTEND == DTSTART thì nhiều ứng dụng lịch tự giãn thành khối 1 tiếng, nên tự
# cho một khối ngắn và có chủ đích — giống cách calendar_handoff.py xử lý.
_DEADLINE_BLOCK = timedelta(minutes=15)
_CALENDAR_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}


def _google_account_email(db: Session, user_id: str) -> str | None:
    """Email tài khoản Google đã kết nối, không kèm điều kiện status — chỉ để
    ghép vào link hiển thị, best-effort (đã ngắt kết nối thì trả None, link
    giữ nguyên như trước, không phải lỗi cần chặn request)."""
    connection = preferred_connection(db, user_id, "google")
    return connection.provider_user_id if connection else None


def _to_event_response(row: CalendarEvent, google_email: str | None = None) -> CachedCalendarEventResponse:
    """Đổi một dòng bộ nhớ đệm sang shape trả về cho giao diện."""
    return CachedCalendarEventResponse(
        id=row.event_id,
        calendar_id=row.calendar_id,
        title=row.title,
        description=row.description or "",
        start_at=row.starts_at,
        end_at=row.ends_at,
        all_day=row.all_day,
        status=row.status,
        deep_link=build_authuser_link(row.deep_link, google_email),
        synced_at=row.synced_at,
    )


def _require_google_connection(db: Session, user_id: str) -> Connection:
    """Lấy kết nối Google còn sống của đúng người dùng đang gọi.

    Điều kiện `user_id` nằm trong truy vấn để không bao giờ mượn được kết nối
    của người khác, kể cả khi tham số khác bị giả mạo.
    """
    connection = preferred_connection(db, user_id, "google")
    if connection is None:
        raise HTTPException(status_code=409, detail="Google Calendar chưa được kết nối.")
    return connection


def _require_write_scope(connection: Connection) -> None:
    """Chặn sớm khi token chỉ có quyền đọc, kèm hướng dẫn kết nối lại."""
    granted = set((connection.scopes or "").split())
    if not granted.intersection(_CALENDAR_WRITE_SCOPES):
        raise HTTPException(
            status_code=409,
            detail="Kết nối Google hiện chỉ có quyền đọc. Hãy kết nối lại để cấp quyền ghi lịch.",
        )


def _validate_window(time_from: datetime, time_to: datetime) -> None:
    """Chuẩn hoá điều kiện cửa sổ thời gian dùng chung cho mọi endpoint đọc."""
    if time_from.tzinfo is None or time_to.tzinfo is None:
        raise HTTPException(status_code=422, detail="timeFrom và timeTo phải có múi giờ.")
    if time_from >= time_to:
        raise HTTPException(status_code=422, detail="timeFrom phải sớm hơn timeTo.")
    if time_to - time_from > _MAX_WINDOW:
        raise HTTPException(status_code=422, detail="Chỉ được tải tối đa 42 ngày lịch mỗi lần.")


@router.get("/events", response_model=CalendarWeekResponse)
async def list_week_events(
    time_from: datetime = Query(alias="timeFrom"),
    time_to: datetime = Query(alias="timeTo"),
    refresh: bool = Query(default=False),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarWeekResponse:
    """Đọc lịch cho lưới tuần, ưu tiên bộ nhớ đệm (FR-102).

    Mặc định trả ngay dữ liệu đã lưu để màn hình hiện tức thì; giao diện tự gọi
    lại với `refresh=true` ở nền. Không tự gọi Google trong nhánh mặc định vì
    như vậy mỗi lần lật tuần lại là một lần gọi API và mất luôn lợi ích của
    việc lưu đệm.
    """
    _validate_window(time_from, time_to)

    failed: list[str] = []
    calendars: list[dict[str, str]] = []
    origin = "cache"
    if refresh:
        connection = _require_google_connection(db, user_id)
        try:
            result = await calendar_cache.refresh_window(
                db,
                user_id=user_id,
                connection=connection,
                time_from=time_from,
                time_to=time_to,
            )
        except CalendarAPIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        calendars = result["calendars"]
        failed = result["failed_calendars"]
        origin = "refreshed"

    rows = calendar_cache.read_window(db, user_id=user_id, time_from=time_from, time_to=time_to)
    google_email = connection.provider_user_id if refresh else _google_account_email(db, user_id)
    return CalendarWeekResponse(
        events=[_to_event_response(row, google_email) for row in rows],
        calendars=[CalendarInfoResponse(**calendar) for calendar in calendars],
        origin=origin,
        last_synced_at=calendar_cache.last_synced_at(db, user_id=user_id),
        failed_calendars=failed,
    )


def _record_operation(
    db: Session,
    *,
    user_id: str,
    calendar_id: str,
    event_id: str,
    op: str,
    before: dict,
    after: dict,
) -> CalendarOperation:
    """Ghi lại thao tác vừa thực hiện kèm dữ liệu đủ để áp ngược lại."""
    operation = CalendarOperation(
        user_id=user_id,
        calendar_id=calendar_id,
        event_id=event_id,
        op=op,
        before=before,
        after=after,
        expires_at=datetime.now(UTC) + _UNDO_WINDOW,
    )
    db.add(operation)
    return operation


def _get_cached_event(db: Session, user_id: str, calendar_id: str, event_id: str) -> CalendarEvent | None:
    """Đọc một dòng bộ nhớ đệm trong phạm vi người dùng đang gọi."""
    return db.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.event_id == event_id,
        )
    ).scalar_one_or_none()


@router.post("/events", response_model=CalendarWriteResponse, status_code=201)
@limiter.limit("10/minute")
async def create_event(
    request: Request,
    payload: CalendarEventWriteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarWriteResponse:
    """Người dùng tự tạo sự kiện trên lưới lịch — ghi ngay, không hộp thoại (FR-069).

    Thao tác trên giao diện chính là sự xác nhận, nên ở đây không có bước
    preview. Đổi lại, phải trả về mã thao tác để hoàn tác được trong 10 giây.
    """
    if not payload.title or payload.start_at is None or payload.end_at is None:
        # FR-061: thời gian mơ hồ để trống chứ không tự đoán. Người dùng tạo
        # tay thì giao diện phải hỏi đủ, máy chủ không điền hộ.
        raise HTTPException(status_code=422, detail="Cần đủ title, startAt và endAt để tạo sự kiện.")

    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)
    try:
        created = await CalendarConnector(connection, db).create_event(
            calendar_id=payload.calendar_id,
            title=payload.title,
            description=payload.description or "",
            starts_at=payload.start_at,
            ends_at=payload.end_at,
            all_day=payload.all_day,
        )
    except CalendarReadOnlyError as exc:
        # 409 chứ không 502: phía Google không hỏng, người dùng chỉ không có
        # quyền ghi vào lịch đó. Thử lại không đổi được gì.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    row = calendar_cache.upsert_event(db, user_id=user_id, calendar_id=payload.calendar_id, raw_event=created)
    operation = _record_operation(
        db,
        user_id=user_id,
        calendar_id=payload.calendar_id,
        event_id=str(created["id"]),
        op="create",
        before={},
        after={"id": str(created["id"])},
    )
    db.commit()
    db.refresh(operation)
    if row is not None:
        db.refresh(row)
    return CalendarWriteResponse(
        event=_to_event_response(row, connection.provider_user_id) if row is not None else None,
        operation_id=operation.id,
        undo_expires_at=operation.expires_at,
    )


@router.post("/events/batch", response_model=CalendarBatchWriteResponse, status_code=201)
@limiter.limit("5/minute")
async def create_events_batch(
    request: Request,
    payload: CalendarBatchWriteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarBatchWriteResponse:
    """Ghi đúng các mốc user đã chọn sau màn hình review ảnh."""
    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)
    connector = CalendarConnector(connection, db)
    created: list[CalendarWriteResponse] = []
    failed: list[CalendarBatchFailure] = []

    for index, event in enumerate(payload.events):
        if not event.title or event.start_at is None or event.end_at is None:
            failed.append(CalendarBatchFailure(index=index, detail="Cần đủ title, startAt và endAt."))
            continue
        try:
            raw = await connector.create_event(
                calendar_id=payload.calendar_id,
                title=event.title,
                description=event.description or "",
                starts_at=event.start_at,
                ends_at=event.end_at,
                all_day=event.all_day,
            )
            row = calendar_cache.upsert_event(
                db, user_id=user_id, calendar_id=payload.calendar_id, raw_event=raw
            )
            operation = _record_operation(
                db,
                user_id=user_id,
                calendar_id=payload.calendar_id,
                event_id=str(raw["id"]),
                op="create",
                before={},
                after={"id": str(raw["id"])},
            )
            db.flush()
            if row is not None:
                db.refresh(row)
            created.append(
                CalendarWriteResponse(
                    event=_to_event_response(row, connection.provider_user_id) if row is not None else None,
                    operation_id=operation.id,
                    undo_expires_at=operation.expires_at,
                )
            )
        except CalendarAPIError as exc:
            failed.append(CalendarBatchFailure(index=index, detail=str(exc)))

    db.commit()
    return CalendarBatchWriteResponse(created=created, failed=failed)


@router.patch("/events/{event_id}", response_model=CalendarWriteResponse)
async def update_event(
    event_id: str,
    payload: CalendarEventWriteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarWriteResponse:
    """Người dùng sửa hoặc kéo đổi giờ một sự kiện (FR-069).

    Chỉ những trường người dùng thật sự đổi mới được gửi lên Google, phần còn
    lại của sự kiện giữ nguyên. Bản trước khi sửa được chụp lại để hoàn tác.
    """
    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)
    cached = _get_cached_event(db, user_id, payload.calendar_id, event_id)
    before = dict(cached.payload) if cached is not None else {}

    try:
        updated = await CalendarConnector(connection, db).update_event(
            calendar_id=payload.calendar_id,
            event_id=event_id,
            title=payload.title,
            description=payload.description,
            starts_at=payload.start_at,
            ends_at=payload.end_at,
            all_day=payload.all_day,
        )
    except CalendarEventNotFoundError as exc:
        calendar_cache.mark_stale(db, user_id=user_id, calendar_id=payload.calendar_id, event_id=event_id)
        db.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CalendarReadOnlyError as exc:
        # 409 chứ không 502: phía Google không hỏng, người dùng chỉ không có
        # quyền ghi vào lịch đó. Thử lại không đổi được gì.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    row = calendar_cache.upsert_event(db, user_id=user_id, calendar_id=payload.calendar_id, raw_event=updated)
    operation = _record_operation(
        db,
        user_id=user_id,
        calendar_id=payload.calendar_id,
        event_id=event_id,
        op="update",
        before=before,
        after={"id": event_id},
    )
    db.commit()
    db.refresh(operation)
    if row is not None:
        db.refresh(row)
    return CalendarWriteResponse(
        event=_to_event_response(row, connection.provider_user_id) if row is not None else None,
        operation_id=operation.id,
        undo_expires_at=operation.expires_at,
    )


@router.delete("/events/{event_id}", response_model=CalendarWriteResponse)
async def delete_event(
    event_id: str,
    calendar_id: str = Query(default="primary", alias="calendarId", max_length=512),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarWriteResponse:
    """Người dùng xoá một sự kiện (FR-069).

    Bản chụp trước khi xoá được giữ lại trong bộ nhớ đệm với trạng thái
    `deleted`. Xoá hẳn khỏi DB thì không còn gì để dựng lại khi người dùng bấm
    hoàn tác, mà xoá trên Google là thao tác không tự lấy lại được (BR-14).
    """
    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)
    cached = _get_cached_event(db, user_id, calendar_id, event_id)
    before = dict(cached.payload) if cached is not None else {}

    try:
        await CalendarConnector(connection, db).delete_event(calendar_id=calendar_id, event_id=event_id)
    except CalendarEventNotFoundError as exc:
        calendar_cache.mark_stale(db, user_id=user_id, calendar_id=calendar_id, event_id=event_id)
        db.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CalendarReadOnlyError as exc:
        # 409 chứ không 502: phía Google không hỏng, người dùng chỉ không có
        # quyền ghi vào lịch đó. Thử lại không đổi được gì.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if cached is not None:
        cached.status = "deleted"
    operation = _record_operation(
        db,
        user_id=user_id,
        calendar_id=calendar_id,
        event_id=event_id,
        op="delete",
        before=before,
        after={},
    )
    db.commit()
    db.refresh(operation)
    return CalendarWriteResponse(
        event=None,
        operation_id=operation.id,
        undo_expires_at=operation.expires_at,
    )


def _require_program_level_a(db: Session, user_id: str) -> str:
    """Chặn đồng bộ lịch chương trình với tài khoản chưa khớp danh tính khóa.

    Tính lại mức thay vì đọc cột trong DB: tài khoản tạo trước khi có bước phân
    loại vẫn đang giữ mức cũ cho tới lần đăng nhập sau (ADR-004).
    """
    level = reconcile_program_access(db, user_id)
    if level != "A":
        raise HTTPException(
            status_code=403,
            detail=(
                "Tài khoản này chưa khớp danh tính chương trình nên chưa đồng bộ được "
                "lịch khóa học. Hãy kết nối Discord bằng đúng tài khoản đang tham gia khóa."
            ),
        )
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    try:
        return resolve_program_cohort_slug(user.program_cohort_slug)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Cohort chương trình cấu hình không hợp lệ.") from exc


@router.post("/program-sync/preview", response_model=ProgramSyncPreviewResponse)
async def preview_program_sync(
    payload: ProgramSyncPreviewRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgramSyncPreviewResponse:
    """Xem trước những mốc chương trình sẽ được ghi vào lịch cá nhân (ADR-009).

    Endpoint này **không ghi gì**. Nó tồn tại để user nhìn thấy đúng danh sách
    trước khi bấm đồng ý — bước bắt buộc của luồng agent-đề-xuất trong ADR-007.
    """
    cohort = _require_program_level_a(db, user_id)
    if payload.time_from and payload.time_to and payload.time_from >= payload.time_to:
        raise HTTPException(status_code=422, detail="timeFrom phải sớm hơn timeTo.")

    plan = plan_program_sync(
        db,
        user_id=user_id,
        cohort_slug=cohort,
        event_types=payload.event_types,
        since=payload.time_from,
        until=payload.time_to,
    )
    return ProgramSyncPreviewResponse(
        cohort_slug=cohort,
        items=[
            ProgramSyncPlanItemResponse(
                program_event_id=item.program_event_id,
                event_type=item.event_type,
                title=item.title,
                start_at=item.starts_at,
                end_at=item.ends_at,
                action=item.action,
                reason=item.reason,
            )
            for item in plan
        ],
    )


@router.post("/program-sync/apply", response_model=ProgramSyncApplyResponse)
async def apply_program_sync(
    payload: ProgramSyncApplyRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProgramSyncApplyResponse:
    """Ghi những mốc user vừa đồng ý vào lịch Google của họ (ADR-009).

    Cơ chế: chỉ ghi đúng các ID có trong `programEventIds`, và lọc lại danh sách
    đó phía máy chủ theo cohort cùng `visibility = program`. Mốc đã có ánh xạ
    thì cập nhật đúng event cũ; chưa có thì tạo mới. Mốc ghi hỏng được trả về
    trong `skipped` thay vì làm hỏng cả lần đồng bộ, vì bỏ dở im lặng khiến user
    tin lịch đã đủ trong khi không đủ.
    """
    cohort = _require_program_level_a(db, user_id)
    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)

    events = approved_events(db, user_id=user_id, cohort_slug=cohort, program_event_ids=payload.program_event_ids)
    if not events:
        raise HTTPException(status_code=422, detail="Không có mốc chương trình hợp lệ để đồng bộ.")

    connector = CalendarConnector(connection, db)
    now = datetime.now(UTC)
    created = updated = 0
    skipped: list[str] = []

    for event in events:
        title, description = describe_event(event)
        # Hạn chót chỉ có một mốc. Google cần cả hai đầu nên cho nó một khối
        # ngắn thay vì khối 0 phút — cùng cách calendar_handoff.py đã xử lý.
        starts_at = event.starts_at
        ends_at = event.ends_at or starts_at + _DEADLINE_BLOCK
        row = get_sync_row(db, user_id=user_id, program_event_id=event.id)

        try:
            if row is None:
                raw = await connector.create_event(
                    calendar_id=payload.calendar_id,
                    title=title,
                    description=description,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    all_day=False,
                )
                created += 1
            else:
                raw = await connector.update_event(
                    calendar_id=row.calendar_id,
                    event_id=row.event_id,
                    title=title,
                    description=description,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    all_day=False,
                )
                updated += 1
        except CalendarEventNotFoundError:
            # Event đã bị xoá phía Google. Không tự tạo lại: user xoá nó là một
            # quyết định, dựng lại im lặng là ghi đè quyết định đó.
            if row is not None:
                row.status = "removed_by_user"
                row.updated_at = now
            skipped.append(f"{event.title}: không còn trong lịch Google, cần duyệt lại")
            continue
        except CalendarAPIError as exc:
            skipped.append(f"{event.title}: {exc}")
            continue

        calendar_id = row.calendar_id if row is not None else payload.calendar_id
        calendar_cache.upsert_event(db, user_id=user_id, calendar_id=calendar_id, raw_event=raw)
        record_sync(
            db,
            user_id=user_id,
            event=event,
            calendar_id=calendar_id,
            google_event_id=str(raw["id"]),
            now=now,
        )

    db.commit()
    return ProgramSyncApplyResponse(created=created, updated=updated, skipped=skipped)


@router.post("/operations/{operation_id}/undo", response_model=CalendarWriteResponse)
async def undo_operation(
    operation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CalendarWriteResponse:
    """Hoàn tác thao tác ghi trực tiếp trong cửa sổ cho phép (BR-14).

    Ba nhánh đối xứng: tạo thì xoá đi, xoá thì dựng lại từ bản chụp, sửa thì
    ghi lại giá trị trước đó. Quá hạn thì từ chối rõ ràng thay vì im lặng
    không làm gì — người dùng phải biết thao tác của họ không có tác dụng.
    """
    operation = db.execute(
        select(CalendarOperation).where(
            CalendarOperation.id == operation_id,
            CalendarOperation.user_id == user_id,
        )
    ).scalar_one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thao tác để hoàn tác.")
    if operation.undone_at is not None:
        raise HTTPException(status_code=409, detail="Thao tác này đã được hoàn tác.")
    expires_at = operation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        raise HTTPException(status_code=409, detail="Đã quá thời gian hoàn tác.")

    connection = _require_google_connection(db, user_id)
    _require_write_scope(connection)
    connector = CalendarConnector(connection, db)
    row: CalendarEvent | None = None
    try:
        if operation.op == "create":
            await connector.delete_event(calendar_id=operation.calendar_id, event_id=operation.event_id)
            cached = _get_cached_event(db, user_id, operation.calendar_id, operation.event_id)
            if cached is not None:
                cached.status = "deleted"
        elif operation.op == "delete":
            row = await _restore_deleted_event(db, connector, operation, user_id)
        else:
            row = await _restore_previous_values(db, connector, operation, user_id)
    except CalendarReadOnlyError as exc:
        # 409 chứ không 502: phía Google không hỏng, người dùng chỉ không có
        # quyền ghi vào lịch đó. Thử lại không đổi được gì.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CalendarAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    operation.undone_at = datetime.now(UTC)
    db.commit()
    if row is not None:
        db.refresh(row)
    return CalendarWriteResponse(
        event=_to_event_response(row, connection.provider_user_id) if row is not None else None,
        operation_id=operation.id,
        undo_expires_at=expires_at,
    )


async def _restore_deleted_event(
    db: Session,
    connector: CalendarConnector,
    operation: CalendarOperation,
    user_id: str,
) -> CalendarEvent | None:
    """Dựng lại sự kiện đã xoá từ bản chụp đã lưu.

    Google không cho khôi phục sự kiện đã xoá, nên phải tạo mới. Sự kiện mới
    mang mã khác — đó là lý do bản ghi cũ trong bộ nhớ đệm được đánh dấu
    `deleted` chứ không tái sử dụng.
    """
    snapshot = operation.before or {}
    if not snapshot.get("start"):
        raise HTTPException(status_code=409, detail="Không còn dữ liệu để dựng lại sự kiện đã xoá.")
    starts_at, ends_at, all_day = _window_from_snapshot(snapshot)
    created = await connector.create_event(
        calendar_id=operation.calendar_id,
        title=snapshot.get("summary") or "(không có tiêu đề)",
        description=snapshot.get("description") or "",
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
    )
    return calendar_cache.upsert_event(db, user_id=user_id, calendar_id=operation.calendar_id, raw_event=created)


async def _restore_previous_values(
    db: Session,
    connector: CalendarConnector,
    operation: CalendarOperation,
    user_id: str,
) -> CalendarEvent | None:
    """Ghi lại giá trị trước khi sửa."""
    snapshot = operation.before or {}
    if not snapshot:
        raise HTTPException(status_code=409, detail="Không còn dữ liệu để hoàn tác thao tác sửa.")
    starts_at, ends_at, all_day = _window_from_snapshot(snapshot)
    updated = await connector.update_event(
        calendar_id=operation.calendar_id,
        event_id=operation.event_id,
        title=snapshot.get("summary"),
        description=snapshot.get("description"),
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=all_day,
    )
    return calendar_cache.upsert_event(db, user_id=user_id, calendar_id=operation.calendar_id, raw_event=updated)


def _window_from_snapshot(snapshot: dict) -> tuple[datetime, datetime | None, bool]:
    """Đọc lại khoảng thời gian từ bản chụp, dùng chung cho hai nhánh hoàn tác."""
    from src.connectors.calendar import parse_event_window

    return parse_event_window({"start": snapshot.get("start", {}), "end": snapshot.get("end", {})})
