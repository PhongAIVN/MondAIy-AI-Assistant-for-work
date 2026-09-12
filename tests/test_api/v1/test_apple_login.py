import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from src.api import auth as auth_api
from src.db import SessionLocal
from src.models.user import User
from src.services import apple_auth

pytestmark = pytest.mark.asyncio


async def test_apple_login_creates_then_reuses_subject(client, monkeypatch):
    subject = f"apple-subject-{uuid.uuid4().hex}"
    email = f"apple-{uuid.uuid4().hex[:12]}@privaterelay.appleid.com"
    monkeypatch.setattr(
        apple_auth,
        "verify_identity_token",
        lambda _token: {"sub": subject, "email": email},
    )

    first = await client.post(
        "/api/v1/auth/apple/session",
        json={"identityToken": "valid-apple-token", "displayName": "Apple User"},
    )
    assert first.status_code == 200
    assert first.json()["email"] == email
    assert first.json()["accessToken"]

    # Apple có thể không trả email/tên lần thứ hai; subject vẫn phải tìm đúng user.
    monkeypatch.setattr(apple_auth, "verify_identity_token", lambda _token: {"sub": subject})
    second = await client.post("/api/v1/auth/apple/session", json={"identityToken": "valid-apple-token"})
    assert second.status_code == 200
    assert second.json()["userId"] == first.json()["userId"]


async def test_apple_login_exchanges_authorization_code_and_stores_refresh_token(client, monkeypatch):
    subject = f"apple-subject-{uuid.uuid4().hex}"
    email = f"apple-{uuid.uuid4().hex[:12]}@privaterelay.appleid.com"
    monkeypatch.setattr(apple_auth, "verify_identity_token", lambda _token: {"sub": subject, "email": email})
    monkeypatch.setattr(apple_auth, "exchange_authorization_code", lambda _code: _async_value("apple-refresh-token"))
    monkeypatch.setattr(auth_api, "encrypt_token", lambda value: f"encrypted:{value}")

    response = await client.post(
        "/api/v1/auth/apple/session",
        json={"identityToken": "valid-apple-token", "authorizationCode": "one-time-code"},
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        assert user.apple_refresh_token_encrypted == "encrypted:apple-refresh-token"


async def test_delete_apple_account_revokes_refresh_token_before_deletion(client, monkeypatch):
    subject = f"apple-subject-{uuid.uuid4().hex}"
    email = f"apple-{uuid.uuid4().hex[:12]}@privaterelay.appleid.com"
    monkeypatch.setattr(apple_auth, "verify_identity_token", lambda _token: {"sub": subject, "email": email})
    monkeypatch.setattr(apple_auth, "exchange_authorization_code", lambda _code: _async_value("apple-refresh-token"))
    monkeypatch.setattr(apple_auth, "revoke_refresh_token", AsyncMock())
    monkeypatch.setattr(auth_api, "encrypt_token", lambda value: f"encrypted:{value}")
    monkeypatch.setattr(auth_api, "decrypt_token", lambda value: value.removeprefix("encrypted:"))

    login = await client.post(
        "/api/v1/auth/apple/session",
        json={"identityToken": "valid-apple-token", "authorizationCode": "one-time-code"},
    )
    assert login.status_code == 200

    deletion = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['accessToken']}"},
        json={},
    )

    assert deletion.status_code == 204
    apple_auth.revoke_refresh_token.assert_awaited_once_with("apple-refresh-token")


async def test_apple_login_rejects_malformed_token_without_server_error(client):
    from src.config import get_settings

    get_settings().apple_client_id = "com.mondaiy.product"
    response = await client.post(
        "/api/v1/auth/apple/session",
        json={"identityToken": "not-a-jwt"},
    )
    assert response.status_code == 401


async def test_apple_login_rejects_invalid_identity_token(client, monkeypatch):
    monkeypatch.setattr(apple_auth, "verify_identity_token", lambda _token: (_ for _ in ()).throw(ValueError("Apple identity token không hợp lệ.")))
    response = await client.post("/api/v1/auth/apple/session", json={"identityToken": "invalid"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Apple identity token không hợp lệ."


async def _async_value(value):
    return value
