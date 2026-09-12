import uuid
from types import SimpleNamespace

import pytest

from src.config import Settings
from src.services import oauth_state
from src.services.connections import google


def test_google_oauth_requests_profile_scope_and_rejects_unsafe_picture_urls():
    settings = Settings(_env_file=None)

    assert "profile" in settings.google_scopes.split()
    assert google._safe_picture_url("javascript:alert(1)") is None
    assert (
        google._safe_picture_url("https://lh3.googleusercontent.com/a/profile-photo")
        == "https://lh3.googleusercontent.com/a/profile-photo"
    )


@pytest.mark.asyncio
async def test_google_userinfo_extracts_email_and_picture(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "email": "avatar.owner@gmail.com",
                "picture": "https://lh3.googleusercontent.com/a/profile-photo",
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(google.httpx, "AsyncClient", lambda **_kwargs: FakeClient())

    profile = await google.fetch_account_profile("google-access-token")

    assert profile.email == "avatar.owner@gmail.com"
    assert profile.picture == "https://lh3.googleusercontent.com/a/profile-photo"


@pytest.mark.asyncio
async def test_google_callback_sets_profile_avatar_and_me_returns_it(client, monkeypatch):
    app_email = f"avatar-owner-{uuid.uuid4().hex}@example.com"
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": app_email,
            "password": "correct-horse-1",
            "displayName": "Avatar Owner",
        },
    )
    assert registered.status_code == 201
    auth = registered.json()

    async def fake_exchange_code(_code: str) -> dict:
        return {
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "expires_in": 3600,
            "scope": "openid email https://www.googleapis.com/auth/gmail.readonly",
        }

    async def fake_account_profile(_access_token: str):
        return SimpleNamespace(
            email="avatar.owner@gmail.com",
            picture="https://lh3.googleusercontent.com/a/profile-photo",
        )

    async def fake_account_label(_access_token: str):
        return "avatar.owner@gmail.com"

    monkeypatch.setattr(google, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(google, "fetch_account_label", fake_account_label)
    monkeypatch.setattr(google, "fetch_account_profile", fake_account_profile, raising=False)
    monkeypatch.setattr("src.api.connections.encrypt_token", lambda value: f"encrypted:{value}")

    state = oauth_state.sign_intent(auth["userId"], "google", "https://frontend.example/sources")
    callback = await client.get(
        "/api/v1/connections/google/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 307
    assert "status=connected" in callback.headers["location"]

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth['accessToken']}"},
    )
    assert me.status_code == 200
    assert me.json()["avatarUrl"] == "https://lh3.googleusercontent.com/a/profile-photo"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": app_email, "password": "correct-horse-1"},
    )
    assert login.status_code == 200
    assert login.json()["avatarUrl"] == "https://lh3.googleusercontent.com/a/profile-photo"
