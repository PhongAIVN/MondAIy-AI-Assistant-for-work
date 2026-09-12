from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings

AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.access"
REVOKE_URL = "https://slack.com/api/auth.revoke"
TEAM_INFO_URL = "https://slack.com/api/team.info"


@dataclass(frozen=True)
class SlackIdentity:
    """User + workspace định danh trả về thẳng trong OAuth v2 response —
    KHÁC Jira: không cần gọi accessible-resources riêng để dò site/cloud_id,
    Slack trả team_id ngay trong bước exchange_code()."""

    user_id: str
    team_id: str
    team_domain: str | None


def callback_url() -> str:
    settings = get_settings()
    return f"{settings.app_public_url}/api/v1/connections/slack/callback"


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.slack_client_id:
        raise ValueError("SLACK_CLIENT_ID chưa cấu hình.")
    params = {
        "client_id": settings.slack_client_id,
        # user_scope (không phải "scope") — xin quyền đọc thay mặt CHÍNH
        # user đang kết nối, không tạo bot token riêng phải mời vào từng
        # channel/DM (khác pattern Discord bot/Jira app cài vào site).
        "user_scope": settings.slack_user_scopes,
        "redirect_uri": callback_url(),
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    """Trả body thô của oauth.v2.access. Token thật nằm ở body["authed_user"]
    ("access_token", "id" = slack_user_id) — KHÁC Discord/Jira nơi access_token
    nằm thẳng ở top-level, vì đây là user token (authed_user), không phải bot
    token (top-level "access_token" nếu có "scope" bot cũng được cấp)."""
    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise ValueError("SLACK_CLIENT_ID/SLACK_CLIENT_SECRET chưa cấu hình.")

    data = {
        "client_id": settings.slack_client_id,
        "client_secret": settings.slack_client_secret,
        "code": code,
        "redirect_uri": callback_url(),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise ValueError(f"Slack OAuth exchange thất bại: {body.get('error', 'unknown_error')}")
        return body


async def fetch_team_domain(access_token: str) -> str | None:
    """domain workspace (vd "mondaiy") để dựng deep_link kiểu
    https://{domain}.slack.com/archives/... — cần scope team:read.
    Trả None nếu lỗi/thiếu scope, deep_link() tự fallback sang app.slack.com."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(TEAM_INFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if response.status_code != 200:
            return None
        body = response.json()
        if not body.get("ok"):
            return None
        return (body.get("team") or {}).get("domain")


async def revoke_token(token: str) -> None:
    """auth.revoke — Slack CÓ endpoint app-initiated revoke (khác Jira/Outlook,
    xem services/connections/__init__.py). Chỉ cần token, không cần
    client_id/secret kèm theo (khác Discord)."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(REVOKE_URL, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        body = response.json()
        if not body.get("ok") and body.get("error") != "already_revoked":
            raise ValueError(f"Slack revoke thất bại: {body.get('error', 'unknown_error')}")


async def ensure_valid_access_token(db: Session, connection) -> str:
    """Slack user token (OAuth v2, không bật token rotation) không hết hạn,
    không có refresh_token — KHÁC Jira/Google. Chỉ giải mã token đã lưu; lỗi
    401 thật (token bị user thu hồi thủ công phía Slack) để caller
    (SlackConnector) bắt và báo cần kết nối lại, không đoán trước ở đây."""
    from src.services.crypto import decrypt_token

    if not connection.access_token_encrypted:
        raise ValueError("Kết nối Slack không có access token, cần kết nối lại.")
    return decrypt_token(connection.access_token_encrypted)


def parse_identity(token_data: dict) -> SlackIdentity | None:
    authed_user = token_data.get("authed_user") or {}
    team = token_data.get("team") or {}
    user_id = authed_user.get("id")
    team_id = team.get("id")
    if not user_id or not team_id:
        return None
    return SlackIdentity(user_id=user_id, team_id=team_id, team_domain=None)
