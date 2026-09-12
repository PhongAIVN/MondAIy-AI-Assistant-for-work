import uuid
from unittest.mock import AsyncMock, patch

import pytest


async def _register(client, prefix: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct-horse-1",
        },
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _stream_from(fake_agent):
    async def stream(_graph, state):
        yield {"event": "progress", "data": {"phase": "thinking"}}
        result = await fake_agent(state)
        yield {"event": "progress", "data": {"phase": "responding"}}
        yield {"event": "token", "data": {"delta": result.get("response", "")}}
        yield {"event": "result", "data": result}

    return stream


@pytest.mark.asyncio
async def test_profile_memory_requires_authentication(client):
    response = await client.get("/api/v1/memory/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_name_survives_new_conversation_and_is_isolated_between_users(client):
    token_a = await _register(client, "memory-a")
    token_b = await _register(client, "memory-b")

    async def fake_agent(state):
        name = state.get("user_profile", {}).get("display_name")
        response = f"Bạn tên là {name}." if name else "Mình chưa biết tên bạn."
        return {"response": response, "analysis": ""}

    agent = AsyncMock(side_effect=fake_agent)
    with patch("src.api.conversations.agent.ainvoke", agent):
        conv_a1 = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]
        first = await client.post(
            f"/api/v1/conversations/{conv_a1}/messages",
            json={"message": "Tôi tên là An."},
            headers=_auth(token_a),
        )
        assert first.status_code == 200

        # Conversation mới không có history, chỉ còn long-term profile.
        conv_a2 = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]
        recalled = await client.post(
            f"/api/v1/conversations/{conv_a2}/messages",
            json={"message": "Tôi tên gì?"},
            headers=_auth(token_a),
        )
        assert recalled.json()["response"] == "Bạn tên là An."

        # User B hỏi cùng câu nhưng không được nhìn thấy profile của A.
        conv_b = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_b))).json()["id"]
        denied = await client.post(
            f"/api/v1/conversations/{conv_b}/messages",
            json={"message": "Tôi tên gì?"},
            headers=_auth(token_b),
        )
        assert denied.json()["response"] == "Mình chưa biết tên bạn."

    profile_a = await client.get("/api/v1/memory/profile", headers=_auth(token_a))
    profile_b = await client.get("/api/v1/memory/profile", headers=_auth(token_b))
    assert profile_a.json()["profile"]["display_name"] == "An"
    assert profile_b.json()["profile"] == {}


@pytest.mark.asyncio
async def test_user_can_delete_all_profile_memory(client):
    token = await _register(client, "memory-delete")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    fake = AsyncMock(return_value={"response": "Đã ghi nhận.", "analysis": ""})
    with patch("src.api.conversations.agent.ainvoke", fake):
        await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Tôi tên là An."},
            headers=_auth(token),
        )

    deleted = await client.delete("/api/v1/memory/profile", headers=_auth(token))
    assert deleted.status_code == 204
    profile = await client.get("/api/v1/memory/profile", headers=_auth(token))
    assert profile.json()["profile"] == {}


@pytest.mark.asyncio
async def test_single_turn_chat_also_persists_and_loads_profile(client):
    token = await _register(client, "memory-chat")

    async def fake_agent(state):
        name = state.get("user_profile", {}).get("display_name")
        return {
            "response": f"Bạn tên là {name}." if name else "Đã ghi nhận.",
            "analysis": "",
        }

    with patch("src.api.routes.agent.ainvoke", AsyncMock(side_effect=fake_agent)):
        stored = await client.post(
            "/api/v1/chat",
            json={"message": "Tôi tên là Bình."},
            headers=_auth(token),
        )
        assert stored.status_code == 200

        recalled = await client.post(
            "/api/v1/chat",
            json={"message": "Tôi tên gì?"},
            headers=_auth(token),
        )
        assert recalled.json()["response"] == "Bạn tên là Bình."


@pytest.mark.asyncio
async def test_single_turn_stream_persists_and_loads_profile(client):
    """Regression: frontend dùng SSE nên memory không thể chỉ nối vào POST /chat."""
    token = await _register(client, "memory-chat-stream")
    observed_states = []

    async def fake_agent(state):
        observed_states.append(state)
        name = state.get("user_profile", {}).get("display_name")
        return {
            "response": f"Bạn tên là {name}." if name else "Đã ghi nhận.",
            "analysis": "",
        }

    with patch("src.api.routes.stream_agent_execution", new=_stream_from(fake_agent)):
        async with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Tôi tên là Bình."},
            headers=_auth(token),
        ) as stored:
            await stored.aread()
        async with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "Tôi tên gì?"},
            headers=_auth(token),
        ) as recalled:
            body = (await recalled.aread()).decode()

    assert stored.status_code == 200
    assert recalled.status_code == 200
    assert '"response": "Bạn tên là Bình."' in body
    assert observed_states[0]["user_profile"] == {}
    assert observed_states[1]["user_profile"]["display_name"] == "Bình"


@pytest.mark.asyncio
async def test_conversation_stream_carries_profile_into_a_new_conversation(client):
    """Profile ghi qua stream phải tồn tại ngoài history của conversation cũ."""
    token = await _register(client, "memory-conversation-stream")
    observed_states = []

    async def fake_agent(state):
        observed_states.append(state)
        name = state.get("user_profile", {}).get("display_name")
        return {
            "response": f"Bạn tên là {name}." if name else "Đã ghi nhận.",
            "analysis": "",
        }

    first_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    second_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    with patch(
        "src.api.conversations.stream_agent_execution",
        new=_stream_from(fake_agent),
    ):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{first_id}/messages/stream",
            json={"message": "Tôi tên là Lan."},
            headers=_auth(token),
        ) as stored:
            await stored.aread()
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{second_id}/messages/stream",
            json={"message": "Tôi tên gì?"},
            headers=_auth(token),
        ) as recalled:
            body = (await recalled.aread()).decode()

    assert stored.status_code == 200
    assert recalled.status_code == 200
    assert '"response": "Bạn tên là Lan."' in body
    assert observed_states[0]["history"] == []
    assert observed_states[0]["user_profile"] == {}
    assert observed_states[1]["history"] == []
    assert observed_states[1]["user_profile"]["display_name"] == "Lan"


@pytest.mark.asyncio
async def test_appended_user_turn_updates_profile_but_assistant_turn_does_not(client):
    token = await _register(client, "memory-turn")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "Tên bạn là Sai."},
        headers=_auth(token),
    )
    before = await client.get("/api/v1/memory/profile", headers=_auth(token))
    assert before.json()["profile"] == {}

    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "user", "content": "Tôi tên là Lan."},
        headers=_auth(token),
    )
    after = await client.get("/api/v1/memory/profile", headers=_auth(token))
    assert after.json()["profile"]["display_name"] == "Lan"
