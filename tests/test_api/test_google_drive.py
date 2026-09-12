"""Test endpoint duyệt/tìm file Google Drive (picker Docs & Sheets).

Mọi lời gọi mạng đi qua `httpx.MockTransport`, không test nào chạm Google.
"""

import uuid

import httpx
import pytest

from src.connectors.google_drive import MIME_DOCUMENT, MIME_SPREADSHEET, build_query
from src.db import SessionLocal
from src.models.connection import Connection

_DRIVE_SCOPES = (
    "openid email https://www.googleapis.com/auth/documents.readonly https://www.googleapis.com/auth/drive.readonly"
)


async def _register(client) -> tuple[str, str]:
    email = f"drive-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "displayName": "Nguyễn Văn An"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["userId"], body["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _connect(user_id: str, scopes: str = _DRIVE_SCOPES) -> None:
    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", scopes=scopes, status="connected_ready"))
        db.commit()
    finally:
        db.close()


def mount_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    """Ép mọi AsyncClient tạo sau lời gọi này đi qua transport giả."""
    seen: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(recording_handler)
    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedClient)
    return seen


def fake_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _token(_db, _connection):
        return "fake-access-token"

    monkeypatch.setattr("src.services.connections.google.ensure_valid_access_token", _token)


@pytest.mark.asyncio
async def test_drive_files_requires_a_connection(client):
    _, token = await _register(client)
    response = await client.get("/api/v1/google-drive/files", headers=_auth(token))
    assert response.status_code == 409
    assert "Google" in response.json()["detail"]


@pytest.mark.asyncio
async def test_drive_files_requires_drive_readonly_scope(client):
    user_id, token = await _register(client)
    _connect(user_id, scopes="openid email https://www.googleapis.com/auth/documents.readonly")
    response = await client.get("/api/v1/google-drive/files", headers=_auth(token))
    assert response.status_code == 409
    assert "Drive" in response.json()["detail"]


@pytest.mark.asyncio
async def test_drive_files_lists_docs_and_sheets(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    fake_token(monkeypatch)
    seen = mount_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "nextPageToken": "page-2",
                "files": [
                    {
                        "id": "doc-1",
                        "name": "Biên bản họp",
                        "mimeType": MIME_DOCUMENT,
                        "modifiedTime": "2026-08-18T03:04:05.000Z",
                        "webViewLink": "https://docs.google.com/document/d/doc-1/edit",
                    },
                    {
                        "id": "sheet-1",
                        "name": "Backlog nhóm",
                        "mimeType": MIME_SPREADSHEET,
                        "modifiedTime": "2026-08-17T03:04:05.000Z",
                        "webViewLink": "https://docs.google.com/spreadsheets/d/sheet-1/edit",
                    },
                    # File không phải Docs/Sheets phải bị loại, picker chỉ nhận 2 loại.
                    {
                        "id": "pdf-1",
                        "name": "Hợp đồng.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2026-08-16T03:04:05.000Z",
                        "webViewLink": "https://drive.google.com/file/d/pdf-1/view",
                    },
                ],
            },
        ),
    )

    response = await client.get(
        "/api/v1/google-drive/files",
        headers=_auth(token),
        params={"q": "backlog", "kind": "all", "pageSize": 10},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [f["id"] for f in body["files"]] == ["doc-1", "sheet-1"]
    assert [f["kind"] for f in body["files"]] == ["document", "spreadsheet"]
    assert body["nextPageToken"] == "page-2"
    assert body["files"][0]["webViewLink"].endswith("/doc-1/edit")
    assert body["files"][0]["modifiedTime"].startswith("2026-08-18T03:04:05")

    outgoing = seen[-1]
    assert outgoing.url.host == "www.googleapis.com"
    assert "name contains 'backlog'" in outgoing.url.params["q"]
    assert outgoing.url.params["pageSize"] == "10"


@pytest.mark.asyncio
async def test_drive_files_filters_by_kind(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    fake_token(monkeypatch)
    seen = mount_transport(monkeypatch, lambda request: httpx.Response(200, json={"files": []}))

    response = await client.get(
        "/api/v1/google-drive/files",
        headers=_auth(token),
        params={"kind": "spreadsheet"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"files": [], "nextPageToken": None}
    query = seen[-1].url.params["q"]
    assert MIME_SPREADSHEET in query
    assert MIME_DOCUMENT not in query


@pytest.mark.asyncio
async def test_drive_files_rejects_page_size_above_cap(client):
    user_id, token = await _register(client)
    _connect(user_id)
    response = await client.get(
        "/api/v1/google-drive/files",
        headers=_auth(token),
        params={"pageSize": 500},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_drive_files_maps_google_error_to_502(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    fake_token(monkeypatch)
    mount_transport(monkeypatch, lambda request: httpx.Response(500, text="boom"))
    response = await client.get("/api/v1/google-drive/files", headers=_auth(token))
    assert response.status_code == 502


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_payload", "expected_status", "expected_detail"),
    [
        (
            {"error": {"errors": [{"reason": "insufficientPermissions"}]}},
            409,
            "cấp lại quyền Google",
        ),
        (
            {
                "error": {
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                            "reason": "SERVICE_DISABLED",
                            "metadata": {"consumer": "projects/secret-project-id"},
                        }
                    ]
                }
            },
            503,
            "chưa được bật",
        ),
        (
            {"error": {"errors": [{"reason": "rateLimitExceeded"}]}},
            503,
            "giới hạn yêu cầu tạm thời",
        ),
        (
            {"error": {"errors": [{"reason": "domainPolicy"}]}},
            403,
            "Google Workspace",
        ),
    ],
)
async def test_drive_files_maps_403_reason_to_actionable_error(
    client,
    monkeypatch,
    error_payload,
    expected_status,
    expected_detail,
):
    user_id, token = await _register(client)
    _connect(user_id)
    fake_token(monkeypatch)
    mount_transport(monkeypatch, lambda request: httpx.Response(403, json=error_payload))

    response = await client.get("/api/v1/google-drive/files", headers=_auth(token))

    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"]
    assert "secret-project-id" not in response.text


@pytest.mark.asyncio
async def test_drive_files_keeps_unknown_403_safe(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    fake_token(monkeypatch)
    mount_transport(monkeypatch, lambda request: httpx.Response(403, text="provider secret"))

    response = await client.get("/api/v1/google-drive/files", headers=_auth(token))

    assert response.status_code == 502
    assert "403" in response.json()["detail"]
    assert "provider secret" not in response.text


def test_build_query_escapes_user_search_term():
    """Dấu nháy đơn trong từ khoá phải bị thoát, không được ghép thêm mệnh đề."""
    query = build_query(search="a' or trashed=true or name contains '", kind="document")
    assert "trashed=false" in query
    # Nháy đơn của người dùng bị thoát nên phần chèn thêm nằm gọn trong chuỗi
    # literal: biểu thức vẫn đúng 3 mệnh đề (mimeType, trashed, name contains).
    assert "\\'" in query
    assert query.count(" and ") == 2
    assert query.endswith("\\''")
