"""Test tầng chống spam token dùng chung cho Google Docs và Google Sheets.

Phủ đúng 4 hành vi Tatejo chốt: cap kích thước (truncated=true), quota
20 lượt/ngày (429 kèm mốc reset), cache theo revision (trúng cache KHÔNG trừ
quota và KHÔNG gọi lại LLM), và nhận documentId/spreadsheetId từ picker.
"""

import uuid

import httpx
import pytest

from src.config import get_settings
from src.connectors.google_sheets import cap_values
from src.db import SessionLocal
from src.models.connection import Connection
from src.services.document_extraction import ExtractedTaskCandidate
from src.services.google_sheet_task_extraction import GoogleSheetTaskCandidate

_SCOPES = (
    "openid email https://www.googleapis.com/auth/documents.readonly "
    "https://www.googleapis.com/auth/spreadsheets.readonly "
    "https://www.googleapis.com/auth/drive.readonly"
)


async def _register(client) -> tuple[str, str]:
    email = f"guard-{uuid.uuid4().hex[:12]}@example.com"
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


def _doc_response(text: str, revision: str = "rev-1") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "revisionId": revision,
            "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": text}}]}}]},
        },
    )


def _count_llm_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Thay LLM trích xuất bằng hàm giả, ghi lại từng lần bị gọi."""
    calls: list[str] = []

    async def fake_extract(document_text: str, **_kwargs):
        calls.append(document_text)
        return [ExtractedTaskCandidate(title="Hoàn thành báo cáo", detail="", assignee="Nguyễn Văn An")]

    monkeypatch.setattr("src.connectors.google_docs.extract_task_candidates_from_text", fake_extract)
    return calls


@pytest.fixture(autouse=True)
def _semantic_sheet_stub(monkeypatch):
    """API guard tests validate cap/quota/cache, not OpenAI semantics."""

    async def extract(values, *, sheet_name):
        del sheet_name
        candidates = []
        for row_number, row in enumerate(values[1:], start=2):
            if not row or not str(row[0]).strip():
                continue
            candidates.append(
                GoogleSheetTaskCandidate(
                    row_number=row_number,
                    title=str(row[0]),
                    assignee=str(row[1]) if len(row) > 1 and row[1] else None,
                )
            )
        return candidates

    monkeypatch.setattr("src.connectors.google_sheets.extract_google_sheet_tasks", extract)


# ---------------------------------------------------------------- documentId


@pytest.mark.asyncio
async def test_docs_accepts_document_id_from_picker(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    _mount(monkeypatch, lambda request: _doc_response("Việc A"))
    _count_llm_calls(monkeypatch)

    document_id = "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentId": document_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["documentId"] == document_id
    assert body["truncated"] is False
    assert body["quotaRemaining"] == get_settings().google_document_reads_per_day - 1


@pytest.mark.asyncio
async def test_docs_rejects_both_url_and_id(client):
    user_id, token = await _register(client)
    _connect(user_id)
    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={
            "documentUrl": "https://docs.google.com/document/d/1AbcdefghijklmnopqrstuvwxYZ_1234567890/edit",
            "documentId": "1AbcdefghijklmnopqrstuvwxYZ_0000000000",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_docs_rejects_missing_url_and_id(client):
    user_id, token = await _register(client)
    _connect(user_id)
    response = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sheets_accepts_spreadsheet_id_from_picker(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/values/" not in str(request.url):
            return httpx.Response(
                200,
                json={"sheets": [{"properties": {"title": "Backlog", "sheetId": 0}}]},
            )
        return httpx.Response(
            200,
            json={"values": [["Tên công việc", "Người phụ trách"], ["Việc A", "Nguyễn Văn An"]]},
        )

    _mount(monkeypatch, handler)

    spreadsheet_id = "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetId": spreadsheet_id, "sheetName": "Backlog"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["spreadsheetId"] == spreadsheet_id
    assert body["proposals"][0]["title"] == "Việc A"
    assert body["truncated"] is False


# --------------------------------------------------------------- truncation


@pytest.mark.asyncio
async def test_docs_truncates_oversized_document(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    max_chars = get_settings().google_document_max_chars
    huge_text = "Việc cần làm. " * (max_chars // 5)
    _mount(monkeypatch, lambda request: _doc_response(huge_text))
    calls = _count_llm_calls(monkeypatch)

    response = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["truncated"] is True
    # Điều quan trọng nhất: LLM nhận đúng phần đã cắt, không nhận cả tài liệu.
    assert len(calls) == 1
    assert len(calls[0]) == max_chars


def test_cap_values_limits_rows_columns_and_chars():
    settings = get_settings()
    values = [[f"c{col}" for col in range(settings.google_sheet_max_columns + 5)] for _ in range(50)]
    capped, truncated = cap_values(values)
    assert truncated is True
    assert all(len(row) == settings.google_sheet_max_columns for row in capped)

    tall = [["x"] for _ in range(settings.google_sheet_max_rows + 10)]
    capped_tall, truncated_tall = cap_values(tall)
    assert truncated_tall is True
    assert len(capped_tall) == settings.google_sheet_max_rows

    fat = [["y" * 1000] for _ in range(settings.google_document_max_chars // 1000 + 5)]
    capped_fat, truncated_fat = cap_values(fat)
    assert truncated_fat is True
    assert sum(len(str(cell)) for row in capped_fat for cell in row) <= settings.google_document_max_chars

    small = [["a", "b"], ["c", "d"]]
    assert cap_values(small) == (small, False)


@pytest.mark.asyncio
async def test_sheets_truncates_oversized_table(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    max_rows = get_settings().google_sheet_max_rows
    rows = [["Tên công việc", "Người phụ trách"]]
    rows += [[f"Việc {index}", "Nguyễn Văn An"] for index in range(max_rows + 20)]

    def handler(request: httpx.Request) -> httpx.Response:
        if "/values/" not in str(request.url):
            return httpx.Response(
                200,
                json={"sheets": [{"properties": {"title": "Backlog", "sheetId": 0}}]},
            )
        return httpx.Response(200, json={"values": rows})

    _mount(monkeypatch, handler)

    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["truncated"] is True
    assert len(body["proposals"]) == max_rows - 1


# -------------------------------------------------------------------- quota


@pytest.mark.asyncio
async def test_docs_returns_429_when_daily_quota_is_exhausted(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", 1)
    _count_llm_calls(monkeypatch)
    # Mỗi lượt là một revision khác nhau nên không lượt nào trúng cache.
    revisions = iter(["rev-a", "rev-b"])
    _mount(monkeypatch, lambda request: _doc_response("Việc A", revision=next(revisions)))

    payload = {"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"}
    first = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["quotaRemaining"] == 0

    second = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    assert second.status_code == 429
    detail = second.json()["detail"]
    assert "hết 1 lượt" in detail
    assert "cấp lại" in detail


@pytest.mark.asyncio
async def test_quota_is_shared_between_docs_and_sheets(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", 1)
    _count_llm_calls(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "docs.googleapis.com":
            return _doc_response("Việc A")
        if "/values/" not in str(request.url):
            return httpx.Response(
                200,
                json={"sheets": [{"properties": {"title": "Backlog", "sheetId": 0}}]},
            )
        return httpx.Response(200, json={"values": [["Tên công việc", "Hạn chót"], ["Việc B", ""]]})

    _mount(monkeypatch, handler)

    docs = await client.post(
        "/api/v1/google-docs/task-proposals",
        headers=_auth(token),
        json={"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"},
    )
    assert docs.status_code == 200, docs.text

    sheets = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetId": "1AbcdefghijklmnopqrstuvwxYZ_0000000000"},
    )
    assert sheets.status_code == 429, sheets.text


# -------------------------------------------------------------------- cache


@pytest.mark.asyncio
async def test_docs_cache_hit_costs_no_quota_and_no_llm_call(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    calls = _count_llm_calls(monkeypatch)
    _mount(monkeypatch, lambda request: _doc_response("Việc A", revision="rev-stable"))

    payload = {"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"}
    first = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    assert first.status_code == 200, first.text
    remaining_after_first = first.json()["quotaRemaining"]

    second = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["quotaRemaining"] == remaining_after_first
    assert second.json()["proposals"] == first.json()["proposals"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_docs_cache_misses_when_revision_changes(client, monkeypatch):
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)
    calls = _count_llm_calls(monkeypatch)
    revisions = iter(["rev-1", "rev-2"])
    _mount(monkeypatch, lambda request: _doc_response("Việc A", revision=next(revisions)))

    payload = {"documentId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"}
    first = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    second = await client.post("/api/v1/google-docs/task-proposals", headers=_auth(token), json=payload)
    assert first.status_code == 200 and second.status_code == 200
    assert len(calls) == 2
    assert second.json()["quotaRemaining"] == first.json()["quotaRemaining"] - 1


@pytest.mark.asyncio
async def test_sheets_cache_is_scoped_per_sheet_name(client, monkeypatch):
    """Cùng file nhưng khác tab là dữ liệu khác — không được trả cache của tab kia."""
    user_id, token = await _register(client)
    _connect(user_id)
    _fake_token(monkeypatch)

    # Cột người phụ trách phải khớp displayName: sau khi hợp nhất với nhánh
    # import Excel/DOCX, connector chỉ giữ dòng có liên quan tới tên người dùng.
    def handler(request: httpx.Request) -> httpx.Response:
        if "/values/" not in str(request.url):
            return httpx.Response(
                200,
                json={
                    "sheets": [
                        {"properties": {"title": "Backlog", "sheetId": 0}},
                        {"properties": {"title": "Sprint", "sheetId": 1}},
                    ]
                },
            )
        header = ["Tên công việc", "Người phụ trách", "Hạn chót"]
        if "Backlog" in str(request.url):
            return httpx.Response(200, json={"values": [header, ["Việc A", "Nguyễn Văn An", ""]]})
        return httpx.Response(200, json={"values": [header, ["Việc B", "Nguyễn Văn An", ""]]})

    _mount(monkeypatch, handler)

    base = {"spreadsheetId": "1AbcdefghijklmnopqrstuvwxYZ_1234567890"}
    first = await client.post(
        "/api/v1/google-sheets/task-proposals", headers=_auth(token), json={**base, "sheetName": "Backlog"}
    )
    second = await client.post(
        "/api/v1/google-sheets/task-proposals", headers=_auth(token), json={**base, "sheetName": "Sprint"}
    )
    assert first.status_code == 200 and second.status_code == 200, second.text
    assert first.json()["proposals"][0]["title"] == "Việc A"
    assert second.json()["proposals"][0]["title"] == "Việc B"
    assert second.json()["quotaRemaining"] == first.json()["quotaRemaining"] - 1
