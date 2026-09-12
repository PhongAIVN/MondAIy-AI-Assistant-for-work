"""Trích file đính kèm không còn là đặc quyền của Gmail.

`attachment_extract_node` từng khoá cứng `provider != "google"`, nên Jira và
Outlook có thu được metadata file cũng không ai tải. Cổng thật sự phải là
"connector này có tải file được không".
"""

import uuid

import pytest

from src.agents.pipeline.nodes import attachment_extract
from src.connectors.jira import JiraConnector
from src.models.connection import Connection
from src.models.pipeline_audit import PipelineAttachmentExtract

_PDF = {"filename": "review.pdf", "mimeType": "application/pdf", "sizeBytes": 1000, "attachmentId": "10001"}


def _settings(**overrides):
    from types import SimpleNamespace

    base = dict(
        attachment_extraction_enabled=True,
        attachment_max_bytes=8_000_000,
        attachment_max_per_message=3,
        attachment_max_extracted_chars=4000,
        attachment_extraction_timeout_seconds=5,
        attachment_max_image_pixels=20_000_000,
        attachment_structured_extraction_enabled=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _jira_connection(pipeline_state) -> int:
    db = pipeline_state["db"]
    row = Connection(
        user_id=f"u-{uuid.uuid4().hex[:8]}",
        provider="jira",
        provider_user_id="acc-me",
        external_site_id="cloud-1",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.id


def _jira_item(connection_id: int, **overrides) -> dict:
    from datetime import UTC, datetime

    item = {
        "id": "TAPB-178",
        "provider": "jira",
        "source_id": "T004",
        "text": "Cần sửa lại bảng số liệu.",
        "sent_at": datetime(2026, 8, 20, tzinfo=UTC),
        "deep_link": "https://x.atlassian.net/browse/TAPB-178",
        "connection_id": connection_id,
        "attachments": [_PDF],
        "importance": "relevant",
    }
    item.update(overrides)
    return item


@pytest.mark.asyncio
async def test_jira_attachments_are_extracted(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    async def fake_download(self, message_id, attachment_id):
        assert message_id == "TAPB-178"
        assert attachment_id == "10001"
        return b"%PDF-fake"

    monkeypatch.setattr(JiraConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "Sửa bảng 17a trước thứ Sáu.")]
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())

    pipeline_state["filtered"] = [_jira_item(_jira_connection(pipeline_state))]
    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert "Sửa bảng 17a trước thứ Sáu." in result["filtered"][0]["attachment_text"]
    rows = (
        pipeline_state["db"]
        .query(PipelineAttachmentExtract)
        .filter_by(run_id=pipeline_state["run_id"])
        .all()
    )
    assert [row.status for row in rows] == ["ok"]


@pytest.mark.asyncio
async def test_a_connector_without_a_download_path_is_skipped_quietly(pipeline_state, monkeypatch):
    """Calendar có thể mang metadata nhưng không có đường tải — bỏ qua im lặng
    thay vì ném lỗi giữa pipeline."""
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    db = pipeline_state["db"]
    row = Connection(user_id=f"u-{uuid.uuid4().hex[:8]}", provider="google", provider_user_id="me@x.com")
    db.add(row)
    db.commit()
    db.refresh(row)

    item = _jira_item(row.id, provider="google_calendar", source_id="calendar:primary", id="evt-1")
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert result["errors"] == []
