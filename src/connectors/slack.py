from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.services.connections import slack as slack_oauth

logger = logging.getLogger(__name__)

API_BASE = "https://slack.com/api"

# Cùng tinh thần _MAX_ISSUES bên jira.py/_MAX_MESSAGE_IDS bên gmail.py — cap
# ngay từ đầu, không đợi phát hiện thiếu.
_MAX_MESSAGES = 1000
_PAGE_SIZE = 200
_MAX_RATE_LIMIT_RETRIES = 5

# subtype hệ thống/tự động — khớp bước 3 Hard Filter trong slack-detail.drawio
# (DROP tuyệt đối, không tính điểm). Để connector KHÔNG lọc — hard_filter()
# trong slack_rules.py mới là nơi quyết định DROP, connector chỉ chuẩn hoá.
_MENTION_RE = re.compile(r"<@([A-Z0-9]+)>")
_CHANNEL_REF_RE = re.compile(r"<#([A-Z0-9]+)\|([^>]*)>")
_LINK_RE = re.compile(r"<(https?://[^|>]+)\|([^>]*)>")
_BARE_LINK_RE = re.compile(r"<(https?://[^>]+)>")


class SlackAPIError(ConnectorAPIError):
    """Lỗi gọi Slack API — message đã làm sạch, an toàn để lộ ra route/SSE."""


class SlackConnector(BaseConnector):
    """KHÔNG hỗ trợ real-time Events API/Socket Mode (xem risk1 trong
    slack-detail.drawio) — BaseConnector chỉ có fetch_range(time_from,
    time_to), mô hình pull. Chỉ ingest message TOP-LEVEL trong channel/DM
    qua conversations.history; reply trong thread KHÔNG được backfill ở bản
    này (cần conversations.replies riêng theo từng thread_ts — theo dõi ở
    TODO(OD-SLACK1), việc sau, không phải thiếu sót khi review diff này)."""

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db
        self._user_name_cache: dict[str, str] = {}

    async def _access_token(self) -> str:
        try:
            return await slack_oauth.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise SlackAPIError(f"Không lấy được access token Slack: {exc}") from exc

    async def _call(self, client: httpx.AsyncClient, method: str, params: dict) -> dict:
        """Slack API luôn trả HTTP 200 kèm {"ok": false, "error": "..."} khi
        lỗi logic (khác Jira/Gmail trả HTTP status code lỗi) — chỉ 429 mới là
        lỗi tầng HTTP thật, cần đọc Retry-After."""
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.get(f"{API_BASE}/{method}", params=params)
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                logger.warning(
                    "Slack API rate limit tại %s, chờ %.1fs (lần %d/%d)",
                    method,
                    wait_seconds,
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue
            body = response.json()
            if not body.get("ok"):
                raise SlackAPIError(f"Slack API lỗi tại {method}: {body.get('error', 'unknown_error')}")
            return body
        raise SlackAPIError(f"Slack API vẫn rate limit sau {_MAX_RATE_LIMIT_RETRIES} lần thử tại {method}")

    async def _resolve_user_name(self, client: httpx.AsyncClient, user_id: str) -> str:
        cached = self._user_name_cache.get(user_id)
        if cached is not None:
            return cached
        try:
            body = await self._call(client, "users.info", {"user": user_id})
        except SlackAPIError:
            self._user_name_cache[user_id] = user_id
            return user_id
        profile = body.get("user") or {}
        name = profile.get("real_name") or profile.get("name") or user_id
        self._user_name_cache[user_id] = name
        return name

    async def _parse_mrkdwn(self, client: httpx.AsyncClient, text: str) -> str:
        """<@U123> -> tên hiển thị (cache), <#C123|ten-kenh> -> #ten-kenh,
        <url|label> -> "label (url)" — khớp bước 2 Normalization trong
        slack-detail.drawio."""
        for user_id in set(_MENTION_RE.findall(text)):
            name = await self._resolve_user_name(client, user_id)
            text = text.replace(f"<@{user_id}>", f"@{name}")
        text = _CHANNEL_REF_RE.sub(lambda m: f"#{m.group(2)}", text)
        text = _LINK_RE.sub(lambda m: f"{m.group(2)} ({m.group(1)})", text)
        text = _BARE_LINK_RE.sub(lambda m: m.group(1), text)
        return text

    async def _channel_type(self, client: httpx.AsyncClient, channel_id: str) -> str:
        body = await self._call(client, "conversations.info", {"channel": channel_id})
        info = body.get("channel") or {}
        if info.get("is_im"):
            return "im"
        if info.get("is_mpim"):
            return "mpim"
        if info.get("is_private"):
            return "private_channel"
        return "public_channel"

    async def list_sources(self) -> list[Source]:
        token = await self._access_token()
        sources: list[Source] = []
        cursor: str | None = None
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while True:
                params = {
                    "types": "public_channel,private_channel,im,mpim",
                    "exclude_archived": "true",
                    "limit": _PAGE_SIZE,
                }
                if cursor:
                    params["cursor"] = cursor
                body = await self._call(client, "conversations.list", params)
                for channel in body.get("channels", []):
                    if channel.get("is_archived"):
                        continue
                    if channel.get("is_channel") or channel.get("is_group"):
                        if not channel.get("is_member", True):
                            continue  # chỉ liệt kê channel bot/user đã tham gia
                        sources.append(Source(id=channel["id"], name=f"#{channel.get('name', channel['id'])}"))
                    elif channel.get("is_im"):
                        other_user = channel.get("user")
                        name = await self._resolve_user_name(client, other_user) if other_user else channel["id"]
                        sources.append(Source(id=channel["id"], name=f"DM · {name}"))
                    elif channel.get("is_mpim"):
                        purpose = (channel.get("purpose") or {}).get("value") or channel.get("name", channel["id"])
                        sources.append(Source(id=channel["id"], name=f"Group DM · {purpose}"))
                cursor = (body.get("response_metadata") or {}).get("next_cursor")
                if not cursor:
                    break
        return sources

    async def fetch_range(
        self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None
    ) -> list[dict]:
        token = await self._access_token()
        messages: list[dict] = []
        cursor: str | None = None
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            channel_type = await self._channel_type(client, source.id)
            while len(messages) < _MAX_MESSAGES:
                params = {
                    "channel": source.id,
                    "oldest": f"{time_from.timestamp():.6f}",
                    "latest": f"{time_to.timestamp():.6f}",
                    "inclusive": "true",
                    "limit": _PAGE_SIZE,
                }
                if cursor:
                    params["cursor"] = cursor
                body = await self._call(client, "conversations.history", params)
                batch = body.get("messages", [])
                if not batch:
                    break
                for message in batch:
                    if len(messages) >= _MAX_MESSAGES:
                        break
                    raw_text = message.get("text", "")
                    # conversations.history KHÔNG trả field "channel" trong
                    # từng message (ngữ cảnh channel ngầm định theo tham số
                    # gọi API) — gắn thủ công để normalize()/deep_link() (sync,
                    # không gọi lại API được) tự đủ dữ liệu.
                    message["channel"] = source.id
                    message["_channel_type"] = channel_type
                    message["_parsed_text"] = await self._parse_mrkdwn(client, raw_text)
                    author_id = message.get("user") or message.get("bot_id")
                    message["_author_name"] = (
                        await self._resolve_user_name(client, author_id)
                        if message.get("user")
                        else (message.get("username") or author_id or "")
                    )
                    messages.append(message)
                    if on_item is not None:
                        on_item(message, raw_text[:80] or "(không có nội dung)")
                cursor = (body.get("response_metadata") or {}).get("next_cursor")
                if not cursor:
                    break
            else:
                logger.warning(
                    "Slack message list chạm cap %d cho channel %s — có thể còn message chưa liệt kê.",
                    _MAX_MESSAGES,
                    source.id,
                )
        return messages[:_MAX_MESSAGES]

    def normalize(self, raw_item: dict, source: Source) -> dict:
        ts = raw_item.get("ts", "")
        thread_ts = raw_item.get("thread_ts")
        channel_type = raw_item.get("_channel_type", "public_channel")
        is_dm = channel_type in ("im", "mpim")
        author_id = raw_item.get("user") or raw_item.get("bot_id")
        provider_user_id = self._connection.provider_user_id or ""
        is_self = bool(author_id) and author_id == provider_user_id
        mentions_current_user = bool(provider_user_id) and f"<@{provider_user_id}>" in raw_item.get("text", "")
        text = raw_item.get("_parsed_text", raw_item.get("text", ""))
        sent_at = _parse_slack_ts(ts)

        return {
            "id": f"{source.id}:{ts}",
            "source_id": source.id,
            "provider": "slack",
            "thread_id": thread_ts or ts,
            "author_id": author_id,
            "author_name": raw_item.get("_author_name") or author_id,
            # Slack không có field tiêu đề sẵn như Jira summary — title được
            # SUY RA ở bước Extraction (slack_rules.py:extract_evidence),
            # không đặt sẵn ở đây.
            "subject": "",
            "to": [],
            "cc": [],
            "snippet": text[:200],
            "label_ids": [],
            "is_unread": False,
            "has_thread_change": bool(thread_ts and thread_ts != ts),
            "is_self": is_self,
            "is_dm": is_dm,
            "text": text,
            "normalized_text": _normalize_message_text(text),
            "attachments": [],
            "sent_at": sent_at,
            "deep_link": self.deep_link(raw_item),
            "capture_mode": "slack_api",
            # Field có cấu trúc riêng cho rule engine (src/services/slack_rules.py)
            "slack_channel_id": source.id,
            "slack_channel_type": channel_type,
            "slack_message_ts": ts,
            "slack_thread_ts": thread_ts,
            "slack_subtype": raw_item.get("subtype"),
            "slack_mentions_current_user": mentions_current_user,
            # Giữ chỗ cho rule "reaction cần phản hồi" (bước 4 slack-detail.drawio)
            # — chưa có trọng số chốt trong RULE_CONFIG bước 5, xem
            # src/services/slack_rules.py.
            "slack_reactions": tuple(r.get("name", "") for r in raw_item.get("reactions", [])),
        }

    def deep_link(self, raw_item: dict) -> str:
        channel_id = raw_item.get("channel") or ""
        ts_no_dot = (raw_item.get("ts") or "").replace(".", "")
        thread_ts = raw_item.get("thread_ts")
        suffix = f"?thread_ts={thread_ts}" if thread_ts and thread_ts != raw_item.get("ts") else ""

        team_domain = self._connection.account_label
        if team_domain:
            return f"https://{team_domain}.slack.com/archives/{channel_id}/p{ts_no_dot}{suffix}"
        team_id = self._connection.external_site_id
        if team_id:
            return f"https://app.slack.com/client/{team_id}/{channel_id}/p{ts_no_dot}{suffix}"
        return f"https://app.slack.com/client/unknown/{channel_id}/p{ts_no_dot}{suffix}"


def _normalize_message_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()


def _parse_slack_ts(ts: str) -> datetime | str:
    """message_ts dạng "1234567890.123456" — epoch giây có phần thập phân
    định danh duy nhất trong 1 channel. Không phải chuỗi ISO như Jira."""
    if not ts:
        return "unknown"
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (ValueError, OverflowError):
        return "unknown"
