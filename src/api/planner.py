"""API cho Planning Workspace: tạo proposal, không ghi Calendar ngoài hệ thống."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.db import get_db
from src.models.schemas import (
    PlannerPlanRequest,
    PlannerPlanResponse,
    PlannerPreferenceResponse,
    PlannerPreferenceUpdateRequest,
)
from src.services.planner.workspace import build_workspace_plan, get_or_create_preferences, validate_preferences

router = APIRouter(prefix="/planner", tags=["planner"])


def _preference_response(row) -> PlannerPreferenceResponse:
    return PlannerPreferenceResponse.model_validate(row, from_attributes=True)


@router.get("/preferences", response_model=PlannerPreferenceResponse)
def get_preferences(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> PlannerPreferenceResponse:
    return _preference_response(get_or_create_preferences(db, user_id))


@router.patch("/preferences", response_model=PlannerPreferenceResponse)
def update_preferences(
    body: PlannerPreferenceUpdateRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> PlannerPreferenceResponse:
    row = get_or_create_preferences(db, user_id)
    for field in body.model_fields_set:
        setattr(row, field, getattr(body, field))
    try:
        validate_preferences(row)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return _preference_response(row)


@router.post("/generate", response_model=PlannerPlanResponse)
def generate_plan(
    body: PlannerPlanRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)
) -> PlannerPlanResponse:
    start = body.start or datetime.now(UTC)
    if start.tzinfo is None or start.utcoffset() is None:
        raise HTTPException(status_code=422, detail="start phải có timezone.")
    try:
        plan = build_workspace_plan(
            db,
            user_id,
            start=start,
            days=body.days,
            known_task_ids=body.known_task_ids,
            previous_blocks=body.previous_blocks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Scheduler trả dataclass bất biến để giữ core thuần Python. Response model
    # phải đọc attribute của các object lồng nhau thay vì đòi dict/Pydantic model.
    return PlannerPlanResponse.model_validate(plan, from_attributes=True)
