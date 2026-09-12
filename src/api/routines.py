from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.db import get_db
from src.models.routine import Routine, RoutineRun
from src.models.schemas import (
    RoutineCreateRequest,
    RoutineListResponse,
    RoutineResponse,
    RoutineRunListResponse,
    RoutineRunResponse,
    RoutineUpdateRequest,
)
from src.services import routines as routines_service

router = APIRouter(prefix="/routines", tags=["routines"])


def _to_response(row: Routine) -> RoutineResponse:
    return RoutineResponse.model_validate(row, from_attributes=True)


def _run_to_response(row: RoutineRun) -> RoutineRunResponse:
    return RoutineRunResponse.model_validate(row, from_attributes=True)


def _get_owned_routine(db: Session, routine_id: int, user_id: str) -> Routine:
    routine = routines_service.get_routine(db, user_id, routine_id)
    if routine is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy routine.")
    return routine


def _validate_schedule_fields(frequency: str, day_of_week: int | None, day_of_month: int | None) -> None:
    """weekly/monthly bắt buộc có đúng field ngày tương ứng — ràng buộc chéo
    field nên validate ở đây thay vì trong Pydantic model."""
    if frequency == "weekly" and day_of_week is None:
        raise HTTPException(status_code=422, detail="Routine hàng tuần cần chọn ngày trong tuần.")
    if frequency == "monthly" and day_of_month is None:
        raise HTTPException(status_code=422, detail="Routine hàng tháng cần chọn ngày trong tháng.")


@router.post("", response_model=RoutineResponse)
def create_routine(
    body: RoutineCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineResponse:
    _validate_schedule_fields(body.frequency, body.day_of_week, body.day_of_month)
    routine = routines_service.create_routine(
        db,
        user_id,
        name=body.name,
        instructions=body.instructions,
        frequency=body.frequency,
        interval_days=body.interval_days,
        hour=body.hour,
        minute=body.minute,
        day_of_week=body.day_of_week,
        day_of_month=body.day_of_month,
        timezone=body.timezone,
        notify_push=body.notify_push,
        notify_email=body.notify_email,
    )
    return _to_response(routine)


@router.get("", response_model=RoutineListResponse)
def list_routines(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineListResponse:
    rows = routines_service.list_routines(db, user_id)
    return RoutineListResponse(routines=[_to_response(row) for row in rows])


@router.get("/runs/recent", response_model=RoutineRunListResponse)
def list_recent_runs(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineRunListResponse:
    rows = routines_service.list_recent_routine_runs(db, user_id)
    runs = []
    for run, routine_name in rows:
        response = _run_to_response(run)
        response.routine_name = routine_name
        runs.append(response)
    return RoutineRunListResponse(runs=runs)


@router.get("/{routine_id}", response_model=RoutineResponse)
def get_routine(
    routine_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineResponse:
    return _to_response(_get_owned_routine(db, routine_id, user_id))


@router.patch("/{routine_id}", response_model=RoutineResponse)
def update_routine(
    routine_id: int,
    body: RoutineUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineResponse:
    routine = _get_owned_routine(db, routine_id, user_id)
    patch = body.model_dump(exclude_unset=True)
    frequency = patch.get("frequency", routine.frequency)
    day_of_week = patch.get("day_of_week", routine.day_of_week)
    day_of_month = patch.get("day_of_month", routine.day_of_month)
    _validate_schedule_fields(frequency, day_of_week, day_of_month)
    updated = routines_service.update_routine(db, routine, **patch)
    return _to_response(updated)


@router.delete("/{routine_id}", status_code=204)
def delete_routine(
    routine_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    routine = _get_owned_routine(db, routine_id, user_id)
    routines_service.delete_routine(db, routine)


@router.get("/{routine_id}/runs", response_model=RoutineRunListResponse)
def list_routine_runs(
    routine_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineRunListResponse:
    _get_owned_routine(db, routine_id, user_id)
    rows = routines_service.list_routine_runs(db, user_id, routine_id)
    return RoutineRunListResponse(runs=[_run_to_response(row) for row in rows])


@router.post("/{routine_id}/run-now", response_model=RoutineRunResponse)
async def run_routine_now(
    routine_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RoutineRunResponse:
    """Chạy thử ngay, không đợi vòng poll — cho UX "Tạo xong thấy kết quả liền"."""
    routine = _get_owned_routine(db, routine_id, user_id)
    run = await routines_service.run_routine(db, routine)
    return _run_to_response(run)
