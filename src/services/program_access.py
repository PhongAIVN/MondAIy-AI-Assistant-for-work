"""Program membership classification and its source-scope grants."""

import logging
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.connection import Connection
from src.models.evidence import SourceItem, SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User

logger = logging.getLogger(__name__)

ProgramAccessLevel = Literal["A", "B", "C"]


def _active_discord_grants(db: Session, user_id: str, now: datetime) -> list[SourceScopeAccess]:
    return list(
        db.scalars(
            select(SourceScopeAccess)
            .join(SourceScope, SourceScope.id == SourceScopeAccess.scope_id)
            .where(
                SourceScopeAccess.user_id == user_id,
                SourceScopeAccess.status == "confirmed",
                SourceScopeAccess.granted_at <= now,
                or_(SourceScopeAccess.valid_to.is_(None), SourceScopeAccess.valid_to > now),
                SourceScope.provider == "discord",
            )
        ).all()
    )


def _revoke_active_grants(db: Session, user_id: str, now: datetime) -> None:
    grants = db.scalars(
        select(SourceScopeAccess)
        .join(SourceScope, SourceScope.id == SourceScopeAccess.scope_id)
        .where(
            SourceScopeAccess.user_id == user_id,
            SourceScopeAccess.status == "confirmed",
            SourceScopeAccess.granted_at <= now,
            or_(SourceScopeAccess.valid_to.is_(None), SourceScopeAccess.valid_to > now),
            SourceScope.provider == "discord",
        )
    ).all()
    for grant in grants:
        grant.status = "revoked"
        grant.valid_to = now


def set_program_access(
    db: Session,
    user_id: str,
    level: ProgramAccessLevel,
    *,
    granted_by: str | None = None,
) -> None:
    """Set A/B/C and synchronise Discord source grants.

    A receives all currently ingested Discord program scopes. B and C receive
    none. This is the only automatic grant path; manual grants remain available
    for exceptional, audited admin cases.
    """
    user = db.get(User, int(user_id))
    if user is None:
        raise ValueError("User không tồn tại.")

    now = datetime.now(UTC)
    user.program_access_level = level
    active_grants = _active_discord_grants(db, str(user.id), now)
    if level == "A":
        scope_ids = db.scalars(select(SourceScope.id).where(SourceScope.provider == "discord")).all()
        active_scope_ids = {grant.scope_id for grant in active_grants}
        for scope_id in sorted(set(scope_ids) - active_scope_ids):
            db.add(
                SourceScopeAccess(
                    user_id=str(user.id),
                    scope_id=scope_id,
                    status="confirmed",
                    granted_by=granted_by,
                    granted_at=now,
                )
            )
    else:
        for grant in active_grants:
            grant.status = "revoked"
            grant.valid_to = now
    db.commit()


def classify_discord_identity(db: Session, user_id: str, discord_user_id: str) -> ProgramAccessLevel:
    """Classify an OAuth identity using the stable Discord snowflake ID."""
    found = db.scalar(
        select(SourceItem.id)
        .where(SourceItem.provider == "discord", SourceItem.author_external_id == discord_user_id)
        .limit(1)
    )
    level: ProgramAccessLevel = "A" if found is not None else "B"
    set_program_access(db, user_id, level)
    return level


def reconcile_program_access(db: Session, user_id: str) -> ProgramAccessLevel:
    """Derive A/B/C from the live Discord link and crawled author IDs.

    This repairs stale users created before identity classification existed and
    upgrades B to A when a later crawl first observes their Discord snowflake.
    """
    connection = db.scalar(
        select(Connection)
        .where(
            Connection.user_id == str(user_id),
            Connection.provider == "discord",
            Connection.status.notin_(["error", "disconnected"]),
        )
        .limit(1)
    )
    if connection is None or not connection.provider_user_id:
        expected: ProgramAccessLevel = "C"
    else:
        found = db.scalar(
            select(SourceItem.id)
            .where(
                SourceItem.provider == "discord",
                SourceItem.author_external_id == connection.provider_user_id,
            )
            .limit(1)
        )
        expected = "A" if found is not None else "B"

    # `users.id` là số nguyên, nên user_id không đổi ra số được thì chắc chắn
    # không trỏ tới user nào — coi như không tồn tại thay vì để ValueError của
    # int() bắn ra. Hai chỗ gọi hàm này là khởi động backend và bước cuối của
    # nạp crawl; một dòng connection rác không được phép giết cả hai.
    numeric_user_id = int(user_id) if str(user_id).lstrip("-").isdigit() else None
    user = db.get(User, numeric_user_id) if numeric_user_id is not None else None
    if user is None:
        raise ValueError("User không tồn tại.")
    now = datetime.now(UTC)
    active_scope_ids = {grant.scope_id for grant in _active_discord_grants(db, str(user.id), now)}
    desired_scope_ids = (
        set(db.scalars(select(SourceScope.id).where(SourceScope.provider == "discord")).all())
        if expected == "A"
        else set()
    )
    if user.program_access_level != expected or active_scope_ids != desired_scope_ids:
        set_program_access(db, str(user.id), expected)
    return expected


def reconcile_all_discord_connections(db: Session) -> dict[str, int]:
    """Reclassify every connected Discord identity after a crawl import."""
    user_ids = db.scalars(
        select(Connection.user_id).where(
            Connection.provider == "discord",
            Connection.status.notin_(["error", "disconnected"]),
        )
    ).all()
    counts = {"A": 0, "B": 0, "C": 0, "skipped": 0}
    for user_id in sorted(set(user_ids)):
        try:
            level = reconcile_program_access(db, user_id)
        except ValueError:
            # Connection trỏ tới user đã xoá hoặc user_id không phải số. Bỏ qua
            # đúng dòng đó rồi chạy tiếp: gặp thật khi nạp crawl, một dòng rác
            # làm hỏng cả bước phân loại quyền của mọi người còn lại.
            logger.warning("Bỏ qua connection Discord không khớp user nào: %r", user_id)
            counts["skipped"] += 1
            continue
        counts[level] += 1
    return counts
