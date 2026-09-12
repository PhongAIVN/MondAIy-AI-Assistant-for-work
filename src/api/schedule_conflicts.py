"""Endpoint cho luồng task/sự kiện bị trùng nhau (src/services/schedule_conflicts.py).

Ba thao tác: quét một cửa sổ thời gian, đọc danh sách, và ghi quyết định ưu
tiên. Quét chỉ đọc bộ nhớ đệm lịch nên không tốn hạn mức Google và gọi lại bao
nhiêu lần cũng không sinh bản trùng.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.db import get_db
from src.models.schedule_conflict import ScheduleConflict
from src.models.schemas import (
    ConflictEventSideResponse,
    ConflictTaskSideResponse,
    ScheduleConflictListResponse,
    ScheduleConflictResolveRequest,
    ScheduleConflictResponse,
)
from src.models.task import Task
from src.services import schedule_conflicts as service

router = APIRouter(prefix="/schedule-conflicts", tags=["schedule-conflicts"])

# Cùng trần 42 ngày với /calendar/events và /tasks/calendar-events — ba chỗ đọc
# cùng một cửa sổ lịch thì không nên có ba giới hạn khác nhau.
_MAX_WINDOW = timedelta(days=42)


def _to_response(db: Session, row: ScheduleConflict) -> ScheduleConflictResponse:
    """Ghép bên task (đọc hiện tại) với bên sự kiện (ảnh chụp lúc phát hiện).

    Bên task đọc live để giao diện thấy đúng trạng thái mới nhất; bên sự kiện
    lấy từ `event_snapshot` vì dòng đã `resolved` phải kể đúng bối cảnh lúc
    người dùng quyết định, kể cả khi sự kiện sau đó bị đổi giờ hoặc xoá.
    """
    task = db.execute(select(Task).where(Task.id == row.task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task của lần trùng này không còn tồn tại.")
    snapshot = row.event_snapshot or {}
    return ScheduleConflictResponse(
        id=row.id,
        conflict_type=row.conflict_type,
        status=row.status,
        overlap_minutes=row.overlap_minutes,
        suggestion=row.suggestion,
        suggestion_reasons=list(row.suggestion_reasons or []),
        resolution=row.resolution,
        resolution_note=row.resolution_note or "",
        resolved_at=row.resolved_at,
        detected_at=row.detected_at,
        task=ConflictTaskSideResponse(
            task_id=task.id,
            title=task.title,
            due_at=task.due_at,
            all_day=task.all_day,
            ambiguous=task.ambiguous,
            status=task.status,
            source_count=task.source_count,
            signal_strength=task.signal_strength,
        ),
        event=ConflictEventSideResponse(
            title=snapshot.get("title", ""),
            calendar_id=row.calendar_id,
            event_id=row.event_id,
            starts_at=snapshot.get("starts_at") or row.event_starts_at,
            ends_at=snapshot.get("ends_at"),
            all_day=snapshot.get("all_day", False),
            deep_link=snapshot.get("deep_link"),
            synced_at=snapshot.get("synced_at"),
        ),
    )


def _to_list_response(db: Session, user_id: str, rows: list[ScheduleConflict]) -> ScheduleConflictListResponse:
    """Bọc danh sách kèm số lần còn chờ quyết, đếm ở máy chủ để badge không sai
    khi giao diện đang lọc theo trạng thái khác."""
    open_count = len(service.list_open_conflicts(db, user_id))
    return ScheduleConflictListResponse(
        conflicts=[_to_response(db, row) for row in rows],
        open_count=open_count,
    )


@router.get("", response_model=ScheduleConflictListResponse)
def list_schedule_conflicts(
    status: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ScheduleConflictListResponse:
    """Đọc các lần trùng đã phát hiện, không tự quét lại."""
    rows = service.list_conflicts(db, user_id, status=status)
    return _to_list_response(db, user_id, rows)


@router.post("/detect", response_model=ScheduleConflictListResponse)
def detect_schedule_conflicts(
    time_from: datetime = Query(alias="timeFrom"),
    time_to: datetime = Query(alias="timeTo"),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ScheduleConflictListResponse:
    """Quét một cửa sổ thời gian và trả về các lần trùng còn chờ quyết."""
    if time_from.tzinfo is None or time_to.tzinfo is None:
        raise HTTPException(status_code=422, detail="timeFrom và timeTo phải có múi giờ.")
    if time_from >= time_to:
        raise HTTPException(status_code=422, detail="timeFrom phải sớm hơn timeTo.")
    if time_to - time_from > _MAX_WINDOW:
        raise HTTPException(status_code=422, detail="Chỉ được quét tối đa 42 ngày mỗi lần.")

    rows = service.detect_conflicts(db, user_id, time_from=time_from, time_to=time_to, now=datetime.now(UTC))
    return _to_list_response(db, user_id, rows)


@router.post("/{conflict_id}/resolve", response_model=ScheduleConflictResponse)
def resolve_schedule_conflict(
    conflict_id: int,
    payload: ScheduleConflictResolveRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ScheduleConflictResponse:
    """Ghi quyết định ưu tiên của người dùng cho một lần trùng."""
    row = db.execute(
        select(ScheduleConflict).where(
            ScheduleConflict.id == conflict_id,
            ScheduleConflict.user_id == user_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần trùng này.")

    try:
        updated = service.resolve_conflict(db, row, payload.resolution, note=payload.note)
    except ValueError as exc:
        # Quyết lại một dòng đã đóng là xung đột trạng thái, không phải dữ liệu sai.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(db, updated)
