"""Ngắt kết nối phải dọn luôn cache thô của provider đó — không thì chatbot
vẫn trả lời bằng dữ liệu nguồn đã ngắt (Message tra thẳng theo user_id+provider
trong _cached_gmail_messages, SourceScopeAccess cấp quyền đọc chunk Discord,
cả hai đều không kiểm tra Connection còn sống). Trước fix này, disconnect chỉ
xoá dòng Connection, hai bảng trên còn nguyên."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.message import Message
from src.models.source_scope_access import SourceScopeAccess


def _unique_email() -> str:
    return f"purge-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_disconnect_google_purges_cached_gmail_messages(client):
    user_id, token = await _register(client)

    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready"))
        db.add(
            Message(
                user_id=user_id,
                provider="google",
                source_id="INBOX",
                external_id=uuid.uuid4().hex,
                text="deadline noi bo",
                sent_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.post("/api/v1/connections/google/disconnect", headers=_auth(token))
    assert response.status_code == 204

    db = SessionLocal()
    try:
        remaining = db.execute(
            select(Message).where(Message.user_id == user_id, Message.provider == "google")
        ).scalars().all()
        assert remaining == []
    finally:
        db.close()


@pytest.mark.asyncio
async def test_disconnect_discord_revokes_source_scope_access(client):
    user_id, token = await _register(client)

    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="discord", status="connected_ready"))
        scope = SourceScope(provider="discord", external_id=f"chan-{uuid.uuid4().hex[:8]}", name="general")
        db.add(scope)
        db.flush()
        access = SourceScopeAccess(user_id=user_id, scope_id=scope.id, status="confirmed")
        db.add(access)
        db.commit()
        access_id = access.id
    finally:
        db.close()

    response = await client.post("/api/v1/connections/discord/disconnect", headers=_auth(token))
    assert response.status_code == 204

    db = SessionLocal()
    try:
        row = db.get(SourceScopeAccess, access_id)
        assert row is not None  # audit trail: revoked, not deleted
        assert row.status != "confirmed"
        assert row.valid_to is not None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_disconnect_leaves_other_providers_cache_untouched(client):
    user_id, token = await _register(client)

    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", status="connected_ready"))
        db.add(
            Message(
                user_id=user_id,
                provider="jira",
                source_id="PROJ",
                external_id=uuid.uuid4().hex,
                text="unrelated jira ticket",
                sent_at=datetime.now(UTC),
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.post("/api/v1/connections/google/disconnect", headers=_auth(token))
    assert response.status_code == 204

    db = SessionLocal()
    try:
        remaining = db.execute(
            select(Message).where(Message.user_id == user_id, Message.provider == "jira")
        ).scalars().all()
        assert len(remaining) == 1
    finally:
        db.close()
