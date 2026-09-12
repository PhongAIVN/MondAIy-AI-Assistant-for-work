import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from src.config import get_settings

# Giá trị này không phải bcrypt hash và luôn được chặn trước khi verify. Nó cho
# phép SQLite cũ còn `NOT NULL` tạo account Google-only mà không biến account
# đó thành account đăng nhập mật khẩu.
GOOGLE_ONLY_PASSWORD_SENTINEL = "!google-oauth-only!"

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def has_usable_password(password_hash: str | None) -> bool:
    return bool(password_hash and password_hash != GOOGLE_ONLY_PASSWORD_SENTINEL)


def _secret_key() -> str:
    settings = get_settings()
    if not settings.app_secret_key:
        raise RuntimeError("APP_SECRET_KEY chưa cấu hình — bắt buộc để ký JWT access/refresh token.")
    return settings.app_secret_key


def _create_token(user_id: int, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def create_access_token(user_id: int) -> tuple[str, int]:
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    token = _create_token(user_id, expires_delta, "access")
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    expires_delta = timedelta(days=settings.refresh_token_expire_days)
    return _create_token(user_id, expires_delta, "refresh")


def decode_token(token: str, expected_type: str) -> int:
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("Token không hợp lệ hoặc đã hết hạn.") from exc

    if payload.get("type") != expected_type:
        raise ValueError("Sai loại token.")

    sub = payload.get("sub")
    if sub is None:
        raise ValueError("Token thiếu subject.")
    return int(sub)


def generate_reset_token() -> str:
    """Token gửi qua email — random đủ entropy nên chỉ cần sha256 để tra cứu,
    không cần bcrypt (khác password, token này không phải thứ người dùng nhớ
    hay tái sử dụng, không có rủi ro dictionary attack)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
