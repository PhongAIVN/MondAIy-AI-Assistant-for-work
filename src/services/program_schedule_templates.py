"""Sinh mốc lịch chương trình từ mẫu lặp theo cohort."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.program_event import ProgramEvent
from src.models.program_schedule_template import ProgramScheduleTemplate
from src.services.program_calendar import TEAM_SCOPED_TYPES
from src.services.program_cohorts import normalize_program_cohort_slug


def parse_weekdays(value: str) -> tuple[int, ...]:
    days = tuple(sorted({int(part) for part in value.split(",") if part.strip()}))
    if not days or any(day < 0 or day > 6 for day in days):
        raise ValueError("weekdays phải chứa các giá trị từ 0 đến 6.")
    return days


def parse_clock(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Giờ phải có định dạng HH:MM.") from exc
    if parsed.second or parsed.microsecond:
        raise ValueError("Giờ chỉ hỗ trợ định dạng HH:MM.")
    return parsed


def _event_id(template: ProgramScheduleTemplate, occurrence: date) -> str:
    return f"template:{template.id}:{occurrence.isoformat()}"


def generate_template_events(
    db: Session,
    template: ProgramScheduleTemplate,
    *,
    now: datetime | None = None,
) -> list[ProgramEvent]:
    """Upsert mốc theo template, giữ cohort và trạng thái phát hành."""
    template.cohort_slug = normalize_program_cohort_slug(template.cohort_slug)
    weekdays = parse_weekdays(template.weekdays)
    start_clock = parse_clock(template.start_time)
    end_clock = parse_clock(template.end_time)
    if end_clock <= start_clock:
        raise ValueError("endTime phải sau startTime trong cùng ngày.")
    observed = now or datetime.now(UTC)
    local_zone = ZoneInfo(get_settings().app_timezone)
    visibility = "team" if template.event_type in TEAM_SCOPED_TYPES else "program"
    changed: list[ProgramEvent] = []
    current = template.starts_on
    while current <= template.ends_on:
        if current.weekday() in weekdays:
            starts_at = datetime.combine(current, start_clock, tzinfo=local_zone).astimezone(UTC)
            ends_at = datetime.combine(current, end_clock, tzinfo=local_zone).astimezone(UTC)
            external_id = _event_id(template, current)
            event = db.scalar(
                select(ProgramEvent).where(
                    ProgramEvent.cohort_slug == template.cohort_slug,
                    ProgramEvent.external_id == external_id,
                )
            )
            digest = hashlib.sha256(
                f"{template.cohort_slug}|{external_id}|{template.title}|{starts_at.isoformat()}|{ends_at.isoformat()}".encode()
            ).hexdigest()
            if event is None:
                event = ProgramEvent(
                    cohort_slug=template.cohort_slug,
                    external_id=external_id,
                    event_type=template.event_type,
                    visibility=visibility,
                    title=template.title,
                    description=template.description,
                    host=template.host,
                    location_url=template.location_url,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    content_hash=digest,
                    observed_at=observed,
                    origin="template",
                    status="published" if template.published else "draft",
                    published_at=observed if template.published else None,
                )
                db.add(event)
            else:
                event.title = template.title
                event.description = template.description
                event.host = template.host
                event.location_url = template.location_url
                event.event_type = template.event_type
                event.visibility = visibility
                event.starts_at = starts_at
                event.ends_at = ends_at
                event.content_hash = digest
                event.observed_at = observed
                event.status = "published" if template.published else "draft"
                event.published_at = observed if template.published else None
            changed.append(event)
        current += timedelta(days=1)
    db.flush()
    return changed
