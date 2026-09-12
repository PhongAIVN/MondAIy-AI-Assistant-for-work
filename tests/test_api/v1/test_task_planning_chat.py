"""Regression cho lane planning: phải kết thúc bằng kế hoạch grounded, không tool-loop."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.db import SessionLocal
from src.models.task import Task
from src.services.task_planning import is_task_planning_request


async def _register(client) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": f"planning-{uuid.uuid4().hex[:10]}@example.com", "password": "correct-horse-1"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["userId"], body["accessToken"]


def _seed_task(user_id: str, title: str) -> None:
    with SessionLocal() as db:
        db.add(Task(
            user_id=user_id, cluster_key=f"planning-{uuid.uuid4().hex}", title=title,
            detail="Tài liệu đã lưu trong mô tả task", status="confirmed", due_at=datetime.now(UTC),
        ))
        db.commit()


def _reply(title: str = "Hoàn tất báo cáo") -> dict:
    return {
        "response": (
            f"1. {title}\nVì sao: quá hạn.\nBước bắt đầu (≤15 phút): mở tài liệu.\n"
            "Bước 2: viết dàn ý.\nTài liệu/context: brief.md\n"
            "Prompt copy-paste: Bạn là trợ lý, hãy lập dàn ý."
        ),
        "analysis": "task_planning_grounded",
    }


@pytest.mark.asyncio
async def test_today_plan_returns_terminal_actionable_stream(client):
    user_id, token = await _register(client)
    _seed_task(user_id, "Hoàn tất báo cáo")
    agent = AsyncMock()
    with patch("src.api.routes.build_task_planning_reply", new=AsyncMock(return_value=_reply())), patch(
        "src.api.routes.stream_agent_execution", agent
    ):
        async with client.stream(
            "POST", "/api/v1/chat/stream", json={"message": "Hôm nay tôi cần làm gì và ưu tiên ra sao?"},
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            body = (await response.aread()).decode()
    assert response.status_code == 200
    assert "event: done" in body
    assert "Bước bắt đầu" in body and "Prompt copy-paste" in body
    agent.assert_not_called()


@pytest.mark.asyncio
async def test_week_plan_in_conversation_uses_same_terminal_lane(client):
    _, token = await _register(client)
    conversation_id = (await client.post("/api/v1/conversations", json={}, headers={"Authorization": f"Bearer {token}"})).json()["id"]
    agent = AsyncMock()
    with patch("src.api.conversations.build_task_planning_reply", new=AsyncMock(return_value=_reply("Chuẩn bị tuần"))), patch(
        "src.api.conversations.stream_agent_execution", agent
    ):
        async with client.stream(
            "POST", f"/api/v1/conversations/{conversation_id}/messages/stream",
            json={"message": "Hãy retro hôm nay và gợi ý việc ưu tiên tuần này."},
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            body = (await response.aread()).decode()
    assert response.status_code == 200
    assert "Chuẩn bị tuần" in body and "event: done" in body
    agent.assert_not_called()


@pytest.mark.asyncio
async def test_empty_inbox_returns_useful_terminal_reply(client):
    _, token = await _register(client)
    async with client.stream(
        "POST", "/api/v1/chat/stream", json={"message": "Hôm nay tôi cần làm gì? Hãy ưu tiên giúp tôi."},
        headers={"Authorization": f"Bearer {token}"},
    ) as response:
        body = (await response.aread()).decode()
    assert response.status_code == 200
    assert "event: done" in body
    assert "chưa có task còn mở" in body


def test_ordinary_chat_is_not_task_planning_request():
    assert not is_task_planning_request("Tóm tắt email hôm nay giúp tôi.")
    assert not is_task_planning_request("Task số 12 đang đến hạn khi nào?")
    assert is_task_planning_request("Hôm nay tôi cần làm gì và việc nào ưu tiên?")
    assert is_task_planning_request("Hãy retro hôm nay rồi lập kế hoạch tuần này.")
    # Thái chốt 2026-09-01: câu trống trơn này thuộc lane kế hoạch ưu tiên,
    # không còn rơi vào luồng gợi ý task từ nguồn.
    assert is_task_planning_request("Hôm nay tôi cần làm gì?")
