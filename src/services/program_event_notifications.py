"""Xếp thông báo thay đổi lịch chương trình mà không gọi mạng trong request."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.notification_preference import NotificationPreference
from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_event import ProgramEvent
from src.models.program_event_notice import ProgramEventNotice
from src.models.reminder import Reminder
from src.models.user import User


def _utc_iso(value: datetime) -> str:
    """Giữ timestamp có offset dù SQLite trả datetime không kèm tzinfo."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _revision_hash(event: ProgramEvent) -> str:
    """Băm đúng trạng thái người nhận sẽ thấy để dedupe bền vững qua restart."""
    payload = {
        "description": event.description,
        "endAt": event.ends_at.isoformat() if event.ends_at else None,
        "eventType": event.event_type,
        "host": event.host,
        "locationUrl": event.location_url,
        "startAt": event.starts_at.isoformat(),
        "status": event.status,
        "title": event.title,
        "visibility": event.visibility,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _eligible_user_ids(db: Session, event: ProgramEvent) -> list[str]:
    """Recipient do server suy ra từ quyền hiện tại và đồng ý sync trước đó."""
    if event.visibility != "program" or event.status != "published":
        return []

    rows = db.execute(
        select(User, NotificationPreference)
        .join(ProgramCalendarSync, ProgramCalendarSync.user_id == User.id.cast(String))
        .outerjoin(NotificationPreference, NotificationPreference.user_id == User.id.cast(String))
        .where(
            ProgramCalendarSync.program_event_id == event.id,
            User.is_active.is_(True),
            User.program_access_level == "A",
        )
    ).all()
    return [
        str(user.id)
        for user, preference in rows
        if preference is None or "calendar_changed" not in (preference.muted_kinds or [])
    ]


def queue_program_event_notices(
    db: Session,
    *,
    event: ProgramEvent,
    changed_fields: list[str],
    change_note: str,
    previous_starts_at: datetime | None = None,
    now: datetime | None = None,
) -> int:
    """Tạo reminder trong transaction hiện tại; delivery nền xử lý về sau."""
    now = now or datetime.now(UTC)
    revision_hash = _revision_hash(event)
    notification_count = 0
    time_changed = bool({"starts_at", "ends_at"} & set(changed_fields))
    change = "time_changed" if time_changed else "details_changed"
    if changed_fields == ["status"]:
        change = "published"

    for user_id in _eligible_user_ids(db, event):
        notice = ProgramEventNotice(
            user_id=user_id,
            program_event_id=event.id,
            revision_hash=revision_hash,
        )
        try:
            # Savepoint giữ transaction request dùng được khi hai admin bấm cùng lúc.
            with db.begin_nested():
                db.add(notice)
                db.flush()
        except IntegrityError:
            continue

        reminder = Reminder(
            task_id=None,
            user_id=user_id,
            kind="calendar_changed",
            milestone=f"program:{event.id}:{revision_hash[:20]}",
            scheduled_at=now,
            payload={
                "eventId": f"program:{event.id}",
                "programEventId": event.id,
                "title": event.title,
                "change": change,
                "changedFields": changed_fields,
                "changeNote": change_note,
                "startsAt": event.starts_at.isoformat(),
                "previousStartsAt": _utc_iso(previous_starts_at)
                if previous_starts_at is not None
                else None,
                "deepLink": "/notifications",
            },
        )
        db.add(reminder)
        db.flush()
        notice.reminder_id = reminder.id
        notification_count += 1

    return notification_count
