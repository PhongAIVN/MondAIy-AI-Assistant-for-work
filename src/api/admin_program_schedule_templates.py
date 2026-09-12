"""Quản trị mẫu lịch lặp theo cohort."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import require_admin
from src.db import get_db
from src.models.program_schedule_template import ProgramScheduleTemplate
from src.models.schemas import AdminProgramScheduleTemplateRequest, AdminProgramScheduleTemplateRow
from src.models.user import User
from src.services.program_cohorts import resolve_program_cohort_slug
from src.services.program_schedule_templates import generate_template_events, parse_weekdays

router = APIRouter(
    prefix="/admin/program-schedule-templates",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

def _template_cohort(value: str | None) -> str:
    try:
        return resolve_program_cohort_slug(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _row(template: ProgramScheduleTemplate) -> AdminProgramScheduleTemplateRow:
    return AdminProgramScheduleTemplateRow(
        id=template.id,
        cohort_slug=template.cohort_slug,
        title=template.title,
        description=template.description,
        host=template.host,
        location_url=template.location_url,
        event_type=template.event_type,
        weekdays=list(parse_weekdays(template.weekdays)),
        start_time=template.start_time,
        end_time=template.end_time,
        starts_on=template.starts_on,
        ends_on=template.ends_on,
        active=template.active,
        published=template.published,
    )


@router.get("", response_model=list[AdminProgramScheduleTemplateRow])
def list_templates(db: Session = Depends(get_db)) -> list[AdminProgramScheduleTemplateRow]:
    rows = db.scalars(
        select(ProgramScheduleTemplate)
        .order_by(ProgramScheduleTemplate.starts_on.asc(), ProgramScheduleTemplate.id.asc())
    ).all()
    return [_row(item) for item in rows]


@router.post("", response_model=AdminProgramScheduleTemplateRow, status_code=201)
def create_template(
    payload: AdminProgramScheduleTemplateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminProgramScheduleTemplateRow:
    cohort = _template_cohort(payload.cohort_slug)
    template = ProgramScheduleTemplate(
        cohort_slug=cohort,
        title=payload.title,
        description=payload.description,
        host=payload.host,
        location_url=payload.location_url,
        event_type=payload.event_type,
        weekdays=",".join(str(day) for day in sorted(payload.weekdays)),
        start_time=payload.start_time,
        end_time=payload.end_time,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        active=payload.active,
        published=payload.published,
        created_by=str(actor.id),
    )
    db.add(template)
    db.flush()
    if template.active:
        generate_template_events(db, template)
    db.commit()
    db.refresh(template)
    return _row(template)


@router.post("/{template_id}/publish", response_model=AdminProgramScheduleTemplateRow)
def publish_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> AdminProgramScheduleTemplateRow:
    template = db.get(ProgramScheduleTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Mẫu lịch không tồn tại.")
    template.published = True
    template.active = True
    generate_template_events(db, template)
    db.commit()
    db.refresh(template)
    return _row(template)
