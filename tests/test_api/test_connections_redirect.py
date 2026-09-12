"""Chặn open redirect ở luồng khởi tạo kết nối OAuth.

ext_redirect_uri do client gửi rồi được ký lại trong state token; nếu backend
không chốt allowlist thì sau khi OAuth xong nó sẽ 302 người dùng tới URL bất kỳ.
Test kiểm hành vi observable: origin ngoài bị 400, còn đích hợp lệ (origin CORS
của web-app và đích chromiumapp của extension) vẫn qua được.
"""

import uuid

import pytest

from src.api.connections import _finish

CONN_PREFIX = "/api/v1/connections"


def test_callback_redirect_url_encodes_backend_message():
    response = _finish(
        "http://localhost:3000/sources",
        "discord",
        "error",
        "Không thể đổi mã & hãy thử lại",
    )

    assert response.headers["location"] == (
        "http://localhost:3000/sources?status=error&provider=discord&message=Kh%C3%B4ng+th%E1%BB%83+%C4%91%E1%BB%95i+m%C3%A3+%26+h%C3%A3y+th%E1%BB%AD+l%E1%BA%A1i"
    )


async def _register(client) -> str:
    email = f"redir-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1"},
    )
    assert response.status_code == 201, response.text
    return response.json()["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_uri",
    [
        "https://evil.example.com/steal",
        "http://attacker.test/",
        "https://phishing.chromiumapp.org.evil.com/",
        "javascript:alert(1)",
        "//evil.example.com",
        "",
    ],
)
async def test_intent_tu_choi_redirect_ngoai_allowlist(client, bad_uri):
    token = await _register(client)
    response = await client.post(
        f"{CONN_PREFIX}/google/intent",
        headers=_auth(token),
        json={"extRedirectUri": bad_uri},
    )
    assert response.status_code == 400, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "good_uri",
    [
        "http://localhost:3000/sources",
        "http://localhost:5173/tasks",
        "mondaiy://auth/callback",
        "https://abcdef.chromiumapp.org/",
        "chrome-extension://abcdefghijklmnop/callback.html",
    ],
)
async def test_intent_nhan_dich_hop_le(client, good_uri):
    token = await _register(client)
    response = await client.post(
        f"{CONN_PREFIX}/google/intent",
        headers=_auth(token),
        json={"extRedirectUri": good_uri},
    )
    assert response.status_code == 200, response.text
    assert response.json()["authorizeUrl"].startswith("http")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "outlook", "jira", "discord", "slack"])
async def test_native_callback_allowlist_applies_to_every_oauth_provider(client, provider):
    token = await _register(client)
    response = await client.post(
        f"{CONN_PREFIX}/{provider}/intent",
        headers=_auth(token),
        json={"extRedirectUri": "mondaiy://auth/callback"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["authorizeUrl"].startswith(
        f"http://localhost:8000/api/v1/connections/{provider}/start?intent="
    )


@pytest.mark.asyncio
async def test_gmail_oauth_start_cung_ap_dung_allowlist(client):
    token = await _register(client)
    bad = await client.post(
        f"{CONN_PREFIX}/gmail/oauth/start",
        headers=_auth(token),
        json={"extRedirectUri": "https://evil.example.com/"},
    )
    assert bad.status_code == 400, bad.text

    ok = await client.post(
        f"{CONN_PREFIX}/gmail/oauth/start",
        headers=_auth(token),
        json={"extRedirectUri": "http://localhost:3000/sources"},
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_intent_khong_token_thi_401(client):
    response = await client.post(
        f"{CONN_PREFIX}/google/intent",
        json={"extRedirectUri": "https://evil.example.com/"},
    )
    assert response.status_code == 401
