import uuid

import pytest

from src.services import routines as routines_service


def _unique_email() -> str:
    return f"test-routines-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


@pytest.mark.asyncio
async def test_create_list_and_delete_routine(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/routines",
        json={"name": "Tóm tắt email", "instructions": "Đọc email hôm nay.", "frequency": "daily", "hour": 8},
        headers=headers,
    )
    assert created.status_code == 200
    routine_id = created.json()["id"]
    assert created.json()["enabled"] is True

    listed = await client.get("/api/v1/routines", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["routines"]] == [routine_id]

    deleted = await client.delete(f"/api/v1/routines/{routine_id}", headers=headers)
    assert deleted.status_code == 204

    listed_again = await client.get("/api/v1/routines", headers=headers)
    assert listed_again.json()["routines"] == []


@pytest.mark.asyncio
async def test_weekly_without_day_of_week_is_rejected(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/routines",
        json={"name": "Weekly review", "instructions": "x", "frequency": "weekly", "hour": 8},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cannot_read_another_users_routine(client):
    _, token_a = await _register(client)
    _, token_b = await _register(client)

    created = await client.post(
        "/api/v1/routines",
        json={"name": "Của A", "instructions": "x", "frequency": "daily", "hour": 8},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    routine_id = created.json()["id"]

    response = await client.get(f"/api/v1/routines/{routine_id}/runs", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 404

    detail = await client.get(f"/api/v1/routines/{routine_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_get_routine_returns_the_owned_routine(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/routines",
        json={"name": "Tóm tắt Jira", "instructions": "x", "frequency": "daily", "hour": 9},
        headers=headers,
    )
    routine_id = created.json()["id"]

    response = await client.get(f"/api/v1/routines/{routine_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Tóm tắt Jira"


@pytest.mark.asyncio
async def test_run_now_writes_agent_response_and_is_listed(client, monkeypatch):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/routines",
        json={"name": "Tóm tắt email", "instructions": "Đọc email hôm nay.", "frequency": "daily", "hour": 8},
        headers=headers,
    )
    routine_id = created.json()["id"]

    async def fake_ainvoke(state):
        return {"response": "Không có email nào cần trả lời hôm nay.", "metadata": {}}

    monkeypatch.setattr(routines_service.agent, "ainvoke", fake_ainvoke)

    run_response = await client.post(f"/api/v1/routines/{routine_id}/run-now", headers=headers)
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "done"
    assert run_response.json()["outputText"] == "Không có email nào cần trả lời hôm nay."

    runs = await client.get(f"/api/v1/routines/{routine_id}/runs", headers=headers)
    assert len(runs.json()["runs"]) == 1

    recent = await client.get("/api/v1/routines/runs/recent", headers=headers)
    assert recent.status_code == 200
    assert recent.json()["runs"][0]["routineId"] == routine_id
    assert recent.json()["runs"][0]["routineName"] == "Tóm tắt email"
