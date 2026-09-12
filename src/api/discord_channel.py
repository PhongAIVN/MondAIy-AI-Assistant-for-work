"""Discord Interactions endpoint for the private Mondaiy bot surface."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db import SessionLocal, get_db
from src.models.connection import Connection
from src.models.user import User
from src.services.telegram_channel import _claim_receipt
from src.services.telegram_chat import handle_free_message

router = APIRouter(prefix="/channels/discord", tags=["discord-channel"])
logger = logging.getLogger(__name__)


def verify_signature(public_key: str, signature: str | None, timestamp: str | None, body: bytes) -> None:
    if not public_key:
        raise HTTPException(status_code=503, detail="Discord interactions chưa được cấu hình.")
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Thiếu chữ ký Discord.")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
            bytes.fromhex(signature), timestamp.encode() + body
        )
    except (ValueError, InvalidSignature):
        raise HTTPException(status_code=401, detail="Chữ ký Discord không hợp lệ.") from None


def _linked_user(db: Session, discord_user_id: str) -> str | None:
    row = db.execute(select(Connection).where(Connection.provider == "discord", Connection.provider_user_id == discord_user_id)).scalar_one_or_none()
    if row is None:
        return None
    user = db.get(User, int(row.user_id))
    return str(row.user_id) if user is not None and user.is_active else None


async def answer_ask(*, db: Session, user_id: str, text: str) -> str:
    """Run the authenticated Mondaiy pipeline used by the private chat channel."""
    if not text:
        return "Hãy nhập câu hỏi sau /ask."
    return await handle_free_message(db, user_id, text)


async def send_response(channel_id: str, text: str) -> dict[str, Any]:
    token = get_settings().discord_bot_token.strip()
    if not token:
        raise HTTPException(status_code=503, detail="DISCORD_BOT_TOKEN chưa cấu hình.")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {token}"}, json={"content": text[:2000]},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Discord gửi phản hồi lỗi HTTP {response.status_code}.")
    return response.json()


async def _answer_and_send(channel_id: str, user_id: str, text: str) -> None:
    try:
        with SessionLocal() as session:
            answer = await answer_ask(db=session, user_id=user_id, text=text)
        await send_response(channel_id, answer)
    except Exception:
        logger.exception("Discord Mondaiy response failed for user %s", user_id)
        try:
            await send_response(channel_id, "Mondaiy chưa thể trả lời lúc này. Hãy thử lại sau.")
        except Exception:
            logger.exception("Discord error response failed for user %s", user_id)


@router.post("/interactions")
async def discord_interaction(
    request: Request,
    background_tasks: BackgroundTasks,
    signature: str | None = Header(default=None, alias="X-Signature-Ed25519"),
    timestamp: str | None = Header(default=None, alias="X-Signature-Timestamp"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await request.body()
    verify_signature(get_settings().discord_public_key, signature, timestamp, body)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload Discord không phải JSON.") from None
    if payload.get("type") == 1:  # PING
        return {"type": 1}
    event_id = str(payload.get("id") or "")
    if not event_id:
        raise HTTPException(status_code=400, detail="Interaction thiếu id.")
    if not _claim_receipt(db, "discord-interaction", event_id):
        return {"type": 6}
    member = payload.get("member") or {}
    sender = member.get("user") or payload.get("user") or {}
    user_id = _linked_user(db, str(sender.get("id") or ""))
    if user_id is None:
        return {"type": 4, "data": {"content": "Discord này chưa liên kết với Mondaiy.", "flags": 64}}
    data = payload.get("data") or {}
    if data.get("name") != "ask":
        return {"type": 4, "data": {"content": "Mondaiy hỗ trợ lệnh /ask <câu hỏi>.", "flags": 64}}
    options = data.get("options") or []
    text = str(options[0].get("value") or "").strip() if options else ""
    if not text:
        return {"type": 4, "data": {"content": "Hãy nhập câu hỏi sau /ask.", "flags": 64}}
    # Không trả lời trong guild/group channel: câu trả lời có thể chứa dữ liệu
    # riêng từ các nguồn đã kết nối. Discord DM (type=1) là boundary an toàn.
    channel = payload.get("channel") if isinstance(payload.get("channel"), dict) else {}
    if channel.get("type") != 1:
        return {"type": 4, "data": {"content": "Mondaiy chỉ trả lời /ask trong tin nhắn riêng.", "flags": 64}}
    channel_id = str(payload.get("channel_id") or "")
    if not channel_id:
        raise HTTPException(status_code=400, detail="Interaction thiếu channel_id.")
    background_tasks.add_task(_answer_and_send, channel_id, user_id, text)
    return {"type": 5, "data": {"flags": 64}}
