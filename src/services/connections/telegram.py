import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.channel_delivery import TelegramLinkIntent
from src.models.connection import Connection

AUTHORIZE_URL = "https://oauth.telegram.org/auth"
AUTH_MAX_AGE_SECONDS = 5 * 60
LINK_MAX_AGE_MINUTES = 10


def _as_utc(value: datetime) -> datetime:
    """SQLite strips timezone info from DateTime(timezone=True)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class TelegramIdentity:
    user_id: str
    account_label: str


def _as_utc(value: datetime) -> datetime:
    """Normalize DB timestamps; SQLite may strip timezone information."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def callback_url() -> str:
    return f"{_login_origin()}/api/v1/connections/telegram/callback"


def _login_origin() -> str:
    """Use the user-facing HTTPS origin registered with BotFather.

    Vercel proxies ``/api`` to the backend, so the callback still reaches the
    FastAPI route while Telegram sees one consistent web domain.
    """
    settings = get_settings()
    origin = (settings.web_app_public_url or settings.app_public_url).strip().rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
        raise ValueError("Telegram Login yêu cầu WEB_APP_PUBLIC_URL là HTTPS origin hợp lệ.")
    return origin


def build_authorize_url(state: str) -> str:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN chưa cấu hình.")
    bot_id = settings.telegram_bot_token.split(":", 1)[0]
    params = {
        "bot_id": bot_id,
        "origin": _login_origin(),
        "embed": "0",
        "request_access": "write",
        "return_to": f"{callback_url()}?state={state}",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def create_bot_link(db: Session, user_id: str) -> str:
    settings = get_settings()
    username = settings.telegram_bot_username.strip().lstrip("@")
    if not username:
        raise ValueError("TELEGRAM_BOT_USERNAME chưa cấu hình.")
    token = secrets.token_urlsafe(24)
    db.add(
        TelegramLinkIntent(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=LINK_MAX_AGE_MINUTES),
        )
    )
    db.commit()
    return f"https://t.me/{username}?start=link_{token}"


def consume_bot_link(
    db: Session,
    token: str,
    *,
    telegram_user_id: str,
    account_label: str,
) -> str | None:
    now = datetime.now(UTC)
    row = db.execute(
        select(TelegramLinkIntent)
        .where(TelegramLinkIntent.token_hash == hashlib.sha256(token.encode()).hexdigest())
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or _as_utc(row.expires_at) < now:
        return None
    linked_elsewhere = db.execute(
        select(Connection).where(
            Connection.provider == "telegram",
            Connection.provider_user_id == telegram_user_id,
            Connection.user_id != row.user_id,
        )
    ).scalar_one_or_none()
    if linked_elsewhere is not None:
        return None
    connection = db.execute(
        select(Connection).where(Connection.user_id == row.user_id, Connection.provider == "telegram")
    ).scalar_one_or_none()
    connection = connection or Connection(user_id=row.user_id, provider="telegram")
    connection.provider_user_id = telegram_user_id
    connection.account_label = account_label
    connection.connected_at = now
    row.used_at = now
    if connection.id is None:
        db.add(connection)
    db.commit()
    return row.user_id


def verify_identity(payload: dict[str, str]) -> TelegramIdentity | None:
    """Verify Login Widget và trả định danh cần cho private-chat delivery."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN chưa cấu hình.")

    received_hash = payload.get("hash")
    if not received_hash:
        return None

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()) if key != "hash")
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    try:
        auth_date = int(payload.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date <= 0 or abs(time.time() - auth_date) > AUTH_MAX_AGE_SECONDS:
        return None

    user_id = payload.get("id", "").strip()
    if not user_id.isdigit():
        return None
    label = payload.get("username") or payload.get("first_name") or f"telegram:{user_id}"
    return TelegramIdentity(user_id=user_id, account_label=label)


def verify_payload(payload: dict[str, str]) -> str | None:
    """Compatibility wrapper cho caller cũ chỉ cần nhãn tài khoản."""
    identity = verify_identity(payload)
    return identity.account_label if identity else None
