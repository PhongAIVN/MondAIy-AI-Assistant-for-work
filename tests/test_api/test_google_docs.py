"""Test quyền và contract endpoint đọc Google Docs."""

import uuid

import pytest

from src.db import SessionLocal
from src.models.connection import Connection


async def _register(client) -> tuple[str, str]:
    email = f"doc-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "displayName": "Nguyễn Văn An"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["userId"], body["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_DOC_URL = "https://docs.google.com/document/d/1AbcdefghijklmnopqrstuvwxYZ_1234567890/edit"


def _fake_read_document(monkeypatch, text: str = "Việc A", revision: str = "rev-1"):
    """Chặn lượt gọi Google Docs API thật; endpoint đọc nội dung để tính khoá cache."""
    from src.connectors.google_docs import DocumentSnapshot

    async def fake_read(self, document_id: str) -> DocumentSnapshot:
        return DocumentSnapshot(text=text, truncated=False, revision=f"{revision}-{uuid.uuid4().hex[:8]}")

    monkeypatch.setattr("src.api.google_docs.GoogleDocsConnector.read_document", fake_read)


@pytest.mark.asyncio
async def test_google_docs_requires_a_connection(client):
    _, token = await _register(client)
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentUrl": _DOC_URL},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_google_docs_requires_documents_readonly_scope(client):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                scopes="openid email https://www.googleapis.com/auth/spreadsheets.readonly",
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentUrl": _DOC_URL},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_google_docs_returns_proposals_after_scope_check(client, monkeypatch):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                scopes="openid email https://www.googleapis.com/auth/documents.readonly",
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    async def fake_proposals(self, **_kwargs):
        return [
            {
                "paragraph_index": 0,
                "title": "Hoàn thành báo cáo",
                "detail": "Báo cáo quý",
                "assignee": "Nguyễn Văn An",
                "due_at": None,
                "all_day": False,
                "matched_user": True,
                "needs_confirmation": False,
                "clarification_question": None,
                "date_ambiguous": False,
                "source": "Google Docs",
                "source_url": "https://docs.google.com/document/d/doc-id/edit",
            }
        ]

    monkeypatch.setattr("src.api.google_docs.GoogleDocsConnector.task_proposals", fake_proposals)
    _fake_read_document(monkeypatch)
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentUrl": _DOC_URL},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["proposals"][0]["title"] == "Hoàn thành báo cáo"
    assert body["documentId"] == "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    # Contract mở rộng: hai field chống spam token luôn có mặt.
    assert body["truncated"] is False
    assert body["quotaRemaining"] >= 0


@pytest.mark.asyncio
async def test_google_docs_returns_502_on_connector_api_error(client, monkeypatch):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                scopes="openid email https://www.googleapis.com/auth/documents.readonly",
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    from src.connectors.google_docs import GoogleDocsAPIError

    async def failing_proposals(self, **_kwargs):
        raise GoogleDocsAPIError("Google Docs API lỗi 500 khi đọc tài liệu.")

    monkeypatch.setattr("src.api.google_docs.GoogleDocsConnector.task_proposals", failing_proposals)
    _fake_read_document(monkeypatch)
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentUrl": _DOC_URL},
    )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_google_docs_rejects_non_google_url_with_422(client):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                scopes="openid email https://www.googleapis.com/auth/documents.readonly",
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentUrl": "https://example.com/document/d/not-google"},
    )
    assert response.status_code == 422
