import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.api import routes
from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.user import User
from src.services.auth import decode_token


def _stream_stub(result: dict, tokens: tuple[str, ...] = ()):
    async def stream(_graph, _state):
        yield {"event": "progress", "data": {"phase": "thinking"}}
        yield {"event": "progress", "data": {"phase": "responding"}}
        for delta in tokens:
            yield {"event": "token", "data": {"delta": delta}}
        yield {"event": "result", "data": result}

    return stream


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_requires_auth(client):
    """Không token thì không được hỏi — nếu không thì chưa biết giới hạn phạm vi
    đọc theo ai."""
    response = await client.post("/api/v1/chat", json={"message": "xin chào"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    email = f"test-chat-{uuid.uuid4().hex[:12]}@example.com"
    register = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = register.json()["accessToken"]

    response = await client.post("/api/v1/chat", json={"message": ""}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_chat_requires_authentication(client):
    response = await client.post("/api/v1/chat", json={"message": "hello"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_rejects_participant_after_daily_llm_quota(client):
    email = f"test-quota-{uuid.uuid4().hex[:12]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.llm_questions_used = get_settings().llm_questions_per_day
        # Quota day must be today for the counter to remain exhausted.
        user.llm_quota_day = datetime.now(ZoneInfo(get_settings().app_timezone)).date().isoformat()
        db.commit()

    mocked = AsyncMock(return_value={"response": "should not run", "analysis": ""})
    with patch("src.api.routes.agent.ainvoke", mocked):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Câu thứ 11"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Bạn hãy góp ý cải thiện sản phẩm của chúng tôi sẽ nhận được thêm 5 lượt dùng nữa. "
        "Đóng góp của bạn là quý giá với đội ngũ phát triển của chúng tôi."
    )
    mocked.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_admin_is_exempt_from_daily_llm_quota(client):
    email = f"test-admin-quota-{uuid.uuid4().hex[:12]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        user = db.get(User, user_id)
        user.role = "admin"
        user.llm_questions_used = 999
        db.commit()

    with patch(
        "src.api.routes.agent.ainvoke",
        AsyncMock(return_value={"response": "admin ok", "analysis": ""}),
    ):
        response = await client.post(
            "/api/v1/chat",
            json={"message": "Admin test"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["response"] == "admin ok"


@pytest.mark.asyncio
async def test_chat_stream_emits_tokens_and_done(client):
    email = f"test-chat-stream-{uuid.uuid4().hex[:12]}@example.com"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    token = registered.json()["accessToken"]
    with patch(
        "src.api.routes.stream_agent_execution",
        new=_stream_stub({"response": "stream answer", "analysis": ""}, ("stream ", "answer")),
    ):
        async with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            body = (await response.aread()).decode()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert "event: progress" in body
    assert '"phase": "thinking"' in body
    assert '"phase": "responding"' in body
    assert "event: token" in body
    assert '"delta": "stream "' in body
    assert '"delta": "answer"' in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_chat_stream_requires_authentication(client):
    response = await client.post("/api/v1/chat/stream", json={"message": "hello"})
    assert response.status_code == 401


def test_scope_ids_for_user_only_uses_connected_providers():
    # Regression: bản trước commit thẳng Connection/SourceScope vào DB dev rồi
    # không dọn — user_id dạng "scope-test-user-..." không phải số, sống mãi
    # trong bảng connections và làm sập lifespan app (reconcile_all_discord_
    # connections gọi int(user_id)). Test phải tự dọn rác của chính nó.
    suffix = uuid.uuid4().hex
    user_id = f"scope-test-user-{suffix}"
    other_user_id = f"scope-test-other-user-{suffix}"
    connections = [
        Connection(user_id=user_id, provider="discord", status="connected_ready"),
        Connection(user_id=other_user_id, provider="google", status="connected_ready"),
    ]
    scopes = [
        SourceScope(provider="discord", external_id=f"scope-test-discord-{suffix}"),
        SourceScope(provider="google", external_id=f"scope-test-google-{suffix}"),
    ]
    with SessionLocal() as db:
        db.add_all([*connections, *scopes])
        db.commit()
        try:
            ids = routes._scope_ids_for_user(db, user_id)
            matched_scopes = db.query(SourceScope).filter(SourceScope.id.in_(ids)).all()

            # DB test trên self-hosted runner có thể đã chứa scope Discord từ test khác;
            # điều cần chứng minh là provider của user được nhận và provider user khác
            # không lọt vào, không phải toàn DB chỉ có đúng một scope Discord.
            by_external_id = {scope.external_id: scope.provider for scope in matched_scopes}
            assert by_external_id[f"scope-test-discord-{suffix}"] == "discord"
            assert f"scope-test-google-{suffix}" not in by_external_id
        finally:
            for connection in connections:
                db.delete(connection)
            for scope in scopes:
                db.delete(scope)
            db.commit()


@pytest.mark.asyncio
async def test_agent_status(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
