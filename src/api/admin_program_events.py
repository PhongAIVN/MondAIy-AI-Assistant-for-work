"""Trang quản trị lịch chương trình: sửa, thêm, phát hành (ADR-010).

Feed ICS của ban tổ chức là nguồn nhập, không phải nguồn chuẩn tuyệt đối. Ban tổ
chức nội bộ vẫn cần sửa một buổi bị ghi sai, thêm buổi chưa có trên Phoenix, và
quyết định khi nào học viên nhìn thấy. Router này là chỗ duy nhất làm được việc
đó.

Nguyên tắc: mọi thay đổi ở đây **thắng feed** cho đúng trường đã sửa, và mọi
thay đổi đều vào audit log. Không có đường nào sửa lịch mà không để lại dấu.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.deps import require_admin
from src.db import get_db
from src.models.program_event import ProgramEvent
from src.models.schemas import (
    AdminProgramEventCreateRequest,
    AdminProgramEventListResponse,
    AdminProgramEventPublishRequest,
    AdminProgramEventRow,
    AdminProgramEventUpdateRequest,
)
from src.models.user import User
from src.services.program_calendar import FEED_FIELDS
from src.services.program_cohorts import configured_program_cohort_slug, normalize_program_cohort_slug
from src.services.program_event_notifications import queue_program_event_notices
from src.services.telemetry import emit_audit

router = APIRouter(
    prefix="/admin/program-events",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

_STATUSES = ("draft", "published", "archived")
_MAX_LIMIT = 200


def _as_utc(value: datetime) -> datetime:
    """SQLite làm rơi tzinfo; coi dữ liệu lịch đã lưu là UTC như contract."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_row(
    event: ProgramEvent,
    *,
    changed_fields: list[str] | None = None,
    notification_count: int = 0,
) -> AdminProgramEventRow:
    """Đổi một mốc sang shape trang quản trị.

    Trả kèm `feedPayload` để màn hình so được bản của ban tổ chức với bản đang
    hiển thị — không có nó thì admin không biết mình đang ghi đè lên cái gì.
    """
    return AdminProgramEventRow(
        id=event.id,
        cohort_slug=event.cohort_slug,
        external_id=event.external_id,
        event_type=event.event_type,
        visibility=event.visibility,
        title=event.title,
        description=event.description,
        host=event.host,
        location_url=event.location_url,
        start_at=event.starts_at,
        end_at=event.ends_at,
        origin=event.origin,
        status=event.status,
        locked_fields=list(event.locked_fields or []),
        source_conflict=bool(event.source_conflict),
        feed_payload=event.feed_payload,
        updated_by=event.updated_by,
        updated_at=_as_utc(event.updated_at) if event.updated_at else None,
        published_at=_as_utc(event.published_at) if event.published_at else None,
        changed_fields=changed_fields or [],
        notification_count=notification_count,
    )


def _get_event(db: Session, event_id: int) -> ProgramEvent:
    cohort = configured_program_cohort_slug()
    event = db.scalar(
        select(ProgramEvent).where(
            ProgramEvent.id == event_id,
            func.lower(ProgramEvent.cohort_slug) == cohort,
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Mốc chương trình không tồn tại.")
    return event


def _configured_cohort(requested: str | None) -> str:
    """Không cho request admin mở rộng phạm vi chỉ bằng một query/body field."""
    cohort = configured_program_cohort_slug()
    if requested is not None:
        try:
            if normalize_program_cohort_slug(requested) != cohort:
                raise HTTPException(status_code=404, detail="Mốc chương trình không tồn tại.")
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Mốc chương trình không tồn tại.") from exc
    return cohort


def _require_current_revision(
    event: ProgramEvent,
    *,
    expected_updated_at: datetime | None,
    expected_provided: bool,
) -> None:
    """Chặn ghi đè khi mốc đã đổi kể từ lúc admin mở form."""
    if not expected_provided:
        return
    current = event.updated_at
    if current is None or expected_updated_at is None:
        if current is expected_updated_at:
            return
        raise HTTPException(status_code=409, detail="Mốc đã thay đổi. Hãy tải lại trước khi lưu.")
    if _as_utc(current) != _as_utc(expected_updated_at):
        raise HTTPException(status_code=409, detail="Mốc đã thay đổi. Hãy tải lại trước khi lưu.")


@router.get("", response_model=AdminProgramEventListResponse)
def list_program_events_admin(
    cohort_slug: str | None = Query(default=None, alias="cohortSlug"),
    status: str | None = Query(default=None),
    conflicts_only: bool = Query(default=False, alias="conflictsOnly"),
    limit: int = Query(default=100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AdminProgramEventListResponse:
    """Liệt kê mốc chương trình cho trang quản trị, gồm cả draft và archived."""
    cohort = _configured_cohort(cohort_slug)
    filters = [func.lower(ProgramEvent.cohort_slug) == cohort]
    if status:
        if status not in _STATUSES:
            raise HTTPException(status_code=422, detail=f"status phải thuộc {_STATUSES}.")
        filters.append(ProgramEvent.status == status)
    if conflicts_only:
        filters.append(ProgramEvent.source_conflict.is_(True))

    total = db.scalar(select(func.count(ProgramEvent.id)).where(*filters)) or 0
    rows = db.scalars(
        select(ProgramEvent)
        .where(*filters)
        .order_by(ProgramEvent.starts_at.asc(), ProgramEvent.id.asc())
        .limit(limit)
        .offset(offset)
    ).all()
    conflicts = (
        db.scalar(
            select(func.count(ProgramEvent.id)).where(
                func.lower(ProgramEvent.cohort_slug) == cohort, ProgramEvent.source_conflict.is_(True)
            )
        )
        or 0
    )
    return AdminProgramEventListResponse(
        items=[_to_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
        cohort_slug=cohort,
        conflict_count=conflicts,
    )


@router.post("", response_model=AdminProgramEventRow, status_code=201)
def create_program_event(
    payload: AdminProgramEventCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Thêm một mốc không có trên feed của ban tổ chức.

    Mốc tự tạo bắt đầu ở `draft` — thêm xong là hiện ngay cho học viên thì
    không còn bước nào để soát lại trước khi phát hành.
    """
    cohort = _configured_cohort(payload.cohort_slug)
    now = datetime.now(UTC)
    external_id = f"admin:{cohort}:{int(now.timestamp() * 1000)}"
    event = ProgramEvent(
        cohort_slug=cohort,
        external_id=external_id,
        event_type=payload.event_type,
        visibility=payload.visibility,
        title=payload.title,
        description=payload.description or "",
        host=payload.host,
        location_url=payload.location_url,
        starts_at=payload.start_at,
        ends_at=payload.end_at,
        content_hash="",
        observed_at=now,
        origin="admin",
        status="draft",
        updated_by=str(actor.id),
        updated_at=now,
    )
    db.add(event)
    db.flush()
    emit_audit(
        db,
        action="program_event_created",
        object_type="program_event",
        object_id=str(event.id),
        actor_type="admin",
        actor_id=str(actor.id),
        # Chỉ ghi tên trường và mốc thời gian, không ghi nội dung. `/admin/audit`
        # là luồng chung cho mọi loại đối tượng và PRD §5 cấm nội dung gốc xuất
        # hiện ở đó; nội dung mốc đọc trên chính trang lịch.
        after={"starts_at": event.starts_at.isoformat(), "origin": "admin"},
    )
    db.commit()
    db.refresh(event)
    return _to_row(event)


@router.patch("/{event_id}", response_model=AdminProgramEventRow)
def update_program_event(
    event_id: int,
    payload: AdminProgramEventUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Sửa nội dung một mốc.

    Trường nào admin sửa trên mốc gốc feed thì trường đó vào `locked_fields`:
    lần nhập feed sau sẽ không ghi đè nó. Đây là điểm khác biệt duy nhất khiến
    trang quản trị có ý nghĩa — không khóa thì mọi chỉnh sửa biến mất sau lần
    đồng bộ kế tiếp, và biến mất im lặng.
    """
    event = _get_event(db, event_id)
    _require_current_revision(
        event,
        expected_updated_at=payload.expected_updated_at,
        expected_provided="expected_updated_at" in payload.model_fields_set,
    )
    changes = payload.model_dump(exclude_unset=True, by_alias=False)
    changes.pop("cohort_slug", None)
    notify_users = bool(changes.pop("notify_users", False))
    change_note = str(changes.pop("change_note", ""))
    changes.pop("expected_updated_at", None)
    if not changes:
        raise HTTPException(status_code=422, detail="Không có trường nào để cập nhật.")
    if notify_users and event.status != "published":
        raise HTTPException(
            status_code=409,
            detail="Chỉ có thể báo thay đổi của mốc đã phát hành.",
        )

    merged_start = changes.get("start_at", event.starts_at)
    merged_end = changes.get("end_at", event.ends_at)
    if merged_end is not None and _as_utc(merged_end) <= _as_utc(merged_start):
        raise HTTPException(status_code=422, detail="endAt phải sau startAt.")

    field_map = {"start_at": "starts_at", "end_at": "ends_at"}
    previous_starts_at = event.starts_at
    changed_fields: list[str] = []
    newly_locked: list[str] = []
    for name, value in changes.items():
        column = field_map.get(name, name)
        if getattr(event, column) == value:
            continue
        setattr(event, column, value)
        changed_fields.append(column)
        if column in FEED_FIELDS and event.origin == "feed":
            newly_locked.append(column)

    if not changed_fields:
        return _to_row(event, changed_fields=[])

    if newly_locked:
        event.locked_fields = sorted(set(event.locked_fields or []) | set(newly_locked))
        # Admin vừa chọn bản của mình cho đúng những trường đang xung đột, nên
        # cờ xung đột hết lý do tồn tại.
        event.source_conflict = False

    now = datetime.now(UTC)
    event.updated_by = str(actor.id)
    event.updated_at = now
    db.flush()
    notification_count = 0
    if notify_users:
        notification_count = queue_program_event_notices(
            db,
            event=event,
            changed_fields=changed_fields,
            change_note=change_note,
            previous_starts_at=previous_starts_at,
            now=now,
        )
    emit_audit(
        db,
        action="program_event_updated",
        object_type="program_event",
        object_id=str(event.id),
        actor_type="admin",
        actor_id=str(actor.id),
        # Chỉ tên trường, không kèm giá trị cũ/mới — xem lý do ở hàm tạo mới.
        before={"changed_fields": changed_fields},
        after={
            "locked_fields": event.locked_fields,
            "notification_count": notification_count,
        },
    )
    db.commit()
    db.refresh(event)
    return _to_row(
        event,
        changed_fields=changed_fields,
        notification_count=notification_count,
    )


@router.post("/{event_id}/publish", response_model=AdminProgramEventRow)
def publish_program_event(
    event_id: int,
    payload: AdminProgramEventPublishRequest | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Phát hành: từ lúc này học viên mức A mới đọc được mốc này."""
    options = payload or AdminProgramEventPublishRequest()
    return _set_status(
        db,
        event_id,
        "published",
        actor,
        notify_users=options.notify_users,
        change_note=options.change_note,
        expected_updated_at=options.expected_updated_at,
        expected_provided=payload is not None
        and "expected_updated_at" in options.model_fields_set,
    )


@router.post("/{event_id}/unpublish", response_model=AdminProgramEventRow)
def unpublish_program_event(
    event_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Rút về nháp — dùng khi phát hiện nội dung sai sau khi đã phát hành."""
    return _set_status(db, event_id, "draft", actor)


@router.post("/{event_id}/archive", response_model=AdminProgramEventRow)
def archive_program_event(
    event_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Gỡ khỏi lịch nhưng giữ lại dòng.

    Không có endpoint xóa hẳn: mốc đã phát hành có thể đã nằm trong lịch Google
    của học viên (ADR-009), xóa sạch dấu vết ở đây là mất khả năng giải thích
    thứ họ đang thấy đến từ đâu.
    """
    return _set_status(db, event_id, "archived", actor)


def _set_status(
    db: Session,
    event_id: int,
    status: str,
    actor: User,
    *,
    notify_users: bool = False,
    change_note: str = "",
    expected_updated_at: datetime | None = None,
    expected_provided: bool = False,
) -> AdminProgramEventRow:
    """Đổi trạng thái phát hành và ghi audit."""
    event = _get_event(db, event_id)
    _require_current_revision(
        event,
        expected_updated_at=expected_updated_at,
        expected_provided=expected_provided,
    )
    if event.status == status:
        return _to_row(event)

    before = event.status
    now = datetime.now(UTC)
    event.status = status
    event.updated_by = str(actor.id)
    event.updated_at = now
    if status == "published":
        event.published_at = now
    db.flush()
    notification_count = 0
    if notify_users:
        notification_count = queue_program_event_notices(
            db,
            event=event,
            changed_fields=["status"],
            change_note=change_note,
            now=now,
        )

    emit_audit(
        db,
        action=f"program_event_{status}",
        object_type="program_event",
        object_id=str(event.id),
        actor_type="admin",
        actor_id=str(actor.id),
        before={"status": before},
        after={"status": status, "notification_count": notification_count},
    )
    db.commit()
    db.refresh(event)
    return _to_row(
        event,
        changed_fields=["status"],
        notification_count=notification_count,
    )


@router.post("/{event_id}/revert-to-source", response_model=AdminProgramEventRow)
def revert_to_source(
    event_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramEventRow:
    """Bỏ mọi chỉnh sửa tay, quay về đúng bản ban tổ chức phát ra.

    Cần có vì luật "admin thắng feed" không có đường lui thì một lần sửa nhầm là
    mốc đó đóng băng vĩnh viễn, không bao giờ nhận cập nhật từ ban tổ chức nữa.
    """
    event = _get_event(db, event_id)
    if event.origin != "feed":
        raise HTTPException(status_code=422, detail="Mốc tự tạo không có bản gốc từ feed.")
    if not event.feed_payload:
        raise HTTPException(
            status_code=409,
            detail="Chưa có ảnh chụp bản gốc cho mốc này. Chạy lại lần nhập feed rồi thử lại.",
        )

    snapshot = event.feed_payload
    before = {"locked_fields": list(event.locked_fields or [])}
    event.event_type = snapshot["event_type"]
    event.visibility = snapshot["visibility"]
    event.title = snapshot["title"]
    event.description = snapshot["description"]
    event.host = snapshot["host"]
    event.location_url = snapshot["location_url"]
    event.starts_at = datetime.fromisoformat(snapshot["starts_at"])
    event.ends_at = datetime.fromisoformat(snapshot["ends_at"]) if snapshot["ends_at"] else None
    event.locked_fields = []
    event.source_conflict = False
    event.updated_by = str(actor.id)
    event.updated_at = datetime.now(UTC)

    emit_audit(
        db,
        action="program_event_reverted_to_source",
        object_type="program_event",
        object_id=str(event.id),
        actor_type="admin",
        actor_id=str(actor.id),
        before=before,
        after={"locked_fields": []},
    )
    db.commit()
    db.refresh(event)
    return _to_row(event)
