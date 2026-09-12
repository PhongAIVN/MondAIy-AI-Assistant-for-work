import base64
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.api.vision import _calendar_suggestions, _classify_action, _task_suggestions
from src.config import get_settings
from src.db import SessionLocal
from src.models.task import Task


def _data_url(mime: str = "image/png", payload: bytes = b"fake-image-bytes") -> str:
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


async def _register(client) -> str:
    email = f"test-vision-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    return response.json()["accessToken"]


def _suggest_tasks_observation(suggestions: list[dict]) -> dict:
    return {
        "name": "suggest_tasks",
        "output": json.dumps({"status": "suggested", "suggestions": suggestions}, ensure_ascii=False),
    }


def test_task_suggestions_reads_and_validates_suggest_tasks_observation() -> None:
    result = {
        "observations": [
            _suggest_tasks_observation(
                [
                    {"title": "Nộp báo cáo", "due_at": "2026-08-20T09:00:00+07:00"},
                    {"title": ""},  # thiếu title bị TaskSuggestionAction từ chối
                    {"title": "Nộp báo cáo", "due_at": "2026-08-20T09:00:00+07:00"},  # trùng, bị khử
                ]
            )
        ]
    }
    suggestions = _task_suggestions(result)
    assert len(suggestions) == 1
    assert suggestions[0].title == "Nộp báo cáo"
    assert suggestions[0].due_at is not None


def test_calendar_suggestions_reads_batch_and_drops_invalid_items() -> None:
    result = {
        "observations": [
            {
                "name": "suggest_calendar_events",
                "output": json.dumps(
                    {
                        "suggestions": [
                            {
                                "title": "Tính toán hiệu suất cao",
                                "start_at": "2026-03-24T07:10:00+07:00",
                                "end_at": "2026-03-24T11:30:00+07:00",
                            },
                            {"title": "Thiếu giờ kết thúc", "start_at": "2026-03-24T07:10:00+07:00"},
                            {
                                "title": "Tính toán hiệu suất cao",
                                "start_at": "2026-03-24T07:10:00+07:00",
                                "end_at": "2026-03-24T11:30:00+07:00",
                            },
                        ]
                    }
                ),
            }
        ]
    }
    suggestions = _calendar_suggestions(result)
    assert len(suggestions) == 1
    assert suggestions[0].start_at.isoformat() == "2026-03-24T07:10:00+07:00"
    assert suggestions[0].end_at.isoformat() == "2026-03-24T11:30:00+07:00"


def test_classify_action_calendar_event_when_all_suggestions_have_due_at() -> None:
    result = {"observations": [_suggest_tasks_observation([{"title": "Họp", "due_at": "2026-08-20T09:00:00+07:00"}])]}
    assert _classify_action(_task_suggestions(result)) == "calendar_event"


def test_classify_action_task_when_no_suggestion_has_due_at() -> None:
    result = {"observations": [_suggest_tasks_observation([{"title": "Chuẩn bị tài liệu"}])]}
    assert _classify_action(_task_suggestions(result)) == "task"


def test_classify_action_mixed_when_some_suggestions_have_due_at() -> None:
    result = {
        "observations": [
            _suggest_tasks_observation(
                [
                    {"title": "Họp", "due_at": "2026-08-20T09:00:00+07:00"},
                    {"title": "Chuẩn bị tài liệu"},
                ]
            )
        ]
    }
    assert _classify_action(_task_suggestions(result)) == "mixed"


def test_classify_action_unclear_when_no_suggestions() -> None:
    assert _classify_action(_task_suggestions({"observations": []})) == "unclear"


@pytest.mark.asyncio
async def test_vision_action_requires_auth(client):
    response = await client.post("/api/v1/vision/actions", json={"imageDataUrl": _data_url()})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vision_action_returns_agent_response_for_valid_image(client):
    token = await _register(client)
    fake_result = {
        "response": "Bạn có deadline nộp bài lúc 09:00 thứ 3.",
        "analysis": "",
        "observations": [],
        "metadata": {"sources": []},
    }
    with (
        patch("src.api.vision.extract_visual_context", AsyncMock(return_value="Nộp bài 09:00 thứ 3")),
        patch("src.api.vision.agent.ainvoke", AsyncMock(return_value=fake_result)),
    ):
        response = await client.post(
            "/api/v1/vision/actions",
            json={"imageDataUrl": _data_url(), "message": "Đây là ảnh gì?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "Bạn có deadline nộp bài lúc 09:00 thứ 3."
    assert body["actionType"] == "unclear"
    assert "calendarSuggestions" not in body


@pytest.mark.asyncio
async def test_vision_action_reports_calendar_event_and_task_suggestion_shape(client):
    """task_suggestions phải khớp field mà POST /tasks/from-suggestion cần."""
    token = await _register(client)
    with SessionLocal() as db:
        task_count_before = len(db.scalars(select(Task)).all())
    fake_result = {
        "response": "Bạn có 1 việc có hạn và 1 việc chưa rõ hạn.",
        "analysis": "",
        "observations": [
            {
                "name": "suggest_tasks",
                "output": json.dumps(
                    {
                        "status": "suggested",
                        "suggestions": [
                            {
                                "title": "Nộp báo cáo",
                                "detail": "Gửi bản PDF cho giảng viên",
                                "due_at": "2026-08-20T09:00:00+07:00",
                                "assignee": "Minh",
                                "source": "Ảnh",
                            },
                            {"title": "Chuẩn bị tài liệu"},
                        ],
                    },
                    ensure_ascii=False,
                ),
            }
        ],
        "metadata": {"sources": []},
    }
    with (
        patch("src.api.vision.extract_visual_context", AsyncMock(return_value="Nộp báo cáo 09:00 thứ 3")),
        patch("src.api.vision.agent.ainvoke", AsyncMock(return_value=fake_result)),
    ):
        response = await client.post(
            "/api/v1/vision/actions",
            json={"imageDataUrl": _data_url(), "message": "Đây là ảnh gì?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["actionType"] == "mixed"
    suggestions = body["taskSuggestions"]
    assert len(suggestions) == 2
    with_due = next(item for item in suggestions if item["title"] == "Nộp báo cáo")
    assert with_due["dueAt"] is not None
    assert with_due["detail"] == "Gửi bản PDF cho giảng viên"
    assert with_due["assignee"] == "Minh"
    assert with_due["allDay"] is False
    without_due = next(item for item in suggestions if item["title"] == "Chuẩn bị tài liệu")
    assert without_due["dueAt"] is None
    # Field trùng tên (camelCase) với TaskFromSuggestionRequest để frontend gọi thẳng.
    for item in suggestions:
        assert {"title", "detail", "dueAt", "allDay", "assignee"}.issubset(item.keys())
    # OCR/agent chỉ dựng draft preview: trước khi người dùng bấm "Thêm task"
    # tuyệt đối không có record Task nào được ghi.
    with SessionLocal() as db:
        assert len(db.scalars(select(Task)).all()) == task_count_before


@pytest.mark.asyncio
async def test_vision_action_rejects_image_over_configured_limit(client):
    token = await _register(client)
    settings = get_settings()
    original_limit = settings.vision_max_image_bytes
    settings.vision_max_image_bytes = 10
    try:
        response = await client.post(
            "/api/v1/vision/actions",
            json={"imageDataUrl": _data_url(payload=b"0123456789ABCDEF0123456789ABCDEF"), "message": "ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        settings.vision_max_image_bytes = original_limit
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_vision_action_rejects_unsupported_mime_type(client):
    token = await _register(client)
    response = await client.post(
        "/api/v1/vision/actions",
        json={"imageDataUrl": _data_url(mime="application/pdf"), "message": "ok"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_vision_action_returns_503_when_openai_not_configured(client, monkeypatch):
    token = await _register(client)
    settings = get_settings()
    original_key = settings.openai_api_key
    settings.openai_api_key = ""
    try:
        response = await client.post(
            "/api/v1/vision/actions",
            json={"imageDataUrl": _data_url(), "message": "ok"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        settings.openai_api_key = original_key
    assert response.status_code == 503
