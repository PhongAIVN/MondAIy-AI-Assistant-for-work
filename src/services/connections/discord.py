from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from src.config import get_settings

AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
REVOKE_URL = "https://discord.com/api/oauth2/token/revoke"
ME_URL = "https://discord.com/api/users/@me"
SCOPE = "identify"


@dataclass(frozen=True)
class DiscordIdentity:
    """Stable Discord identity returned by `/users/@me`."""

    user_id: str
    label: str | None


def callback_url() -> str:
    settings = get_settings()
    return f"{settings.app_public_url}/api/v1/connections/discord/callback"


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.discord_client_id:
        raise ValueError("DISCORD_CLIENT_ID chưa cấu hình.")
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": callback_url(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "prompt": "consent",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_client_secret:
        raise ValueError("DISCORD_CLIENT_ID/DISCORD_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_url(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()


async def revoke_token(token: str) -> None:
    """Thu hồi access/refresh token phía Discord — revoke 1 trong 2 loại huỷ
    toàn bộ grant liên quan (theo docs Discord). Bắt buộc HTTP Basic auth
    bằng client_id/client_secret, KHÁC Google (chỉ cần chính token). Lỗi ở
    đây KHÔNG được chặn việc xoá connection local — caller tự bọc try/except."""
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_client_secret:
        raise ValueError("DISCORD_CLIENT_ID/DISCORD_CLIENT_SECRET chưa cấu hình.")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            REVOKE_URL,
            data={"token": token},
            auth=(settings.discord_client_id, settings.discord_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()


async def fetch_account_identity(access_token: str) -> DiscordIdentity | None:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            return None
        body = response.json()
        discord_user_id = str(body.get("id") or "").strip()
        if not discord_user_id:
            return None
        username = body.get("username")
        discriminator = body.get("discriminator")
        if username and discriminator and discriminator != "0":
            label = f"{username}#{discriminator}"
        else:
            label = username
        return DiscordIdentity(user_id=discord_user_id, label=label)


async def fetch_account_label(access_token: str) -> str | None:
    """Backward-compatible label-only helper for callers outside OAuth callback."""
    identity = await fetch_account_identity(access_token)
    return identity.label if identity else None
