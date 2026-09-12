import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.task import Task
from src.services.task_breakdown import (
    _SYSTEM_PROMPT,
    TaskBreakdownCandidate,
    TaskBreakdownError,
    TaskBreakdownPlan,
    build_task_breakdown,
)


def _with_llm(monkeypatch, api_key="test-key") -> None:
    """Đặt cấu hình OpenAI cho lượt test, tự hoàn tác khi test kết thúc."""
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", api_key, raising=False)
    monkeypatch.setattr(settings, "task_breakdown_model", "gpt-4o-mini", raising=False)
    monkeypatch.setattr(settings, "llm_request_timeout_seconds", 5.0, raising=False)


def _unique_email() -> str:
    return f"test-breakdown-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_open_task(user_id: str, title: str, due_at: datetime | None = None) -> int:
    db = SessionLocal()
    try:
        task = Task(
            user_id=user_id,
            cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
            title=title,
            detail="",
            status="confirmed",
            due_at=due_at,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_breakdown_empty_inbox_returns_no_items(client):
    user_id, token = await _register(client)

    response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["schedule"]["blocks"] == []
    assert body["schedule"]["deferredToTomorrow"] == []
    assert body["schedule"]["restReminder"] is None


@pytest.mark.asyncio
async def test_breakdown_grounds_model_output_to_real_tasks(client, monkeypatch):
    """Model bịa task_id không có thật phải bị loại; việc thật bị model bỏ sót
    vẫn phải xuất hiện trong kết quả."""
    user_id, token = await _register(client)
    real_id = _create_open_task(user_id, "Việc có thật", due_at=datetime.now(UTC))
    ghost_plan = TaskBreakdownPlan(
        summary="Kế hoạch thử.",
        tasks=[
            TaskBreakdownCandidate(
                task_id=999_999,
                priority_rank=1,
                should_break=True,
                reason="Việc bịa.",
                steps=["Bước bịa"],
                context_needed=[],
                ai_prompt="Prompt bịa",
            ),
            TaskBreakdownCandidate(
                task_id=real_id,
                priority_rank=2,
                should_break=False,
                reason="Việc nhỏ làm trực tiếp.",
                steps=["Làm ngay"],
                context_needed=["Link bài tập"],
                ai_prompt="Bạn là trợ lý học tập...",
            ),
        ],
    )

    # Gọi đúng luồng thật: vá tầng LLM (_plan) chứ không vá tầng grounding.
    async def _fake_plan(_payload: str) -> TaskBreakdownPlan:
        return ghost_plan

    _with_llm(monkeypatch)
    with patch("src.services.task_breakdown._plan", side_effect=_fake_plan):
        response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["taskId"] for item in items] == [real_id]
    assert items[0]["title"] == "Việc có thật"
    assert items[0]["shouldBreak"] is False
    assert items[0]["steps"] == ["Làm ngay"]
    assert items[0]["contextNeeded"] == ["Link bài tập"]
    assert items[0]["aiPrompt"].startswith("Bạn là")
    scheduled_ids = {
        item["taskId"]
        for item in response.json()["schedule"]["blocks"] + response.json()["schedule"]["deferredToTomorrow"]
    }
    assert scheduled_ids == {real_id}


@pytest.mark.asyncio
async def test_breakdown_orders_items_by_priority_rank(client, monkeypatch):
    user_id, token = await _register(client)
    first = _create_open_task(user_id, "Việc A")
    second = _create_open_task(user_id, "Việc B")

    async def _fake_plan(_payload: str) -> TaskBreakdownPlan:
        # Model chủ động xếp Việc B trước dù DB trả A trước.
        return TaskBreakdownPlan(
            summary="",
            tasks=[
                TaskBreakdownCandidate(task_id=second, priority_rank=1, should_break=False),
                TaskBreakdownCandidate(task_id=first, priority_rank=2, should_break=True, steps=["Bước"]),
            ],
        )

    _with_llm(monkeypatch)
    with patch("src.services.task_breakdown._plan", side_effect=_fake_plan):
        response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [item["taskId"] for item in response.json()["items"]] == [second, first]


@pytest.mark.asyncio
async def test_breakdown_without_openai_configured_is_503(client, monkeypatch):
    user_id, token = await _register(client)
    _create_open_task(user_id, "Việc chưa cấu hình")

    _with_llm(monkeypatch, api_key="")
    response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 503
    assert "OpenAI" in response.json()["detail"]


@pytest.mark.asyncio
async def test_breakdown_llm_failure_maps_to_502(client, monkeypatch):
    user_id, token = await _register(client)
    _create_open_task(user_id, "Việc khi LLM lỗi")

    async def _boom(_payload: str) -> TaskBreakdownPlan:
        raise TaskBreakdownError("Dịch vụ OpenAI đang tạm thời không khả dụng. Hãy thử lại sau.")

    _with_llm(monkeypatch)
    with patch("src.services.task_breakdown._plan", side_effect=_boom):
        response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_breakdown_requires_auth(client):
    response = await client.post("/api/v1/tasks/breakdown")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_breakdown_excludes_completed_and_dismissed_tasks(client, monkeypatch):
    user_id, token = await _register(client)
    open_id = _create_open_task(user_id, "Việc còn mở")

    async def _fake_plan(_payload: str) -> TaskBreakdownPlan:
        return TaskBreakdownPlan(summary="", tasks=[])

    db = SessionLocal()
    try:
        closed = Task(
            user_id=user_id,
            cluster_key=f"ck-{uuid.uuid4().hex[:16]}",
            title="Việc đã xong",
            detail="",
            status="completed",
            completed_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(closed)
        db.commit()
    finally:
        db.close()

    _with_llm(monkeypatch)
    with patch("src.services.task_breakdown._plan", side_effect=_fake_plan):
        response = await client.post("/api/v1/tasks/breakdown", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [item["taskId"] for item in response.json()["items"]] == [open_id]


def test_breakdown_schedule_dung_wsjf_nhung_items_giu_priority_rank_llm():
    user_id = f"breakdown-schedule-{uuid.uuid4().hex}"
    future_id = _create_open_task(
        user_id,
        "Việc còn hạn",
        due_at=datetime(2026, 8, 30, 10, 0, tzinfo=UTC),
    )
    overdue_id = _create_open_task(
        user_id,
        "Việc quá hạn",
        due_at=datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
    )
    plan = TaskBreakdownPlan(
        tasks=[
            TaskBreakdownCandidate(task_id=future_id, priority_rank=1, should_break=False),
            TaskBreakdownCandidate(task_id=overdue_id, priority_rank=2, should_break=False),
        ]
    )

    db = SessionLocal()
    try:
        result = build_task_breakdown(
            db,
            user_id,
            plan,
            now=datetime(2026, 8, 27, 7, 0, tzinfo=UTC),
        )
    finally:
        db.close()

    assert [item["task_id"] for item in result["items"]] == [future_id, overdue_id]
    assert [block.task_id for block in result["schedule"].blocks] == [overdue_id, future_id]
    assert result["schedule"].now.hour == 14
    assert result["schedule"].now.utcoffset() is not None
    assert all(block.estimate_confidence == "neutral_fallback" for block in result["schedule"].blocks)


def test_system_prompt_cam_llm_tu_gan_gio():
    assert "Không tự gán giờ làm cụ thể" in _SYSTEM_PROMPT
    assert "Backend xác định giờ" in _SYSTEM_PROMPT


def test_schedule_khong_mat_task_thu_16_du_llm_payload_co_cap():
    user_id = f"breakdown-all-tasks-{uuid.uuid4().hex}"
    task_ids = {_create_open_task(user_id, f"Việc {index}") for index in range(16)}

    db = SessionLocal()
    try:
        result = build_task_breakdown(
            db,
            user_id,
            TaskBreakdownPlan(),
            now=datetime(2026, 8, 27, 16, 0, tzinfo=UTC),
        )
    finally:
        db.close()

    scheduled_ids = {block.task_id for block in result["schedule"].blocks}
    deferred_ids = {task.task_id for task in result["schedule"].deferred_to_tomorrow}
    assert scheduled_ids | deferred_ids == task_ids
    assert len(result["items"]) == 15
