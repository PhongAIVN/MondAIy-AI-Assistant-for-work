"""Test hồi quy cho hai đường lách còn lại mà review chéo tìm ra (2026-08-20).

1. Cap ký tự bị lách khi dồn hết nội dung vào MỘT hàng/MỘT ô.
2. Cả Docs lẫn Sheets tải nguyên payload về RAM rồi mới cắt — chỉ cần trỏ vào
   một file khổng lồ là bơm được RAM/băng thông dù token cuối cùng vẫn bị cắt.
"""

import json
import uuid

import httpx
import pytest

from src.config import get_settings
from src.connectors.google_http import GoogleResponseTooLargeError, fetch_json_capped
from src.connectors.google_sheets import bounded_range, cap_values
from src.db import SessionLocal
from src.models.connection import Connection
from src.services.google_sheet_task_extraction import GoogleSheetTaskCandidate

_SCOPES = (
    "openid email https://www.googleapis.com/auth/documents.readonly "
    "https://www.googleapis.com/auth/spreadsheets.readonly"
)


async def _register(client) -> tuple[str, str]:
    email = f"size-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "displayName": "Nguyễn Văn An"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["userId"], body["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _connect(user_id: str) -> None:
    db = SessionLocal()
    try:
        db.add(Connection(user_id=user_id, provider="google", scopes=_SCOPES, status="connected_ready"))
        db.commit()
    finally:
        db.close()


def _fake_token(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _token(_db, _connection):
        return "fake-access-token"

    monkeypatch.setattr("src.services.connections.google.ensure_valid_access_token", _token)


def _mount(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
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


def _retained_chars(values: list[list[object]]) -> int:
    return sum(len(str(cell or "")) for row in values for cell in row)


# ------------------------------------------------- lỗi 2: cap tới mức từng ô


def test_cap_values_truncates_a_single_oversized_row():
    """Probe của reviewer: limit=20000 thì retained phải <= 20000 và truncated=True.

    Bản cũ giữ nguyên hàng đầu tiên (retained=20001, truncated=False) — tức chỉ
    cần một hàng dài là lách được cap.
    """
    limit = get_settings().google_document_max_chars
    values = [["x" * (limit + 1)]]
    capped, truncated = cap_values(values)
    assert truncated is True
    assert _retained_chars(capped) == limit


def test_cap_values_truncates_a_single_oversized_cell_among_others():
    limit = get_settings().google_document_max_chars
    values = [["tiêu đề", "y" * (limit * 2)], ["hàng sau", "bị bỏ"]]
    capped, truncated = cap_values(values)
    assert truncated is True
    assert _retained_chars(capped) <= limit
    # Phần đầu bảng vẫn được giữ nguyên, chỉ ô tràn mới bị cắt.
    assert capped[0][0] == "tiêu đề"


def test_cap_values_drops_rows_once_the_budget_is_gone():
    limit = get_settings().google_document_max_chars
    values = [["a" * limit], ["hàng này không còn ngân sách"]]
    capped, truncated = cap_values(values)
    assert truncated is True
    assert len(capped) == 1
    assert _retained_chars(capped) == limit


def test_cap_values_keeps_small_tables_untouched():
    values = [["a", "b"], ["c", "d"]]
    assert cap_values(values) == (values, False)


# ------------------------------- lỗi 3a: Sheets chỉ xin đúng vùng cần dùng


@pytest.fixture
def semantic_sheet_stub(monkeypatch):
    async def extract(values, *, sheet_name):
        del sheet_name
        if len(values) < 2:
            return []
        return [GoogleSheetTaskCandidate(row_number=2, title=str(values[1][0]))]

    monkeypatch.setattr("src.connectors.google_sheets.extract_google_sheet_tasks", extract)


def test_bounded_range_asks_for_one_extra_row_and_column():
    settings = get_settings()
    assert bounded_range("Backlog") == f"'Backlog'!A1:U{settings.google_sheet_max_rows + 1}"


def test_bounded_range_escapes_quotes_in_sheet_name():
    assert bounded_range("Tuần 'A'").startswith("'Tuần ''A'''!A1:")


@pytest.mark.asyncio
async def test_sheets_request_is_bounded_before_download(client, monkeypatch, semantic_sheet_stub):
    del semantic_sheet_stub
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/values/" not in str(request.url):
            return httpx.Response(
                200,
                json={"sheets": [{"properties": {"title": "Backlog", "sheetId": 0}}]},
            )
        return httpx.Response(200, json={"values": [["Tên công việc", "Hạn chót"], ["Việc A", ""]]})

    seen = _mount(monkeypatch, handler)

    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 200, response.text
    settings = get_settings()
    expected = f"A1%3AU{settings.google_sheet_max_rows + 1}"
    assert expected in str(seen[-1].url), seen[-1].url


# ---------------------------- lỗi 3b: chặn kích thước ngay ở tầng request


def _oversized_json(size: int) -> bytes:
    return json.dumps({"filler": "z" * size}).encode("utf-8")


@pytest.mark.asyncio
async def test_fetch_json_capped_refuses_a_declared_oversized_response(monkeypatch):
    """Content-Length đã vượt ngưỡng thì từ chối trước khi đọc byte nội dung nào."""
    cap = get_settings().google_api_max_response_bytes
    monkeypatch.setattr(get_settings(), "google_api_max_response_bytes", 1_000)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_oversized_json(5_000))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw_client:
        with pytest.raises(GoogleResponseTooLargeError) as excinfo:
            await fetch_json_capped(raw_client, "https://docs.googleapis.com/v1/documents/x", source="Google Docs")
    message = str(excinfo.value)
    assert "quá lớn" in message
    assert "ngưỡng cho phép" in message
    assert cap > 0


@pytest.mark.asyncio
async def test_fetch_json_capped_aborts_a_streamed_response_without_content_length(monkeypatch):
    """Máy chủ không khai độ dài thì phải huỷ GIỮA CHỪNG, không tải hết rồi mới chặn."""
    monkeypatch.setattr(get_settings(), "google_api_max_response_bytes", 4_000)
    delivered = {"bytes": 0}

    async def chunks():
        for _ in range(100):
            delivered["bytes"] += 1_000
            yield b"z" * 1_000

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=chunks())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as raw_client:
        with pytest.raises(GoogleResponseTooLargeError):
            await fetch_json_capped(raw_client, "https://sheets.googleapis.com/v4/x", source="Google Sheets")
    # Dừng ngay khi vượt ngưỡng thay vì nuốt hết 100 KB.
    assert delivered["bytes"] <= 6_000, delivered


@pytest.mark.asyncio
async def test_fetch_json_capped_returns_body_when_within_the_cap():
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient(transport=transport) as raw_client:
        status_code, body = await fetch_json_capped(
            raw_client, "https://docs.googleapis.com/v1/x", source="Google Docs"
        )
    assert (status_code, body) == (200, {"ok": True})


@pytest.mark.asyncio
async def test_docs_endpoint_maps_oversized_file_to_422(client, monkeypatch):
    """File quá lớn = lỗi đầu vào -> 422 (đúng contract), detail nói rõ vượt bao nhiêu."""
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    monkeypatch.setattr(get_settings(), "google_api_max_response_bytes", 2_000)
    _mount(monkeypatch, lambda request: httpx.Response(200, content=_oversized_json(20_000)))

    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "Google Docs" in detail
    assert "MB" in detail


@pytest.mark.asyncio
async def test_sheets_endpoint_maps_oversized_file_to_422(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    monkeypatch.setattr(get_settings(), "google_api_max_response_bytes", 2_000)
    _mount(monkeypatch, lambda request: httpx.Response(200, content=_oversized_json(20_000)))

    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 422, response.text
    assert "Google Sheets" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oversized_file_does_not_consume_quota(client, monkeypatch):
    """Bị chặn vì quá lớn thì không được trừ lượt: người dùng chưa đọc được gì."""
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    monkeypatch.setattr(get_settings(), "google_api_max_response_bytes", 2_000)
    _mount(monkeypatch, lambda request: httpx.Response(200, content=_oversized_json(20_000)))

    from src.services.document_read_quota import quota_remaining

    before = quota_remaining(SessionLocal(), user_id)
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 422
    assert quota_remaining(SessionLocal(), user_id) == before
