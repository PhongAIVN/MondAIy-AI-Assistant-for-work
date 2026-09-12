import uuid
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.services import oauth_state
from src.services.connections import google

pytestmark = pytest.mark.asyncio

_GOOGLE_SCOPES = (
    "openid email profile https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/calendar.events "
    "https://www.googleapis.com/auth/spreadsheets.readonly "
    "https://www.googleapis.com/auth/documents.readonly "
    "https://www.googleapis.com/auth/drive.readonly"
)


def _frontend_redirect(path: str = "/auth/google/callback") -> str:
    settings = get_settings()
    origin = (settings.web_app_public_url or settings.app_public_url).rstrip("/")
    return f"{origin}{path}"


def _fake_google_exchange(
    monkeypatch,
    email: str,
    picture: str | None = None,
    refresh_token: str | None = "google-refresh-token",
) -> None:
    async def fake_exchange_code(_code: str) -> dict:
        token_data = {
            "access_token": "google-access-token",
            "expires_in": 3600,
            "scope": _GOOGLE_SCOPES,
        }
        if refresh_token:
            token_data["refresh_token"] = refresh_token
        return token_data

    async def fake_account_profile(_access_token: str):
        from types import SimpleNamespace

        return SimpleNamespace(email=email, picture=picture)

    monkeypatch.setattr(google, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(google, "fetch_account_profile", fake_account_profile, raising=False)
    monkeypatch.setattr(
        google,
        "get_settings",
        lambda: type(
            "GoogleSettings",
            (),
            {
                "google_client_id": "client-id",
                "google_redirect_uri": "https://api.example.com/api/v1/connections/google/callback",
                "app_public_url": "https://api.example.com",
                "google_scopes": _GOOGLE_SCOPES,
            },
        )(),
    )
    monkeypatch.setattr("src.api.connections.encrypt_token", lambda value: f"encrypted:{value}")


async def _run_login_flow(client, monkeypatch, email: str, picture: str | None = None):
    """Reproduce trọn luồng: /auth/google/login ký state -> callback đổi code
    thật ra login code -> /auth/google/session đổi login code lấy token."""
    _fake_google_exchange(monkeypatch, email, picture)
    ext_redirect_uri = _frontend_redirect()

    login_redirect = await client.get(
        "/api/v1/auth/google/login",
        params={"extRedirectUri": ext_redirect_uri},
        follow_redirects=False,
    )
    assert login_redirect.status_code == 307
    authorize_url = login_redirect.headers["location"]
    assert "state=" in authorize_url
    authorize_params = parse_qs(urlsplit(authorize_url).query)
    scopes = authorize_params["scope"][0].split()
    assert {
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    }.issubset(scopes)
    assert authorize_params["access_type"] == ["offline"]
    assert authorize_params["prompt"] == ["consent"]
    state = authorize_url.split("state=")[1].split("&")[0]

    callback = await client.get(
        "/api/v1/connections/google/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 307
    location = callback.headers["location"]
    assert "status=login_success" in location
    login_code = location.split("code=")[1].split("&")[0]

    session = await client.post("/api/v1/auth/google/session", json={"code": login_code})
    assert session.status_code == 200
    return session.json()


async def test_google_login_creates_new_user_and_issues_session(client, monkeypatch):
    email = f"google-new-{uuid.uuid4().hex[:12]}@gmail.com"

    tokens = await _run_login_flow(client, monkeypatch, email, picture="https://lh3.googleusercontent.com/a/pic")

    assert tokens["email"] == email
    assert tokens["accessToken"]
    assert tokens["refreshToken"]
    assert tokens["avatarUrl"] == "https://lh3.googleusercontent.com/a/pic"

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['accessToken']}"})
    assert me.status_code == 200
    assert me.json()["email"] == email

    connections = await client.get(
        "/api/v1/connections",
        headers={"Authorization": f"Bearer {tokens['accessToken']}"},
    )
    google_connection = next(row for row in connections.json()["connections"] if row["provider"] == "google")
    assert google_connection["connected"] is True
    assert google_connection["accountLabel"] == email

    gmail_status = await client.get(
        "/api/v1/connections/gmail/status",
        headers={"Authorization": f"Bearer {tokens['accessToken']}"},
    )
    assert gmail_status.status_code == 200
    assert gmail_status.json()["oauthValid"] is True
    assert gmail_status.json()["mailboxAccessible"] is True


async def test_google_relogin_preserves_existing_refresh_token(client, monkeypatch):
    email = f"google-refresh-{uuid.uuid4().hex[:12]}@example.com"
    await _run_login_flow(client, monkeypatch, email)

    with SessionLocal() as db:
        connection = db.scalar(select(Connection).where(Connection.provider == "google", Connection.account_label == email))
        assert connection is not None
        first_refresh_token = connection.refresh_token_encrypted
        assert first_refresh_token

    _fake_google_exchange(monkeypatch, email, refresh_token=None)
    await _run_login_flow(client, monkeypatch, email)

    with SessionLocal() as db:
        connection = db.scalar(select(Connection).where(Connection.provider == "google", Connection.account_label == email))
        assert connection is not None
        assert connection.refresh_token_encrypted == first_refresh_token


async def test_google_login_reuses_existing_user_by_email(client, monkeypatch):
    email = f"google-existing-{uuid.uuid4().hex[:12]}@example.com"
    registered = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"}
    )
    assert registered.status_code == 201
    original_user_id = registered.json()["userId"]

    tokens = await _run_login_flow(client, monkeypatch, email)
    assert tokens["userId"] == original_user_id

    # Tài khoản có mật khẩu từ trước vẫn đăng nhập bằng mật khẩu được bình
    # thường — luồng Google không âm thầm xoá password_hash cũ.
    password_login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "correct-horse-1"}
    )
    assert password_login.status_code == 200


async def test_google_only_account_rejects_password_login_generically(client, monkeypatch):
    email = f"google-only-{uuid.uuid4().hex[:12]}@example.com"
    await _run_login_flow(client, monkeypatch, email)

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "anything-1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Email hoặc mật khẩu không đúng."


async def test_google_login_rejects_untrusted_redirect_target(client):
    response = await client.get(
        "/api/v1/auth/google/login",
        params={"extRedirectUri": "https://attacker.example/steal"},
        follow_redirects=False,
    )
    assert response.status_code == 400


async def test_google_login_accepts_only_the_configured_native_callback(client, monkeypatch):
    settings = get_settings()
    previous = settings.mobile_app_redirect_uri
    settings.mobile_app_redirect_uri = "mondaiy://auth/callback"
    monkeypatch.setattr(
        google,
        "build_login_authorize_url",
        lambda state: f"https://accounts.google.com/o/oauth2/v2/auth?state={state}",
    )
    try:
        accepted = await client.get(
            "/api/v1/auth/google/login",
            params={"extRedirectUri": "mondaiy://auth/callback"},
            follow_redirects=False,
        )
        rejected = await client.get(
            "/api/v1/auth/google/login",
            params={"extRedirectUri": "mondaiy://auth/attacker"},
            follow_redirects=False,
        )
    finally:
        settings.mobile_app_redirect_uri = previous

    assert accepted.status_code == 307
    authorize_url = accepted.headers["location"]
    assert urlsplit(authorize_url).netloc == "accounts.google.com"
    assert parse_qs(urlsplit(authorize_url).query)["state"][0]
    assert rejected.status_code == 400


async def test_google_session_rejects_invalid_code(client):
    response = await client.post("/api/v1/auth/google/session", json={"code": "not-a-real-code"})
    assert response.status_code == 400


async def test_google_session_rejects_connect_flow_state_reused_as_login(client, monkeypatch):
    """State ký cho flow="connect" (kết nối nguồn) không được lén dùng để
    đăng nhập — verify_intent phải phân biệt qua field `flow`."""
    email = f"cross-flow-{uuid.uuid4().hex[:12]}@example.com"
    _fake_google_exchange(monkeypatch, email)
    connect_state = oauth_state.sign_intent("999999", "google", _frontend_redirect())

    callback = await client.get(
        "/api/v1/connections/google/callback",
        params={"code": "oauth-code", "state": connect_state},
        follow_redirects=False,
    )
    # Rơi vào nhánh connect (không phải login) — không phát login code nào,
    # dù user_id trong state không tồn tại thật.
    assert callback.status_code == 307
    location = callback.headers["location"]
    assert "status=connected" in location
    assert "code=" not in location
