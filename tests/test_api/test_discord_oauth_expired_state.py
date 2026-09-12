"""State OAuth hết hạn phải kết thúc bằng redirect, không phải 400 JSON thô.

`discord_callback` từng gọi `oauth_state.verify_intent` trong một try/except
riêng, raise thẳng `HTTPException(400)` khi state hết hạn — trước khi vào block
try bên trong vốn xử lý mọi lỗi khác (ví dụ exchange_failed) bằng cách redirect
về `ext_redirect_uri` qua `_finish`. Người dùng mất hơn 5 phút ở màn hình
login/consent của Discord (2FA, tab cũ...) vì vậy nhận một trang JSON lỗi thô
trên API host thay vì được đưa về web app kèm toast lỗi như các nhánh khác.
"""

import uuid

import pytest

from src.services import oauth_state

CONN_PREFIX = "/api/v1/connections"


async def _register(client) -> str:
    email = f"discord-expired-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1"},
    )
    assert response.status_code == 201, response.text
    return response.json()["userId"]


@pytest.mark.asyncio
async def test_discord_callback_voi_state_het_han_thi_redirect_ve_ext_uri(client, monkeypatch):
    user_id = await _register(client)
    ext_redirect_uri = "http://localhost:3000/sources"

    state = oauth_state.sign_intent(user_id, "discord", ext_redirect_uri)

    # Giá trị âm khiến token vừa ký luôn quá hạn, không cần chờ đồng hồ thật.
    monkeypatch.setattr(oauth_state, "INTENT_MAX_AGE_SECONDS", -1)

    response = await client.get(
        f"{CONN_PREFIX}/discord/callback",
        params={"code": "irrelevant-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303, 307), response.text
    location = response.headers["location"]
    assert location.startswith(ext_redirect_uri)
    assert "status=error" in location
    assert "message=state_expired" in location


@pytest.mark.asyncio
async def test_discord_callback_voi_state_khong_hop_le_van_400(client):
    """State bị giả mạo/garbage (BadSignature) không có payload đáng tin cậy
    để khôi phục ext_redirect_uri an toàn — vẫn phải từ chối bằng 400, không
    được đoán bừa đích redirect (tránh open redirect)."""
    response = await client.get(
        f"{CONN_PREFIX}/discord/callback",
        params={"code": "irrelevant-code", "state": "not-a-real-state-token"},
        follow_redirects=False,
    )
    assert response.status_code == 400, response.text
