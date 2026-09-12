"""Dựng kế hoạch đồng bộ lịch chương trình sang lịch cá nhân (ADR-009).

Module này **không ghi gì lên Google**. Nó chỉ trả lời một câu: với user này,
mốc nào cần tạo mới, mốc nào nguồn đã đổi sau lần duyệt trước, mốc nào không
phải làm gì. Việc ghi nằm ở tầng API, sau khi user bấm đồng ý với đúng danh
sách mốc mà họ vừa nhìn thấy.

Tách như vậy để bước xem trước chạy được mà không cần kết nối Google, và để
test khẳng định được luật "không tự ghi" bằng cách gọi thẳng hàm này.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_event import ProgramEvent
from src.services.program_calendar import list_program_events

logger = logging.getLogger(__name__)

# Hạn daily lặp mỗi ngày; đổ hết vào lịch cá nhân là làm hỏng lịch của user chứ
# không phải giúp họ. Muốn có thì phải chọn tường minh ở bước xem trước.
DEFAULT_SYNC_TYPES = ("custom", "gate_deadline", "weekly_deadline")

# Trần một lần đồng bộ. Không phải giới hạn kỹ thuật mà là giới hạn của việc
# "user thật sự nhìn qua danh sách trước khi bấm đồng ý".
MAX_SYNC_ITEMS = 60


def event_content_hash(event: ProgramEvent) -> str:
    """Băm phần nội dung của mốc mà user nhìn thấy khi duyệt.

    Dùng chính các trường sẽ được ghi sang Google. Đổi bất kỳ trường nào trong
    số này thì event trong lịch của user đã lệch nguồn, và đó đúng là lúc phải
    hỏi lại.
    """
    payload = " ".join(
        [
            event.title,
            event.description,
            event.host or "",
            event.location_url or "",
            event.starts_at.isoformat(),
            event.ends_at.isoformat() if event.ends_at else "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SyncPlanItem:
    """Một dòng trong bảng xem trước mà user sẽ duyệt."""

    program_event_id: int
    external_id: str
    event_type: str
    title: str
    starts_at: datetime
    ends_at: datetime | None
    action: str  # create | update | unchanged
    reason: str
    content_hash: str


def plan_program_sync(
    db: Session,
    *,
    user_id: str,
    cohort_slug: str,
    event_types: list[str] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = MAX_SYNC_ITEMS,
) -> list[SyncPlanItem]:
    """Dựng danh sách mốc cần đồng bộ cho một user, không đụng tới Google.

    Cơ chế: lấy mốc chương trình trong khoảng (đã loại sự kiện riêng của nhóm ở
    tầng dưới), đối chiếu với bảng ánh xạ của chính user này rồi phân loại:

    - chưa có dòng ánh xạ → `create`
    - có ánh xạ nhưng băm nội dung khác băm đã duyệt → `update`
    - còn lại → `unchanged`
    """
    events = list_program_events(
        db,
        cohort_slug=cohort_slug,
        since=since,
        until=until,
        event_types=list(event_types or DEFAULT_SYNC_TYPES),
        include_team_scoped=False,
        limit=min(limit, MAX_SYNC_ITEMS),
    )
    if not events:
        return []

    existing = {
        row.program_event_id: row
        for row in db.scalars(
            select(ProgramCalendarSync).where(
                ProgramCalendarSync.user_id == user_id,
                ProgramCalendarSync.program_event_id.in_([event.id for event in events]),
            )
        )
    }

    plan: list[SyncPlanItem] = []
    for event in events:
        digest = event_content_hash(event)
        row = existing.get(event.id)
        if row is None:
            action, reason = "create", "Chưa có trong lịch của bạn."
        elif row.approved_content_hash != digest:
            action, reason = "update", "Ban tổ chức đã đổi mốc này sau lần bạn duyệt."
        else:
            action, reason = "unchanged", "Đã đồng bộ và khớp nguồn."
        plan.append(
            SyncPlanItem(
                program_event_id=event.id,
                external_id=event.external_id,
                event_type=event.event_type,
                title=event.title,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                action=action,
                reason=reason,
                content_hash=digest,
            )
        )
    return plan


def approved_events(
    db: Session,
    *,
    user_id: str,
    cohort_slug: str,
    program_event_ids: list[int],
) -> list[ProgramEvent]:
    """Lấy đúng những mốc user vừa duyệt, sau khi kiểm lại phía máy chủ.

    Không tin danh sách ID client gửi lên: lọc lại theo cohort và theo
    `visibility = program`. Thiếu bước này thì một ID nhóm khác gửi lên là ghi
    lịch trực của nhóm đó vào lịch cá nhân của người không thuộc nhóm.
    """
    if not program_event_ids:
        return []
    rows = db.scalars(
        select(ProgramEvent).where(
            ProgramEvent.id.in_(program_event_ids[:MAX_SYNC_ITEMS]),
            ProgramEvent.cohort_slug == cohort_slug,
            ProgramEvent.visibility == "program",
            ProgramEvent.status == "published",
        )
    ).all()
    bo_qua = set(program_event_ids) - {row.id for row in rows}
    if bo_qua:
        logger.warning(
            "Bỏ %d mốc user %s gửi lên nhưng không thuộc lịch chung của %s",
            len(bo_qua),
            user_id,
            cohort_slug,
        )
    return sorted(rows, key=lambda row: row.starts_at)


def get_sync_row(db: Session, *, user_id: str, program_event_id: int) -> ProgramCalendarSync | None:
    """Đọc ánh xạ hiện có của đúng user này cho một mốc."""
    return db.scalars(
        select(ProgramCalendarSync).where(
            ProgramCalendarSync.user_id == user_id,
            ProgramCalendarSync.program_event_id == program_event_id,
        )
    ).one_or_none()


def record_sync(
    db: Session,
    *,
    user_id: str,
    event: ProgramEvent,
    calendar_id: str,
    google_event_id: str,
    now: datetime,
) -> ProgramCalendarSync:
    """Ghi lại việc user đã duyệt và mốc đã nằm trong lịch của họ.

    Gọi sau khi ghi sang Google thành công. Ghi trước là tạo ra ánh xạ trỏ tới
    một event không tồn tại, và lần sau ta sẽ cố cập nhật nó rồi thất bại.
    """
    row = get_sync_row(db, user_id=user_id, program_event_id=event.id)
    digest = event_content_hash(event)
    if row is None:
        row = ProgramCalendarSync(
            user_id=user_id,
            program_event_id=event.id,
            calendar_id=calendar_id,
            event_id=google_event_id,
            approved_content_hash=digest,
            status="synced",
            approved_at=now,
            updated_at=now,
        )
        db.add(row)
        return row

    row.calendar_id = calendar_id
    row.event_id = google_event_id
    row.status = "synced"
    row.updated_at = now
    if row.approved_content_hash != digest:
        row.reapproved_count += 1
    row.approved_content_hash = digest
    return row


def describe_event(event: ProgramEvent) -> tuple[str, str]:
    """Dựng tiêu đề và mô tả sẽ ghi sang Google.

    Tiêu đề mang tiền tố cố định để user phân biệt được mốc do mondaiy ghi vào
    với sự kiện họ tự tạo — quan trọng khi họ muốn xoá hàng loạt.
    """
    title = f"[Chương trình] {event.title}".strip()
    parts = []
    if event.host:
        parts.append(f"Chủ trì: {event.host}")
    if event.description:
        parts.append(event.description)
    if event.location_url:
        parts.append(event.location_url)
    parts.append("Đồng bộ từ lịch chương trình bởi mondaiy.")
    return title[:500], "\n\n".join(parts)[:5000]
