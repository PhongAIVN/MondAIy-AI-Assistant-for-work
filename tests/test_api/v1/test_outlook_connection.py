import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.connectors.outlook import OutlookConnector
from src.connectors.registry import resolve_connector
from src.db import SessionLocal
from src.models.connection import Connection
from src.services import oauth_state
from src.services.connections import microsoft


def _unique_email() -> str:
    return f"outlook-user-{uuid.uuid4().hex[:12]}@example.com"


async def _register_with_user_id(client) -> tuple[str, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _connection_row(user_id: str) -> Connection | None:
    db = SessionLocal()
    try:
        return db.execute(
            select(Connection).where(Connection.user_id == user_id, Connection.provider == "outlook")
        ).scalar_one_or_none()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_outlook_appears_in_connections_list(client):
    _user_id, token = await _register_with_user_id(client)

    response = await client.get("/api/v1/connections", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    providers = {row["provider"] for row in response.json()["connections"]}
    assert "outlook" in providers


@pytest.mark.asyncio
async def test_outlook_callback_creates_connection_with_email_identity(client, monkeypatch):
    user_id, token = await _register_with_user_id(client)

    async def fake_exchange_code(_code: str) -> dict:
        return {
            "access_token": "graph-access-token",
            "refresh_token": "graph-refresh-token",
            "expires_in": 3600,
            "scope": "openid profile email offline_access https://graph.microsoft.com/Mail.Read",
        }

    async def fake_fetch_account_profile(_access_token: str):
        return SimpleNamespace(email="student@outlook.com", display_name="Student")

    monkeypatch.setattr(microsoft, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(microsoft, "fetch_account_profile", fake_fetch_account_profile)
    monkeypatch.setattr("src.api.connections.encrypt_token", lambda value: f"encrypted:{value}")

    state = oauth_state.sign_intent(user_id, "outlook", "https://frontend.example/sources")
    callback = await client.get(
        "/api/v1/connections/outlook/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 307
    assert "status=connected" in callback.headers["location"]

    row = _connection_row(user_id)
    assert row is not None
    assert row.account_label == "student@outlook.com"
    assert row.provider_user_id == "student@outlook.com"

    listed = await client.get("/api/v1/connections", headers={"Authorization": f"Bearer {token}"})
    outlook_status = next(c for c in listed.json()["connections"] if c["provider"] == "outlook")
    assert outlook_status["connected"] is True


@pytest.mark.asyncio
async def test_outlook_callback_fails_gracefully_when_graph_returns_no_email(client, monkeypatch):
    user_id, _token = await _register_with_user_id(client)

    async def fake_exchange_code(_code: str) -> dict:
        return {"access_token": "graph-access-token", "expires_in": 3600}

    async def fake_fetch_account_profile(_access_token: str):
        return SimpleNamespace(email=None, display_name=None)

    monkeypatch.setattr(microsoft, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(microsoft, "fetch_account_profile", fake_fetch_account_profile)

    state = oauth_state.sign_intent(user_id, "outlook", "https://frontend.example/sources")
    callback = await client.get(
        "/api/v1/connections/outlook/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 307
    assert "status=error" in callback.headers["location"]
    assert _connection_row(user_id) is None


@pytest.mark.asyncio
async def test_outlook_callback_redirects_gracefully_when_user_denies_consent(client):
    # Tenant Azure AD chan bang chinh sach admin-approval (hoac user tu bam
    # Cancel) redirect ve callback voi error=..., KHONG co code. code truoc
    # day la query param bat buoc -> FastAPI tra 422 JSON tho ra thang browser
    # truoc khi vao duoc than ham xu ly loi (khong redirect ve frontend duoc).
    user_id, _token = await _register_with_user_id(client)

    state = oauth_state.sign_intent(user_id, "outlook", "https://frontend.example/sources")
    callback = await client.get(
        "/api/v1/connections/outlook/callback",
        params={"error": "access_denied", "error_subcode": "cancel", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 307
    assert "status=error" in callback.headers["location"]
    assert "message=consent_denied" in callback.headers["location"]
    assert _connection_row(user_id) is None


def test_registry_resolves_outlook_connector():
    connector_cls, native_source_id = resolve_connector("outlook", "inbox")

    assert connector_cls is OutlookConnector
    assert native_source_id == "inbox"


def test_build_authorize_url_requires_client_id(monkeypatch):
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="MICROSOFT_CLIENT_ID"):
            microsoft.build_authorize_url("state-token")
    finally:
        get_settings.cache_clear()
