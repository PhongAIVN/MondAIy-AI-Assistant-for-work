import uuid

import pytest

from src.connectors.base import ConnectorAPIError, Source
from src.connectors.calendar import CalendarConnector
from src.connectors.gmail import GmailConnector
from src.db import SessionLocal
from src.models.connection import Connection


def _unique_email() -> str:
    return f"test-integrations-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> str:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    return response.json()["accessToken"]


async def _register_with_user_id(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _create_connection(user_id: str, provider: str) -> int:
    db = SessionLocal()
    try:
        row = Connection(user_id=user_id, provider=provider, account_label="acc")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_list_integrations_empty_when_not_connected(client):
    token = await _register(client)

    response = await client.get("/api/v1/integrations", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["integrations"] == []


@pytest.mark.asyncio
async def test_list_integrations_requires_auth(client):
    response = await client.get("/api/v1/integrations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_sources_for_unknown_integration_returns_404(client):
    token = await _register(client)

    response = await client.get("/api/v1/integrations/999999/sources", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_sources_returns_warning_for_provider_without_connector(client):
    user_id, token = await _register_with_user_id(client)
    integration_id = _create_connection(user_id, "telegram")

    response = await client.get(
        f"/api/v1/integrations/{integration_id}/sources", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert "chưa hỗ trợ" in response.json()["warnings"][0]


@pytest.mark.asyncio
async def test_list_sources_no_longer_hardcoded_to_google_only(client):
    user_id, token = await _register_with_user_id(client)
    integration_id = _create_connection(user_id, "jira")

    response = await client.get(
        f"/api/v1/integrations/{integration_id}/sources", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_google_integration_lists_namespaced_gmail_and_calendar_sources(client, monkeypatch):
    user_id, token = await _register_with_user_id(client)
    integration_id = _create_connection(user_id, "google")

    async def gmail_sources(self):
        return [Source(id="INBOX", name="Hộp thư chính", item_count=12)]

    async def calendar_sources(self):
        return [Source(id="primary", name="Lịch chính")]

    monkeypatch.setattr(GmailConnector, "list_sources", gmail_sources)
    monkeypatch.setattr(CalendarConnector, "list_sources", calendar_sources)

    response = await client.get(
        f"/api/v1/integrations/{integration_id}/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "sources": [
            {"id": "INBOX", "name": "Gmail · Hộp thư chính", "itemCount": 12},
            {"id": "calendar:primary", "name": "Calendar · Lịch chính", "itemCount": None},
        ],
        "warnings": [],
    }


@pytest.mark.asyncio
async def test_google_integration_returns_partial_sources_with_warning(client, monkeypatch):
    user_id, token = await _register_with_user_id(client)
    integration_id = _create_connection(user_id, "google")

    async def gmail_sources(self):
        return [Source(id="INBOX", name="Hộp thư chính")]

    async def calendar_sources(self):
        raise ConnectorAPIError("token cần cấp lại calendar.readonly")

    monkeypatch.setattr(GmailConnector, "list_sources", gmail_sources)
    monkeypatch.setattr(CalendarConnector, "list_sources", calendar_sources)

    response = await client.get(
        f"/api/v1/integrations/{integration_id}/sources",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert [source["id"] for source in response.json()["sources"]] == ["INBOX"]
    assert "calendar.readonly" in response.json()["warnings"][0]
