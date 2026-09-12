"""Regression cho response boundary của Planning Workspace."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.services.planner.schedule import DeferredTask, ScheduledBlock


async def _register(client) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"planner-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct-horse-1",
        },
    )
    assert response.status_code == 201
    return response.json()["accessToken"]


@pytest.mark.asyncio
async def test_generate_plan_serializes_scheduler_domain_objects(client, monkeypatch):
    """Dataclass từ scheduler phải qua được Pydantic response boundary."""
    token = await _register(client)
    generated_at = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
    block = ScheduledBlock(
        task_id=80,
        title="Sửa báo cáo",
        start=generated_at,
        end=generated_at + timedelta(minutes=45),
        minutes=45,
        energy="deep",
        estimate_confidence="estimated",
        why="Sắp đến hạn.",
        communication=None,
    )
    deferred = DeferredTask(
        task_id=59,
        title="Đọc tài liệu",
        start=None,
        end=None,
        minutes=30,
        energy="shallow",
        estimate_confidence="neutral_fallback",
        why="Không còn khung trống 30 phút.",
    )

    def fake_plan(db, user_id, *, start, days, known_task_ids, previous_blocks):
        return {
            "generated_at": generated_at,
            "days": days,
            "blocks": [block],
            "at_risk": [deferred],
            "calendar_blocks": [],
            "considered_task_ids": [80, 59],
            "refresh": {
                "new_task_count": 1,
                "new_urgent_today_count": 1,
                "reschedule_count": 1,
                "at_risk_count": 1,
            },
            "reschedule_suggestions": [{
                "task_id": 80,
                "title": "Sửa báo cáo",
                "from_start": generated_at + timedelta(hours=1),
                "from_end": generated_at + timedelta(hours=1, minutes=45),
                "to_start": generated_at,
                "to_end": generated_at + timedelta(minutes=45),
                "reason": "Nhường chỗ cho việc mới có hạn hôm nay.",
            }],
            "notes": ["Đây là bản nháp."],
        }

    monkeypatch.setattr("src.api.planner.build_workspace_plan", fake_plan)

    response = await client.post(
        "/api/v1/planner/generate",
        json={
            "days": 1,
            "knownTaskIds": [59],
            "previousBlocks": [{"taskId": 80, "start": "2026-08-29T09:00:00Z", "end": "2026-08-29T09:45:00Z"}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["blocks"] == [
        {
            "taskId": 80,
            "title": "Sửa báo cáo",
            "start": "2026-08-29T08:00:00Z",
            "end": "2026-08-29T08:45:00Z",
            "minutes": 45,
            "energy": "deep",
            "estimateConfidence": "estimated",
            "why": "Sắp đến hạn.",
            "communication": None,
        }
    ]
    assert response.json()["atRisk"][0]["taskId"] == 59
    assert response.json()["atRisk"][0]["why"] == "Không còn khung trống 30 phút."
    assert response.json()["refresh"]["newUrgentTodayCount"] == 1
    assert response.json()["rescheduleSuggestions"][0]["toStart"] == "2026-08-29T08:00:00Z"
