import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Refresh sớm hơn hạn thật, cùng biên độ với google.py/jira.py.
_REFRESH_SKEW_SECONDS = 60


def _authorize_url() -> str:
    return f"https://login.microsoftonline.com/{get_settings().microsoft_tenant}/oauth2/v2.0/authorize"


def _token_url() -> str:
    return f"https://login.microsoftonline.com/{get_settings().microsoft_tenant}/oauth2/v2.0/token"


def callback_url() -> str:
    settings = get_settings()
    return f"{settings.app_public_url}/api/v1/connections/outlook/callback"


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.microsoft_client_id:
        raise ValueError("MICROSOFT_CLIENT_ID chưa cấu hình.")
    params = {
        "client_id": settings.microsoft_client_id,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": settings.microsoft_scopes,
        "response_mode": "query",
        "state": state,
    }
    return f"{_authorize_url()}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise ValueError("MICROSOFT_CLIENT_ID/MICROSOFT_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url(),
        "scope": settings.microsoft_scopes,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(_token_url(), data=data)
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Đổi access token mới bằng refresh token. Microsoft CÓ THỂ xoay vòng
    refresh_token (không đảm bảo như Atlassian, không cố định như Google) —
    caller phải ghi đè refresh_token mới nếu response có, giữ bản cũ nếu không."""
    settings = get_settings()
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise ValueError("MICROSOFT_CLIENT_ID/MICROSOFT_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": settings.microsoft_scopes,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(_token_url(), data=data)
        response.raise_for_status()
        return response.json()


@dataclass(frozen=True)
class MicrosoftAccountProfile:
    email: str | None
    display_name: str | None


def _clean_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


async def fetch_account_profile(access_token: str) -> MicrosoftAccountProfile:
    """`mail` rỗng với nhiều tài khoản cá nhân (outlook.com) chưa cấu hình hộp
    thư chính — fallback `userPrincipalName`, gần như luôn là địa chỉ đăng
    nhập thật cho cả tài khoản cá nhân lẫn tổ chức."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{GRAPH_BASE}/me", headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            # Nuốt lỗi thành email=None trước đây từng làm mất luôn lý do thật
            # (thường là thiếu scope User.Read) — log lại status/body của
            # Graph để không phải đoán mù lần sau. Body lỗi Graph chỉ chứa mã
            # lỗi chuẩn, không có dữ liệu người dùng, an toàn để log.
            logger.warning(
                "Graph GET /me lỗi %d khi lấy profile Outlook: %s", response.status_code, response.text[:500]
            )
            return MicrosoftAccountProfile(email=None, display_name=None)
        payload = response.json()
        email = _clean_str(payload.get("mail")) or _clean_str(payload.get("userPrincipalName"))
        display_name = _clean_str(payload.get("displayName"))
        return MicrosoftAccountProfile(email=email.lower() if email else None, display_name=display_name)


async def ensure_valid_access_token(db: Session, connection) -> str:
    """Trả access token còn hạn (plaintext) cho connection Outlook, tự refresh
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
        raise ValueError("Kết nối Outlook không có refresh token, cần kết nối lại.")

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
