from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

# Refresh sớm hơn hạn thật để tránh race giữa lúc connector gọi API và lúc
# access token thực sự hết hạn.
_REFRESH_SKEW_SECONDS = 60


@dataclass(frozen=True)
class GoogleAccountProfile:
    email: str | None
    picture: str | None


def callback_url() -> str:
    settings = get_settings()
    if settings.google_redirect_uri:
        return settings.google_redirect_uri
    # Phải khớp y hệt URI đã đăng ký trên Google Cloud Console (đã test thật,
    # xem ghi chú OAuth trong .env). /gmail/oauth/callback chỉ là alias trỏ về
    # cùng handler (src/api/connections.py), không đăng ký trên Console.
    return f"{settings.app_public_url}/api/v1/connections/google/callback"


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID chưa cấu hình.")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": settings.google_scopes,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def build_login_authorize_url(state: str) -> str:
    """Đăng nhập và cấp toàn bộ quyền Google của Mondaiy trong một consent.

    Cùng `google_scopes` với luồng kết nối nguồn sau đăng nhập để người dùng
    mới không phải xác thực Google lần thứ hai khi mở Gmail, Calendar, Drive,
    Docs hoặc Sheets. `prompt=consent` vẫn đảm bảo có refresh token.
    """
    settings = get_settings()
    if not settings.google_client_id:
        raise ValueError("GOOGLE_CLIENT_ID chưa cấu hình.")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": settings.google_scopes,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()


def _safe_picture_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    picture = value.strip()
    parsed = urlsplit(picture)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return picture[:2048]


REVOKE_URL = "https://oauth2.googleapis.com/revoke"


async def revoke_token(token: str) -> None:
    """Thu hồi access/refresh token phía Google — gọi được với 1 trong 2 loại,
    Google tự suy ra và huỷ toàn bộ grant liên quan. Không cần client
    id/secret (chính token đã là bằng chứng sở hữu). Lỗi ở đây KHÔNG được
    chặn việc xoá connection local — caller tự quyết bọc try/except."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(REVOKE_URL, data={"token": token})
        response.raise_for_status()


async def fetch_account_profile(access_token: str) -> GoogleAccountProfile:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            return GoogleAccountProfile(email=None, picture=None)
        payload = response.json()
        raw_email = payload.get("email")
        email = raw_email.strip() if isinstance(raw_email, str) and raw_email.strip() else None
        return GoogleAccountProfile(
            email=email,
            picture=_safe_picture_url(payload.get("picture")),
        )


async def fetch_account_label(access_token: str) -> str | None:
    """Giữ API cũ cho caller ngoài repo; code mới dùng toàn bộ profile."""
    return (await fetch_account_profile(access_token)).email


async def refresh_access_token(refresh_token: str) -> dict:
    """Đổi access token mới bằng refresh token. Google KHÔNG trả refresh_token
    mới trong response này — giữ nguyên cái đã lưu."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()


async def ensure_valid_access_token(db: Session, connection) -> str:
    """Trả access token còn hạn (plaintext) cho connection Google, tự refresh
    và ghi lại DB nếu đã hết hạn. `connection` là instance src.models.connection.Connection."""
    from src.services.crypto import decrypt_token, encrypt_token

    now = datetime.now(UTC)
    expires_at = connection.expires_at
    # SQLite may deserialize timezone-aware columns as naive datetimes.
    # Treat those values as UTC before comparing with the aware clock.
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    is_expired = expires_at is None or expires_at <= now + timedelta(seconds=_REFRESH_SKEW_SECONDS)
    if not is_expired:
        return decrypt_token(connection.access_token_encrypted)

    if not connection.refresh_token_encrypted:
        connection.status = "expired"
        connection.last_error = "Kết nối Google không có refresh token, cần kết nối lại."
        db.commit()
        raise ValueError(connection.last_error)

    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    try:
        token_data = await refresh_access_token(refresh_token)
    except httpx.HTTPStatusError as exc:
        # 400/401 nghĩa là Google đã thu hồi/hết hạn refresh token — lỗi
        # KHÔNG tự hết (retry lại vẫn 400), phải người dùng kết nối lại thật.
        # Đánh dấu ngay ở đây thay vì để lỗi rơi vào log rồi im lặng lặp lại
        # mỗi vòng job nền: `_DEAD_STATUSES` (calendar_auto_refresh.py) đã
        # loại status "expired" khỏi hàng đợi retry, nên set xong là hết spam.
        # 5xx/timeout thì KHÔNG đánh dấu — đó là Google tạm trục trặc, refresh
        # token vẫn tốt, lần sau thử lại bình thường.
        if exc.response is not None and exc.response.status_code in (400, 401):
            connection.status = "expired"
            connection.last_error = "Google đã thu hồi hoặc làm hết hạn quyền truy cập — cần kết nối lại."
            db.commit()
        raise

    new_access_token = token_data["access_token"]
    connection.access_token_encrypted = encrypt_token(new_access_token)
    expires_in = token_data.get("expires_in")
    connection.expires_at = now + timedelta(seconds=expires_in) if expires_in else None
    db.commit()

    return new_access_token
