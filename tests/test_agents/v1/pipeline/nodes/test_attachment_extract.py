import uuid
from types import SimpleNamespace

import pytest

from src.agents.pipeline.nodes import attachment_extract
from src.connectors.gmail import GmailConnector
from src.guardrail.attachment_safety import AttachmentRejectedError
from src.models.connection import Connection
from src.models.pipeline_audit import PipelineAttachmentExtract
from tests.test_agents.v1.pipeline.conftest import gmail_item

_PDF_ATTACHMENT = {
    "filename": "bao-cao.pdf",
    "mimeType": "application/pdf",
    "sizeBytes": 1000,
    "attachmentId": "att-1",
}
_EXE_ATTACHMENT = {
    "filename": "setup.exe",
    "mimeType": "application/x-msdownload",
    "sizeBytes": 1000,
    "attachmentId": "att-evil",
}


def _settings(**overrides) -> SimpleNamespace:
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


def _insert_google_connection(pipeline_state, *, provider_user_id="me@example.test") -> int:
    db = pipeline_state["db"]
    connection = Connection(
        user_id=f"u-test-{uuid.uuid4().hex[:8]}", provider="google", provider_user_id=provider_user_id
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection.id


@pytest.mark.asyncio
async def test_disabled_by_default_is_a_noop(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings(attachment_extraction_enabled=False))
    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 0


@pytest.mark.asyncio
async def test_skips_ignored_email_without_touching_gmail(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())
    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT], importance="ignore")
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 0


@pytest.mark.asyncio
async def test_relevant_email_with_supported_file_is_extracted(pipeline_state, monkeypatch):
    """Cost-gate cũ (critical/important) cắt luôn mail công việc thường: thang
    điểm filter_classify cần >= 60 mới tới "important", mà mail có người gửi +
    người nhận + tín hiệu action hay dừng ở 50-55. Mail "relevant" ĐÍNH KÈM file
    thuộc allow-list vẫn phải được trích, nếu không phần tóm tắt file biến mất."""
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    async def fake_download(self, message_id, attachment_id):
        return b"%PDF-fake-bytes"

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "Nộp báo cáo trước thứ Sáu.")]
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT], importance="relevant")
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert "Nộp báo cáo trước thứ Sáu." in result["filtered"][0]["attachment_text"]


@pytest.mark.asyncio
async def test_relevant_email_without_supported_file_stays_gated(pipeline_state, monkeypatch):
    """Nới cost-gate chỉ áp dụng khi có file thuộc allow-list — mail hạng
    "relevant" đính kèm loại file không trích được vẫn không đáng gọi Gmail."""
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    async def fail_download(self, message_id, attachment_id):
        raise AssertionError("không được tải attachment của mail relevant khi file không nằm trong allow-list")

    monkeypatch.setattr(GmailConnector, "download_attachment", fail_download)

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_EXE_ATTACHMENT], importance="relevant")
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 0


@pytest.mark.asyncio
async def test_skips_email_without_attachments(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())
    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 0


@pytest.mark.asyncio
async def test_disallowed_mime_type_is_recorded_as_skipped_type(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())
    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_EXE_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    rows = pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).all()
    assert len(rows) == 1
    assert rows[0].status == "skipped_type"
    assert rows[0].filename == "setup.exe"


@pytest.mark.asyncio
async def test_successful_pdf_extraction_sets_attachment_text_and_audit_row(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    async def fake_download(self, message_id, attachment_id):
        assert message_id == "m1"
        assert attachment_id == "att-1"
        return b"%PDF-fake-bytes"

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "Nộp báo cáo trước thứ Sáu.")]
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    text = result["filtered"][0]["attachment_text"]
    assert "[Đính kèm: bao-cao.pdf]" in text
    assert "Nộp báo cáo trước thứ Sáu." in text

    rows = pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).all()
    assert len(rows) == 1
    assert rows[0].status == "ok"
    assert rows[0].filename == "bao-cao.pdf"
    assert "Nộp báo cáo" in rows[0].extracted_text


@pytest.mark.asyncio
async def test_extraction_failure_is_recorded_without_crashing_the_node(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())

    async def fake_download(self, message_id, attachment_id):
        return b"%PDF-fake-bytes"

    def boom(file_bytes):
        raise RuntimeError("pypdf lỗi giả lập")

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(attachment_extract, "extract_pdf_text", boom)
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert len(result["errors"]) == 1
    assert "bao-cao.pdf" in result["errors"][0]

    rows = pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).all()
    assert rows[0].status == "failed"


@pytest.mark.asyncio
async def test_caps_number_of_attachments_processed_per_message(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings(attachment_max_per_message=1))

    downloaded_ids: list[str] = []

    async def fake_download(self, message_id, attachment_id):
        downloaded_ids.append(attachment_id)
        return b"%PDF-fake-bytes"

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "text")])
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())

    connection_id = _insert_google_connection(pipeline_state)
    second_pdf = {**_PDF_ATTACHMENT, "filename": "second.pdf", "attachmentId": "att-2"}
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT, second_pdf])
    pipeline_state["filtered"] = [item]

    await attachment_extract.attachment_extract_node(pipeline_state)

    assert downloaded_ids == ["att-1"]
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 1


@pytest.mark.asyncio
async def test_missing_connection_row_is_skipped_without_crashing(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())
    item = gmail_item(connection_id=999_999, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert result["filtered"][0].get("attachment_text") is None
    assert pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).count() == 0


@pytest.mark.asyncio
async def test_structured_extraction_enabled_tags_attachment_text_by_section(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        attachment_extract, "get_settings", lambda: _settings(attachment_structured_extraction_enabled=True)
    )

    async def fake_download(self, message_id, attachment_id):
        return b"%PDF-fake-bytes"

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract,
        "extract_pdf_text",
        lambda file_bytes: [("Trang 1", "Vui lòng nộp báo cáo trước thứ Sáu."), ("Trang 2", "Cảm ơn bạn.")],
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())
    monkeypatch.setattr(attachment_extract, "build_langextract_config", lambda: object())
    monkeypatch.setattr(
        attachment_extract,
        "extract_structured_signals",
        lambda sections, config: [{"class": "action", "text": "nộp báo cáo trước thứ Sáu", "section": "Trang 1"}],
    )

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    text = result["filtered"][0]["attachment_text"]
    assert "[Trang 1] nộp báo cáo trước thứ Sáu" in text
    assert "Cảm ơn bạn" not in text  # Trang 2 không có tín hiệu, LangExtract không trả về

    rows = pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).all()
    assert rows[0].structured_extract == [
        {"class": "action", "text": "nộp báo cáo trước thứ Sáu", "section": "Trang 1"}
    ]


@pytest.mark.asyncio
async def test_structured_extraction_falls_back_to_flat_text_on_langextract_error(pipeline_state, monkeypatch):
    monkeypatch.setattr(
        attachment_extract, "get_settings", lambda: _settings(attachment_structured_extraction_enabled=True)
    )

    async def fake_download(self, message_id, attachment_id):
        return b"%PDF-fake-bytes"

    def boom(sections, config):
        raise RuntimeError("LangExtract rate limited")

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "Nộp báo cáo trước thứ Sáu.")]
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())
    monkeypatch.setattr(attachment_extract, "build_langextract_config", lambda: object())
    monkeypatch.setattr(attachment_extract, "extract_structured_signals", boom)

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    # LangExtract lỗi -> fallback nối phẳng section, attachment_text vẫn có,
    # không mất trắng, không sập node.
    text = result["filtered"][0]["attachment_text"]
    assert "Nộp báo cáo trước thứ Sáu." in text
    rows = pipeline_state["db"].query(PipelineAttachmentExtract).filter_by(run_id=pipeline_state["run_id"]).all()
    assert rows[0].structured_extract is None


@pytest.mark.asyncio
async def test_structured_extraction_disabled_by_default_never_calls_langextract(pipeline_state, monkeypatch):
    monkeypatch.setattr(attachment_extract, "get_settings", lambda: _settings())  # flag mặc định False

    async def fake_download(self, message_id, attachment_id):
        return b"%PDF-fake-bytes"

    def must_not_be_called():
        raise AssertionError("build_langextract_config không được gọi khi flag tắt")

    monkeypatch.setattr(GmailConnector, "download_attachment", fake_download)
    monkeypatch.setattr(
        attachment_extract, "extract_pdf_text", lambda file_bytes: [("Trang 1", "Nộp báo cáo trước thứ Sáu.")]
    )
    monkeypatch.setattr(attachment_extract, "get_llm", lambda: object())
    monkeypatch.setattr(attachment_extract, "build_langextract_config", must_not_be_called)

    connection_id = _insert_google_connection(pipeline_state)
    item = gmail_item(connection_id=connection_id, attachments=[_PDF_ATTACHMENT])
    pipeline_state["filtered"] = [item]

    result = await attachment_extract.attachment_extract_node(pipeline_state)

    assert "Nộp báo cáo trước thứ Sáu." in result["filtered"][0]["attachment_text"]


def test_attachment_rejected_is_a_real_exception_class():
    # Sanity: module import path đúng, không phải lỗi gõ nhầm re-export.
    with pytest.raises(AttachmentRejectedError):
        raise AttachmentRejectedError("test", code="type")
