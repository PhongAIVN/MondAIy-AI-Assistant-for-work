"""ensure_valid_access_token phải đánh dấu connection 'expired' khi Google
thu hồi/hết hạn refresh token (400/401), nhưng KHÔNG đánh dấu khi Google chỉ
tạm trục trặc (5xx) — retry lần sau vẫn còn cơ hội. Trước fix này, mọi lỗi
refresh đều rơi vào log rồi im lặng lặp lại mỗi vòng job nền
(calendar_auto_refresh) mà không ai biết cần kết nối lại (xem AGENTS.md
2026-08-27: job nền báo lỗi liên tục cho user 769, refresh_token đã chết)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from src.db import SessionLocal
from src.models.connection import Connection
from src.services.connections import google
from src.services.crypto import encrypt_token


def _seed_expired_connection(db, refresh_token: str | None = "fake-refresh-token") -> Connection:
    row = Connection(
        user_id=f"conn-google-{uuid.uuid4().hex[:12]}",
        provider="google",
        access_token_encrypted=encrypt_token("stale-access-token"),
        refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _mount_token_endpoint(monkeypatch: pytest.MonkeyPatch, status_code: int, body: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedClient)


@pytest.mark.asyncio
async def test_refresh_400_marks_connection_expired(monkeypatch):
    db = SessionLocal()
    try:
        row = _seed_expired_connection(db)
        _mount_token_endpoint(monkeypatch, 400, {"error": "invalid_grant"})

        with pytest.raises(httpx.HTTPStatusError):
            await google.ensure_valid_access_token(db, row)

        db.refresh(row)
        assert row.status == "expired"
        assert row.last_error
    finally:
        db.close()


@pytest.mark.asyncio
async def test_refresh_500_does_not_mark_connection_expired(monkeypatch):
    db = SessionLocal()
    try:
        row = _seed_expired_connection(db)
        _mount_token_endpoint(monkeypatch, 500, {"error": "internal"})

        with pytest.raises(httpx.HTTPStatusError):
            await google.ensure_valid_access_token(db, row)

        db.refresh(row)
        assert row.status != "expired"
        assert row.last_error is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_missing_refresh_token_marks_connection_expired():
    db = SessionLocal()
    try:
        row = _seed_expired_connection(db, refresh_token=None)

        with pytest.raises(ValueError):
            await google.ensure_valid_access_token(db, row)

        db.refresh(row)
        assert row.status == "expired"
        assert row.last_error
    finally:
        db.close()
