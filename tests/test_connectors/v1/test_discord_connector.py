from datetime import UTC, datetime

import pytest

from src.connectors.base import Source
from src.connectors.discord import DiscordAPIError, DiscordConnector
from src.connectors.registry import resolve_connector


class Connection:
    user_id = "user-1"
    provider_user_id = "author-1"


def test_discord_connector_fails_closed_without_scope_db():
    connector = DiscordConnector(Connection(), None)
    with pytest.raises(DiscordAPIError, match="chưa được cấp scope"):
        connector._allowed()


@pytest.mark.asyncio
async def test_fetch_rejects_source_not_granted(monkeypatch):
    connector = DiscordConnector(Connection(), object())
    monkeypatch.setattr(connector, "_allowed", lambda: {})
    with pytest.raises(DiscordAPIError, match="chưa được cấp quyền"):
        await connector.fetch_range(Source(id="private", name="Private"), datetime.now(UTC), datetime.now(UTC))


def test_normalize_and_deep_link_keep_discord_identity():
    connector = DiscordConnector(Connection(), object())
    raw = {
        "id": "m-1",
        "channel_id": "c-1",
        "_guild_id": "g-1",
        "timestamp": "2026-08-24T01:02:03.000Z",
        "content": "Nộp báo cáo",
        "author": {"id": "author-1", "username": "an", "global_name": "An"},
    }
    result = connector.normalize(raw, Source(id="c-1", name="#general"))
    assert result["provider"] == "discord"
    assert result["is_self"] is True
    assert result["deep_link"] == "https://discord.com/channels/g-1/c-1/m-1"
    assert result["capture_mode"] == "discord_bot_api"


def test_registry_resolves_discord_connector():
    connector_cls, source_id = resolve_connector("discord", "channel-1")
    assert connector_cls is DiscordConnector
    assert source_id == "channel-1"
