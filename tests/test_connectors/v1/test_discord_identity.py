from __future__ import annotations

import httpx
import pytest

from src.services.connections import discord


@pytest.mark.asyncio
async def test_fetch_account_identity_keeps_stable_discord_id(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers):
            assert url == discord.ME_URL
            assert headers == {"Authorization": "Bearer access-token"}
            return httpx.Response(
                200,
                json={"id": "123456789012345678", "username": "anhoaithai", "discriminator": "0"},
            )

    monkeypatch.setattr(discord.httpx, "AsyncClient", FakeAsyncClient)

    identity = await discord.fetch_account_identity("access-token")

    assert identity is not None
    assert identity.user_id == "123456789012345678"
    assert identity.label == "anhoaithai"


@pytest.mark.asyncio
async def test_fetch_account_identity_rejects_profile_without_id(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers):
            return httpx.Response(200, json={"username": "anhoaithai"})

    monkeypatch.setattr(discord.httpx, "AsyncClient", FakeAsyncClient)

    assert await discord.fetch_account_identity("access-token") is None
