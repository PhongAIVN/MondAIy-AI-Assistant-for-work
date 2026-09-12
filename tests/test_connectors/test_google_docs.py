from datetime import UTC
from types import SimpleNamespace

import httpx
import pytest

from src.connectors.google_docs import GoogleDocsConnector, extract_document_id
from src.services.document_extraction import ExtractedTaskCandidate


def test_extract_document_id_accepts_google_url_and_rejects_other_url():
    document_id = "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    assert extract_document_id(f"https://docs.google.com/document/d/{document_id}/edit") == document_id
    with pytest.raises(ValueError):
        extract_document_id("https://example.com/document/d/not-google")


def test_extract_document_id_accepts_bare_id():
    document_id = "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    assert extract_document_id(document_id) == document_id


def test_extract_document_id_rejects_short_garbage():
    with pytest.raises(ValueError):
        extract_document_id("not-an-id")


@pytest.mark.asyncio
async def test_read_document_text_joins_paragraphs_and_truncates(monkeypatch):
    connector = GoogleDocsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_access_token():
        return "token"

    monkeypatch.setattr(connector, "_access_token", fake_access_token)

    # Dùng MockTransport thay cho client giả tự viết: connector đọc phản hồi
    # theo luồng (để chặn file quá lớn ngay ở tầng request) nên nó cần một
    # client httpx thật, không chỉ một object có mỗi .get().
    body = {
        "body": {
            "content": [
                {"paragraph": {"elements": [{"textRun": {"content": "Dòng một\n"}}]}},
                {"sectionBreak": {}},
                {"paragraph": {"elements": [{"textRun": {"content": "Dòng hai\n"}}]}},
            ]
        }
    }
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=body))
    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    monkeypatch.setattr("src.connectors.google_docs.httpx.AsyncClient", PatchedClient)

    text = await connector.read_document_text("doc-id")
    assert text == "Dòng một\nDòng hai"


@pytest.mark.asyncio
async def test_task_proposals_uses_llm_extraction_and_reuses_sheets_logic(monkeypatch):
    connector = GoogleDocsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_document_text(_document_id):
        return "Hoàn thành báo cáo trước 31/08/2026, phụ trách: Nguyễn Văn An."

    monkeypatch.setattr(connector, "read_document_text", fake_read_document_text)
    monkeypatch.setattr(
        "src.connectors.google_docs.get_settings",
        lambda: SimpleNamespace(app_timezone="Asia/Ho_Chi_Minh"),
    )

    async def fake_extract(_text, **_kwargs):
        return [
            ExtractedTaskCandidate(
                title="Hoàn thành báo cáo",
                detail="Báo cáo quý",
                due_at="31/08/2026",
                assignee="Nguyễn Văn An",
            )
        ]

    monkeypatch.setattr("src.connectors.google_docs.extract_task_candidates_from_text", fake_extract)

    proposals = await connector.task_proposals(document_id="doc-id", display_name="Nguyễn Văn An")

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal["title"] == "Hoàn thành báo cáo"
    assert proposal["matched_user"] is True
    assert proposal["needs_confirmation"] is False
    assert proposal["due_at"].tzinfo == UTC
    assert proposal["date_ambiguous"] is False
    assert proposal["paragraph_index"] == 0
    assert proposal["source"] == "Google Docs"


@pytest.mark.asyncio
async def test_task_proposals_flags_ambiguous_date_and_unmatched_assignee(monkeypatch):
    connector = GoogleDocsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_document_text(_document_id):
        return "text"

    monkeypatch.setattr(connector, "read_document_text", fake_read_document_text)
    monkeypatch.setattr(
        "src.connectors.google_docs.get_settings",
        lambda: SimpleNamespace(app_timezone="Asia/Ho_Chi_Minh"),
    )

    async def fake_extract(_text, **_kwargs):
        return [
            ExtractedTaskCandidate(
                title="Việc thiếu năm hạn chót",
                detail="",
                due_at="15/3",
                assignee="Người khác",
            )
        ]

    monkeypatch.setattr("src.connectors.google_docs.extract_task_candidates_from_text", fake_extract)

    proposals = await connector.task_proposals(document_id="doc-id", display_name="Nguyễn Văn An")

    proposal = proposals[0]
    assert proposal["matched_user"] is False
    assert proposal["date_ambiguous"] is True
    assert proposal["needs_confirmation"] is True
    assert "Người khác" in proposal["clarification_question"]
    assert "không rõ năm" in proposal["clarification_question"]


@pytest.mark.asyncio
async def test_task_proposals_skips_candidates_without_title(monkeypatch):
    connector = GoogleDocsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_document_text(_document_id):
        return "text"

    monkeypatch.setattr(connector, "read_document_text", fake_read_document_text)
    monkeypatch.setattr(
        "src.connectors.google_docs.get_settings",
        lambda: SimpleNamespace(app_timezone="Asia/Ho_Chi_Minh"),
    )

    async def fake_extract(_text, **_kwargs):
        return [ExtractedTaskCandidate(title="   ", detail="", due_at=None, assignee=None)]

    monkeypatch.setattr("src.connectors.google_docs.extract_task_candidates_from_text", fake_extract)

    proposals = await connector.task_proposals(document_id="doc-id", display_name="Nguyễn Văn An")

    assert proposals == []
