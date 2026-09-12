from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings

AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"
ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"
# Danh tính người dùng lấy từ endpoint TÀI KHOẢN ATLASSIAN, không phải
# /rest/api/3/myself của Jira. Hai cái cần scope khác nhau: `/myself` đòi
# `read:jira-user`, còn `jira_scopes` mặc định chỉ xin `read:me`. Bug thật:
# `fetch_account_id` gọi `/myself` và ăn 401, trả None lặng lẽ — kết nối vẫn
# báo thành công với accountId rỗng, khiến jira_rules không bao giờ đối chiếu
# được assignee với người dùng.
ACCOUNT_URL = "https://api.atlassian.com/me"

# Refresh sớm hơn hạn thật, cùng biên độ với google.py.
_REFRESH_SKEW_SECONDS = 60


def callback_url() -> str:
    settings = get_settings()
    return f"{settings.app_public_url}/api/v1/connections/jira/callback"


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.jira_client_id:
        raise ValueError("JIRA_CLIENT_ID chưa cấu hình.")
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.jira_client_id,
        "scope": settings.jira_scopes,
        "redirect_uri": callback_url(),
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    if not settings.jira_client_id or not settings.jira_client_secret:
        raise ValueError("JIRA_CLIENT_ID/JIRA_CLIENT_SECRET chưa cấu hình.")

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.jira_client_id,
        "client_secret": settings.jira_client_secret,
        "code": code,
        "redirect_uri": callback_url(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, json=data)
        response.raise_for_status()
        return response.json()


async def fetch_accessible_resource(access_token: str) -> dict | None:
    """1 site Jira Cloud user vừa cấp quyền — {id: cloudId, url, name, scopes}.
    Pilot giả định 1 site/user, lấy resource đầu tiên; nhiều site là backlog."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(ACCESSIBLE_RESOURCES_URL, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            return None
        resources = response.json()
        return resources[0] if resources else None


async def fetch_account_id(access_token: str, cloud_id: str) -> str | None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(ACCOUNT_URL, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            return None
        # `/me` trả snake_case `account_id`; `/myself` của Jira trả `accountId`.
        return response.json().get("account_id")


async def refresh_access_token(refresh_token: str) -> dict:
    """Đổi access token mới bằng refresh token. KHÁC Google: Atlassian XOAY
    VÒNG refresh_token — mỗi lần refresh trả refresh_token MỚI, bản cũ hết
    hạn. Caller bắt buộc lưu đè refresh_token mới, không được giữ bản cũ."""
    settings = get_settings()
    if not settings.jira_client_id or not settings.jira_client_secret:
        raise ValueError("JIRA_CLIENT_ID/JIRA_CLIENT_SECRET chưa cấu hình.")

    data = {
        "grant_type": "refresh_token",
        "client_id": settings.jira_client_id,
        "client_secret": settings.jira_client_secret,
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, json=data)
        response.raise_for_status()
        return response.json()


async def ensure_valid_access_token(db: Session, connection) -> str:
    """Trả access token còn hạn (plaintext) cho connection Jira, tự refresh
    và ghi lại DB nếu đã hết hạn. `connection` là instance src.models.connection.Connection."""
    from src.services.crypto import decrypt_token, encrypt_token

    now = datetime.now(UTC)
    expires_at = connection.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    is_expired = expires_at is None or expires_at <= now + timedelta(seconds=_REFRESH_SKEW_SECONDS)
    if not is_expired:
        return decrypt_token(connection.access_token_encrypted)

    if not connection.refresh_token_encrypted:
        raise ValueError("Kết nối Jira không có refresh token, cần kết nối lại.")

    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    new_access_token = token_data["access_token"]
    connection.access_token_encrypted = encrypt_token(new_access_token)
    new_refresh_token = token_data.get("refresh_token")
    if new_refresh_token:
        connection.refresh_token_encrypted = encrypt_token(new_refresh_token)
    expires_in = token_data.get("expires_in")
    connection.expires_at = now + timedelta(seconds=expires_in) if expires_in else None
    db.commit()

    return new_access_token
