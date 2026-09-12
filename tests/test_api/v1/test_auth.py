import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

import src.api.auth as auth_api
from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceItem, SourceScope
from src.models.user import User


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


def _extract_token(reset_link: str) -> str:
    return parse_qs(urlparse(reset_link).query)["token"][0]


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_tokens(client):
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == email
    assert data["accessToken"]
    assert data["refreshToken"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    email = _unique_email()
    payload = {"email": email, "password": "correct-horse-1"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    response = await client.post("/api/v1/auth/register", json={"email": _unique_email(), "password": "short"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_invalid_email(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "correct-horse-1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_correct_password_returns_tokens(client):
    email = _unique_email()
    password = "correct-horse-1"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email


@pytest.mark.asyncio
async def test_login_repairs_stale_c_to_a_when_discord_identity_matches_crawl(client):
    email = _unique_email()
    password = "correct-horse-1"
    registered = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    user_id = registered.json()["userId"]
    suffix = uuid.uuid4().hex
    discord_id = f"discord-{suffix}"
    now = datetime.now(UTC)
    with SessionLocal() as db:
        scope = SourceScope(provider="discord", external_id=f"scope-{suffix}")
        db.add(scope)
        db.flush()
        db.add_all(
            [
                Connection(
                    user_id=user_id,
                    provider="discord",
                    provider_user_id=discord_id,
                ),
                SourceItem(
                    provider="discord",
                    external_id=f"message-{suffix}",
                    scope_id=scope.id,
                    author_external_id=discord_id,
                    content="Tin nhắn đã crawl",
                    content_hash=f"hash-{suffix}",
                    source_updated_at=now,
                    observed_at=now,
                    run_id="test",
                ),
            ]
        )
        db.commit()

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 200
    assert response.json()["programAccessLevel"] == "A"


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client):
    email = _unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401_not_404(client):
    # Không lộ thông tin email có tồn tại hay không (tránh user enumeration).
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _unique_email(), "password": "correct-horse-1"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token_returns_user(client):
    email = _unique_email()
    register_response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    access_token = register_response.json()["accessToken"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


@pytest.mark.asyncio
async def test_me_with_garbage_token_returns_401(client):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_is_rejected(client):
    # Refresh endpoint chỉ nhận refresh token, không nhận access token
    # (kiểm tra "type" claim trong auth_service.decode_token).
    email = _unique_email()
    register_response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    access_token = register_response.json()["accessToken"]

    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": access_token})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_valid_refresh_token_returns_new_tokens(client):
    email = _unique_email()
    register_response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    refresh_token = register_response.json()["refreshToken"]

    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})
    assert response.status_code == 200
    assert response.json()["email"] == email


@pytest.mark.asyncio
async def test_forgot_password_always_returns_generic_message(client, monkeypatch):
    # Không lộ email nào tồn tại: message + status phải giống hệt nhau, chỉ
    # khác ở việc có thật sự gửi mail phía sau (kiểm tra qua sent_links).
    sent_links: list[str] = []
    monkeypatch.setattr(
        auth_api.email_service,
        "send_password_reset_email",
        lambda to_email, reset_link: sent_links.append(reset_link),
    )

    email = _unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})

    existing = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": _unique_email()})

    assert existing.status_code == 200
    assert unknown.status_code == 200
    assert existing.json()["message"] == unknown.json()["message"]
    assert len(sent_links) == 1


@pytest.mark.asyncio
async def test_forgot_password_locks_user_after_too_many_attempts(client, monkeypatch):
    # reset_request_count đã đạt ngưỡng (giả lập nhiều lần bấm trước đó, kể cả
    # từ IP khác nhau) — lần bấm tiếp theo phải bị khoá per-user, không gửi
    # mail, và không lộ khác biệt qua response (vẫn message chung + 200).
    sent_links: list[str] = []
    monkeypatch.setattr(
        auth_api.email_service,
        "send_password_reset_email",
        lambda to_email, reset_link: sent_links.append(reset_link),
    )

    email = _unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})

    settings = get_settings()
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        user.reset_request_count = settings.forgot_password_max_attempts
        user.reset_request_window_started_at = datetime.now(UTC)
        db.commit()

    response = await client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert response.status_code == 200
    assert sent_links == []
    with SessionLocal() as db:
        locked_user = db.execute(select(User).where(User.email == email)).scalar_one()
        assert locked_user.reset_locked_until is not None
        locked_until = locked_user.reset_locked_until
        if locked_until.tzinfo is None:
            # SQLite trả DateTime(timezone=True) về naive; quy ước lưu của app
            # vẫn là UTC, nên assertion phải kiểm tra instant thay vì driver.
            locked_until = locked_until.replace(tzinfo=UTC)
        assert locked_until > datetime.now(UTC)


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_changes_password_and_is_single_use(client, monkeypatch):
    sent_links: list[str] = []
    monkeypatch.setattr(
        auth_api.email_service,
        "send_password_reset_email",
        lambda to_email, reset_link: sent_links.append(reset_link),
    )

    email = _unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = _extract_token(sent_links[0])

    reset_response = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "newPassword": "new-password-1"}
    )
    assert reset_response.status_code == 200

    old_password_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-1"}
    )
    assert old_password_login.status_code == 401

    new_password_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "new-password-1"}
    )
    assert new_password_login.status_code == 200

    reused_token = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "newPassword": "another-password-1"}
    )
    assert reused_token.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_with_unknown_token_returns_400(client):
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "newPassword": "new-password-1"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password(client, monkeypatch):
    sent_links: list[str] = []
    monkeypatch.setattr(
        auth_api.email_service,
        "send_password_reset_email",
        lambda to_email, reset_link: sent_links.append(reset_link),
    )

    email = _unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    token = _extract_token(sent_links[0])

    response = await client.post("/api/v1/auth/reset-password", json={"token": token, "newPassword": "short"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_is_rate_limited_after_repeated_attempts(client):
    # /auth/login giới hạn 10/minute/IP để chặn brute-force password.
    payload = {"email": _unique_email(), "password": "wrong-password"}
    for _ in range(10):
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401

    blocked = await client.post("/api/v1/auth/login", json=payload)
    assert blocked.status_code == 429
