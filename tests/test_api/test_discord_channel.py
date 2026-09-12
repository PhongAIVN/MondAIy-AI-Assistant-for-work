import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from src.api import discord_channel
from src.api.discord_channel import verify_signature


def test_discord_signature_verification_accepts_valid_payload():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw().hex()
    body, timestamp = b'{"type":1}', "1700000000"
    signature = key.sign(timestamp.encode() + body).hex()
    verify_signature(public, signature, timestamp, body)


def test_discord_signature_verification_rejects_tampering():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw().hex()
    signature = key.sign(b"1700000000{}" ).hex()
    with pytest.raises(HTTPException) as exc:
        verify_signature(public, signature, "1700000000", b'{"type":1}')
    assert exc.value.status_code == 401


def test_discord_signature_verification_fails_when_unconfigured():
    with pytest.raises(HTTPException) as exc:
        verify_signature("", "00", "1", b"{}")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_discord_ask_uses_authenticated_mondaiy_pipeline(monkeypatch):
    calls = {}

    async def fake_handle(db, user_id, text):
        calls.update(db=db, user_id=user_id, text=text)
        return "Đã xử lý."

    monkeypatch.setattr(discord_channel, "handle_free_message", fake_handle)
    result = await discord_channel.answer_ask(db="db", user_id="user-1", text="  kiểm tra lịch ")

    assert result == "Đã xử lý."
    assert calls == {"db": "db", "user_id": "user-1", "text": "  kiểm tra lịch "}
