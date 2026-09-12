import uuid

import pytest
from sqlalchemy import select

from src.db import SessionLocal
from src.models.connection import Connection
from src.services.connections import discord, google
from src.services.crypto import encrypt_token


def _unique_email() -> str:
    return f"disconnect-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _seed_connection(user_id: str, provider: str, access_token: str | None = "plain-access-token") -> None:
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider=provider,
                account_label=f"{provider}-account",
                access_token_encrypted=encrypt_token(access_token) if access_token else None,
            )
        )
        db.commit()
    finally:
        db.close()


def _connection_row(user_id: str, provider: str) -> Connection | None:
    db = SessionLocal()
    try:
        return db.execute(
            select(Connection).where(Connection.user_id == user_id, Connection.provider == provider)
        ).scalar_one_or_none()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_disconnect_google_revokes_token_then_deletes_connection(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_connection(user_id, "google")

    revoked_with: list[str] = []

    async def fake_revoke_token(access_token: str) -> None:
        revoked_with.append(access_token)

    monkeypatch.setattr(google, "revoke_token", fake_revoke_token)

    response = await client.post(
        "/api/v1/connections/google/disconnect", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert revoked_with == ["plain-access-token"]
    assert _connection_row(user_id, "google") is None


@pytest.mark.asyncio
async def test_disconnect_discord_revokes_token_then_deletes_connection(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_connection(user_id, "discord")

    revoked_with: list[str] = []

    async def fake_revoke_token(access_token: str) -> None:
        revoked_with.append(access_token)

    monkeypatch.setattr(discord, "revoke_token", fake_revoke_token)

    response = await client.post(
        "/api/v1/connections/discord/disconnect", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert revoked_with == ["plain-access-token"]
    assert _connection_row(user_id, "discord") is None


@pytest.mark.asyncio
async def test_disconnect_still_deletes_connection_when_provider_revoke_fails(client, monkeypatch):
    # Provider that revoke thất bại (mạng rớt, token đã hết hạn từ trước...)
    # KHÔNG được chặn việc xoá connection local — user bấm Ngắt kết nối phải
    # luôn thấy hiệu lực ngay trong app.
    user_id, token = await _register(client)
    _seed_connection(user_id, "google")

    async def failing_revoke_token(_access_token: str) -> None:
        raise RuntimeError("mạng rớt")

    monkeypatch.setattr(google, "revoke_token", failing_revoke_token)

    response = await client.post(
        "/api/v1/connections/google/disconnect", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert _connection_row(user_id, "google") is None


@pytest.mark.asyncio
async def test_disconnect_jira_skips_revoke_no_public_endpoint_exists(client, monkeypatch):
    # Jira (Atlassian OAuth 2.0 3LO) khong co API revoke cong khai - dung
    # gia lap revoke_token de dam bao connections.py KHONG tu bia ra 1 lenh
    # goi khong ton tai cho provider nay.
    user_id, token = await _register(client)
    _seed_connection(user_id, "jira")

    response = await client.post(
        "/api/v1/connections/jira/disconnect", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert _connection_row(user_id, "jira") is None


@pytest.mark.asyncio
async def test_disconnect_skips_revoke_when_no_token_stored(client, monkeypatch):
    user_id, token = await _register(client)
    _seed_connection(user_id, "google", access_token=None)

    called = False

    async def fake_revoke_token(_access_token: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(google, "revoke_token", fake_revoke_token)

    response = await client.post(
        "/api/v1/connections/google/disconnect", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204
    assert called is False
    assert _connection_row(user_id, "google") is None
