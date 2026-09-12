"""Exact, author-safe reads over the separately crawled Discord database."""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.models.evidence import SourceItem, SourceScope


@dataclass(frozen=True)
class DiscordMessage:
    message_id: str
    channel: str
    content: str
    occurred_at: datetime
    deep_link: str | None


@dataclass(frozen=True)
class DiscordChannelActivity:
    channel: str
    message_count: int
    last_message_at: datetime


def _message_filters(
    scope_ids: list[int],
    author_external_id: str,
    since: datetime | None,
    until: datetime | None,
) -> list:
    filters = [
        SourceItem.provider == "discord",
        SourceItem.scope_id.in_(scope_ids),
        SourceItem.author_external_id == author_external_id,
    ]
    if since is not None:
        filters.append(SourceItem.source_updated_at >= since)
    if until is not None:
        filters.append(SourceItem.source_updated_at <= until)
    return filters


def search_my_discord_messages(
    engine: Engine,
    *,
    scope_ids: list[int],
    author_external_id: str,
    query: str = "",
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 12,
) -> list[DiscordMessage]:
    """Return exact messages by the authenticated Discord author only."""
    if not scope_ids or not author_external_id:
        return []
    filters = _message_filters(scope_ids, author_external_id, since, until)
    terms = [term for term in re.split(r"\W+", query, flags=re.UNICODE) if len(term) >= 2]
    if terms:
        filters.append(or_(*(SourceItem.content.ilike(f"%{term}%") for term in terms)))
    statement = (
        select(SourceItem, SourceScope.name, SourceScope.external_id)
        .join(SourceScope, SourceScope.id == SourceItem.scope_id)
        .where(*filters)
        .order_by(SourceItem.source_updated_at.desc(), SourceItem.id.desc())
        .limit(max(1, min(limit, 50)))
    )
    with Session(engine) as db:
        rows = db.execute(statement).all()
    return [
        DiscordMessage(
            message_id=item.external_id,
            channel=channel_name or channel_id,
            content=item.content,
            occurred_at=item.source_updated_at,
            deep_link=item.deep_link,
        )
        for item, channel_name, channel_id in rows
    ]


def get_my_discord_activity(
    engine: Engine,
    *,
    scope_ids: list[int],
    author_external_id: str,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 10,
) -> list[DiscordChannelActivity]:
    """Summarize the authenticated author's activity without exposing others."""
    if not scope_ids or not author_external_id:
        return []
    statement = (
        select(
            SourceScope.name,
            SourceScope.external_id,
            func.count(SourceItem.id),
            func.max(SourceItem.source_updated_at),
        )
        .join(SourceScope, SourceScope.id == SourceItem.scope_id)
        .where(*_message_filters(scope_ids, author_external_id, since, until))
        .group_by(SourceScope.id, SourceScope.name, SourceScope.external_id)
        .order_by(func.count(SourceItem.id).desc(), func.max(SourceItem.source_updated_at).desc())
        .limit(max(1, min(limit, 50)))
    )
    with Session(engine) as db:
        rows = db.execute(statement).all()
    return [
        DiscordChannelActivity(
            channel=channel_name or channel_id,
            message_count=message_count,
            last_message_at=last_message_at,
        )
        for channel_name, channel_id, message_count, last_message_at in rows
    ]
