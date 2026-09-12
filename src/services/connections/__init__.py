import logging

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.connection import Connection
from src.services.connections import discord, google, slack
from src.services.crypto import decrypt_token

logger = logging.getLogger(__name__)

_DEAD_CONNECTION_STATUSES = ("disconnected", "error", "expired", "revoked")


def preferred_connection(
    db: Session,
    user_id: str,
    provider: str = "google",
    *,
    connection_id: int | None = None,
    include_dead: bool = False,
) -> Connection | None:
    """Chọn một connection rõ ràng cho consumer cũ chưa truyền account id.

    Các API mới có thể truyền `connection_id`; fallback deterministic dùng
    connection active gần nhất để nhiều Google account không làm query scalar
    nổ hoặc vô tình chọn một row ngẫu nhiên.
    """
    statement = select(Connection).where(
        Connection.user_id == str(user_id),
        Connection.provider == provider,
    )
    if not include_dead:
        # Old pilot rows can have NULL status because the state-machine columns
        # were added after the table was first created; keep those rows usable.
        statement = statement.where(
            or_(
                Connection.status.is_(None),
                Connection.status.notin_(_DEAD_CONNECTION_STATUSES),
            )
        )
    if connection_id is not None:
        statement = statement.where(Connection.id == connection_id)
    return db.scalars(
        statement.order_by(Connection.connected_at.desc(), Connection.id.desc())
    ).first()


async def revoke_connection_tokens(connection: Connection) -> None:
    """Best-effort thu hồi token phía provider trước khi xoá row local.

    Google/Discord có API revoke token thật. Jira (Atlassian OAuth 2.0 3LO)
    và Outlook (Microsoft identity platform) KHÔNG có endpoint app-initiated
    revoke công khai — đã xác nhận qua docs chính thức của 2 provider đó,
    không phải thiếu sót ở đây. User phải tự vào trang quản lý app của
    provider đó (id.atlassian.com/manage-profile hoặc myaccount.microsoft.com)
    để thu hồi hoàn toàn — không có cách nào app tự làm được thay.

    Gọi qua `google.revoke_token`/`discord.revoke_token` (thuộc tính module,
    tra cứu lúc chạy) thay vì bind function object vào dict ở module scope —
    bind sẵn sẽ khiến monkeypatch trong test không có tác dụng.

    Lỗi ở đây KHÔNG ĐƯỢC chặn việc xoá connection local — dù revoke thành
    công hay không, connection vẫn phải biến mất khỏi app ngay khi user bấm
    Ngắt kết nối / xoá tài khoản (không được kẹt vì lỗi mạng phía thứ ba)."""
    if connection.provider == "google":
        revoke_fn = google.revoke_token
    elif connection.provider == "discord":
        revoke_fn = discord.revoke_token
    elif connection.provider == "slack":
        revoke_fn = slack.revoke_token
    else:
        return

    token_encrypted = connection.access_token_encrypted or connection.refresh_token_encrypted
    if not token_encrypted:
        return

    try:
        token = decrypt_token(token_encrypted)
        await revoke_fn(token)
    except Exception as exc:  # noqa: BLE001 - xem docstring, không được chặn xoá connection
        logger.warning("Revoke token %s thất bại (vẫn xoá connection local): %s", connection.provider, exc)
