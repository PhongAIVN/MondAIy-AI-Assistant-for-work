"""Xác thực và thu hồi credential Sign in with Apple."""

import time
from typing import Any

import httpx
import jwt

from src.config import get_settings

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_REVOKE_URL = "https://appleid.apple.com/auth/revoke"


def verify_identity_token(identity_token: str) -> dict[str, Any]:
    """Verify chữ ký, issuer và audience trước khi dùng bất kỳ claim nào."""
    settings = get_settings()
    if not settings.apple_client_id:
        raise ValueError("Đăng nhập Apple chưa được cấu hình.")

    try:
        signing_key = jwt.PyJWKClient(APPLE_JWKS_URL).get_signing_key_from_jwt(identity_token)
        claims = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer=APPLE_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Apple identity token không hợp lệ.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise ValueError("Apple identity token thiếu định danh tài khoản.")
    return claims


def _client_secret() -> str:
    settings = get_settings()
    if not all((settings.apple_team_id, settings.apple_key_id, settings.apple_private_key, settings.apple_client_id)):
        raise ValueError("Apple token revocation chưa được cấu hình đầy đủ.")
    private_key = settings.apple_private_key.replace("\\n", "\n")
    now = int(time.time())
    return str(jwt.encode(
        {"iss": settings.apple_team_id, "iat": now, "exp": now + 300, "aud": APPLE_ISSUER, "sub": settings.apple_client_id},
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    ))


async def exchange_authorization_code(authorization_code: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(APPLE_TOKEN_URL, data={
            "client_id": settings.apple_client_id,
            "client_secret": _client_secret(),
            "code": authorization_code,
            "grant_type": "authorization_code",
        })
        response.raise_for_status()
        refresh_token = response.json().get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise ValueError("Apple không trả về refresh token.")
    return refresh_token


async def revoke_refresh_token(refresh_token: str) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(APPLE_REVOKE_URL, data={
            "client_id": settings.apple_client_id,
            "client_secret": _client_secret(),
            "token": refresh_token,
            "token_type_hint": "refresh_token",
        })
        response.raise_for_status()
