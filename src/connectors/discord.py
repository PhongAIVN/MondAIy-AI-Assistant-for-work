from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess

API_BASE = "https://discord.com/api/v10"
_PAGE_SIZE = 100
_MAX_MESSAGES = 1000
_TEXT_CHANNEL_TYPES = frozenset({0, 5})


class DiscordAPIError(ConnectorAPIError):
    """Discord API/configuration error safe to expose to API callers."""


def _dt(value: str | None) -> datetime | str:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return "unknown"


class DiscordConnector(BaseConnector):
    """Read Discord with a bot, bounded strictly by the user's source grants."""

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection, self._db = connection, db
        self._guild_by_channel: dict[str, str] = {}

    def _token(self) -> str:
        token = get_settings().discord_bot_token.strip()
        if not token:
            raise DiscordAPIError("DISCORD_BOT_TOKEN chưa cấu hình.")
        return token

    def _allowed(self) -> dict[str, SourceScope]:
        if self._db is None:
            raise DiscordAPIError("Discord chưa được cấp scope nguồn cho user này.")
        now = datetime.now(UTC)
        rows = self._db.execute(
            select(SourceScope).join(SourceScopeAccess, SourceScopeAccess.scope_id == SourceScope.id).where(
                SourceScope.provider == "discord",
                SourceScopeAccess.user_id == str(self._connection.user_id),
                SourceScopeAccess.status == "confirmed",
                SourceScopeAccess.granted_at <= now,
                or_(SourceScopeAccess.valid_to.is_(None), SourceScopeAccess.valid_to > now),
            )
        ).scalars().all()
        return {str(row.external_id): row for row in rows}

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict | list:
        for attempt in range(6):
            response = await client.get(f"{API_BASE}{path}", params=params)
            if response.status_code == 429 and attempt < 5:
                try:
                    delay = float(response.json().get("retry_after", 1))
                except (TypeError, ValueError):
                    delay = 1.0
                await asyncio.sleep(min(max(delay, 0), 60))
                continue
            if response.status_code in (401, 403):
                raise DiscordAPIError(f"Discord từ chối truy cập ({response.status_code}) tại {path}.")
            if response.status_code == 404:
                raise DiscordAPIError(f"Discord channel không tồn tại hoặc bot mất quyền tại {path}.")
            if response.status_code != 200:
                raise DiscordAPIError(f"Discord API lỗi {response.status_code} tại {path}.")
            return response.json()
        raise DiscordAPIError("Discord API vẫn rate limit sau 5 lần thử.")

    async def list_sources(self) -> list[Source]:
        allowed = self._allowed()
        if not allowed:
            raise DiscordAPIError("Discord chưa có SourceScopeAccess; cấp quyền channel trước khi đồng bộ.")
        token = self._token()
        result: list[Source] = []
        async with httpx.AsyncClient(headers={"Authorization": f"Bot {token}"}, timeout=15) as client:
            for channel_id, scope in allowed.items():
                channel = await self._get(client, f"/channels/{channel_id}")
                if not isinstance(channel, dict) or channel.get("type") not in _TEXT_CHANNEL_TYPES:
                    continue
                guild_id = str(channel.get("guild_id") or scope.guild_external_id or "")
                self._guild_by_channel[channel_id] = guild_id
                result.append(Source(id=channel_id, name=scope.name or f"#{channel.get('name') or channel_id}"))
        return result

    async def fetch_range(self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None) -> list[dict]:
        allowed = self._allowed()
        if source.id not in allowed:
            raise DiscordAPIError("Discord source chưa được cấp quyền cho user này.")
        token = self._token()
        result: list[dict] = []
        before: str | None = None
        start, end = time_from.astimezone(UTC), time_to.astimezone(UTC)
        async with httpx.AsyncClient(headers={"Authorization": f"Bot {token}"}, timeout=15) as client:
            while len(result) < _MAX_MESSAGES:
                params = {"limit": _PAGE_SIZE, **({"before": before} if before else {})}
                page = await self._get(client, f"/channels/{source.id}/messages", params=params)
                if not isinstance(page, list) or not page:
                    break
                stop = False
                for message in page:
                    sent = _dt(message.get("timestamp"))
                    if not isinstance(sent, datetime):
                        continue
                    if sent < start:
                        stop = True
                    elif sent <= end:
                        item = dict(message)
                        item["_guild_id"] = self._guild_by_channel.get(source.id) or allowed[source.id].guild_external_id or ""
                        result.append(item)
                        if on_item:
                            author = item.get("author") or {}
                            on_item(item, author.get("global_name") or author.get("username") or "Discord message")
                    if len(result) >= _MAX_MESSAGES:
                        break
                before = str(page[-1].get("id") or "")
                if stop or not before or len(page) < _PAGE_SIZE:
                    break
        return result

    def normalize(self, raw_item: dict, source: Source) -> dict:
        author = raw_item.get("author") or {}
        author_id = str(author.get("id") or "") or None
        text = str(raw_item.get("content") or "")
        return {"id": str(raw_item.get("id") or ""), "source_id": source.id, "provider": "discord", "thread_id": str((raw_item.get("message_reference") or {}).get("message_id") or raw_item.get("id") or ""), "author_id": author_id, "author_name": author.get("global_name") or author.get("username"), "subject": "", "to": [], "cc": [], "snippet": text[:200], "label_ids": [], "is_unread": False, "has_thread_change": bool(raw_item.get("message_reference")), "is_self": author_id == str(self._connection.provider_user_id or ""), "is_dm": False, "text": text, "normalized_text": " ".join(text.split()), "attachments": raw_item.get("attachments") or [], "sent_at": _dt(raw_item.get("timestamp")), "deep_link": self.deep_link(raw_item), "capture_mode": "discord_bot_api", "discord_channel_id": source.id, "discord_guild_id": raw_item.get("_guild_id") or self._guild_by_channel.get(source.id), "discord_message_id": str(raw_item.get("id") or ""), "discord_message_type": raw_item.get("type"), "discord_author_is_bot": bool(author.get("bot"))}

    def deep_link(self, raw_item: dict) -> str:
        return f"https://discord.com/channels/{raw_item.get('_guild_id') or '@me'}/{raw_item.get('channel_id') or ''}/{raw_item.get('id') or ''}"
