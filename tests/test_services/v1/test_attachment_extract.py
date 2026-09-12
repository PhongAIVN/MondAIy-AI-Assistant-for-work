import io

import pytest
from docx import Document
from openpyxl import Workbook

from src.services.attachment_extract import (
    build_langextract_config,
    extract_docx_text,
    extract_image_text,
    extract_pdf_text,
    extract_structured_signals,
    extract_xlsx_text,
)


def _build_minimal_pdf(text: str) -> bytes:
    """PDF hợp lệ tối thiểu tự viết tay (không phụ thuộc reportlab, chưa có
    trong requirements) — đủ xref/trailer để pypdf parse được, có 1 trang
    chứa đúng `text` trong content stream."""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    stream_content = f"BT /F1 24 Tf 10 100 Td ({text}) Tj ET".encode()
    objects.append(b"<</Length " + str(len(stream_content)).encode() + b">>\nstream\n" + stream_content + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj".encode() + obj + b"endobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


def _build_empty_pdf() -> bytes:
    """PDF hợp lệ nhưng content stream rỗng — mô phỏng PDF scan không có
    text layer, extract_pdf_text phải trả chuỗi rỗng, không lỗi."""
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R>>",
        b"<</Length 0>>\nstream\n\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj".encode() + obj + b"endobj\n"
    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return bytes(out)


def test_extract_pdf_text_reads_real_text_layer():
    pdf_bytes = _build_minimal_pdf("Hello mondaiy attachment test")
    assert extract_pdf_text(pdf_bytes) == [("Trang 1", "Hello mondaiy attachment test")]


def test_extract_pdf_text_returns_empty_list_for_scanned_pdf_without_text_layer():
    assert extract_pdf_text(_build_empty_pdf()) == []


def test_extract_docx_text_reads_paragraphs_and_table_cells():
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("Nội dung chính của tài liệu")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Hạn chót"
    table.rows[0].cells[1].text = "Thứ Sáu"
    document.save(buffer)

    sections = extract_docx_text(buffer.getvalue())
    joined = "\n".join(text for _, text in sections)
    assert "Nội dung chính của tài liệu" in joined
    assert "Hạn chót | Thứ Sáu" in joined
    assert ("Bảng", "Hạn chót | Thứ Sáu") in sections


def test_extract_docx_text_groups_paragraphs_by_heading():
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("Nhận xét MC1", style="Heading 1")
    document.add_paragraph("Lỗi trích dẫn ở bảng 17a")
    document.add_paragraph("Nhận xét MC2", style="Heading 1")
    document.add_paragraph("Thiếu số liệu ở mục 3.2")
    document.save(buffer)

    sections = extract_docx_text(buffer.getvalue())
    labels = [label for label, _ in sections]
    assert "Nhận xét MC1" in labels
    assert "Nhận xét MC2" in labels
    assert dict(sections)["Nhận xét MC1"] == "Lỗi trích dẫn ở bảng 17a"
    assert dict(sections)["Nhận xét MC2"] == "Thiếu số liệu ở mục 3.2"


def test_extract_xlsx_text_serializes_rows_with_sheet_section():
    buffer = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ngân sách"
    sheet.append(["Mục", "Số tiền"])
    sheet.append(["Ăn uống", 500000])
    workbook.save(buffer)

    sections = extract_xlsx_text(buffer.getvalue())
    assert sections == [("Sheet: Ngân sách", "Mục | Số tiền\nĂn uống | 500000")]


def test_extract_xlsx_text_truncates_large_sheets():
    buffer = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    for i in range(250):
        sheet.append([f"row-{i}"])
    workbook.save(buffer)

    sections = extract_xlsx_text(buffer.getvalue())
    text = sections[0][1]
    assert "row-0" in text
    assert "row-199" in text
    assert "row-249" not in text
    assert "đã cắt bớt" in text


class _FakeVisionResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeVisionLLM:
    def __init__(self, content: str) -> None:
        self._content = content
        self.received_messages: list = []

    async def ainvoke(self, messages):
        self.received_messages.append(messages)
        return _FakeVisionResponse(self._content)


@pytest.mark.asyncio
async def test_extract_image_text_calls_vision_llm_with_multimodal_payload(monkeypatch):
    from src.services import attachment_extract as module

    monkeypatch.setattr(module, "get_settings", lambda: type("S", (), {"mock_llm": False})())

    llm = _FakeVisionLLM("Ảnh chụp bảng deadline: nộp báo cáo trước thứ Sáu.")
    result = await extract_image_text(b"\x89PNGfakebytes", "image/png", llm)

    assert result == "Ảnh chụp bảng deadline: nộp báo cáo trước thứ Sáu."
    assert len(llm.received_messages) == 1
    content = llm.received_messages[0][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_extract_image_text_short_circuits_under_mock_llm(monkeypatch):
    from src.services import attachment_extract as module

    monkeypatch.setattr(module, "get_settings", lambda: type("S", (), {"mock_llm": True})())

    llm = _FakeVisionLLM("should not be called")
    result = await extract_image_text(b"bytes", "image/png", llm)

    assert result == ""
    assert llm.received_messages == []


def test_build_langextract_config_none_when_no_api_key_configured(monkeypatch):
    from src.services import attachment_extract as module
    from src.services import openrouter_keys

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: type("S", (), {"model_name": "m", "openrouter_base_url": "https://x"})(),
    )

    def _raise_no_key():
        raise ValueError("Chưa cấu hình OPENROUTER_API_KEY hoặc OPENROUTER_API_KEYS")

    monkeypatch.setattr(openrouter_keys, "build_openrouter_key_pool", _raise_no_key)

    assert build_langextract_config() is None


def test_build_langextract_config_builds_openai_compatible_model_config(monkeypatch):
    from src.services import attachment_extract as module
    from src.services import openrouter_keys

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "model_name": "test-model",
                "openrouter_base_url": "https://openrouter.test/api/v1",
                "attachment_structured_extraction_max_output_tokens": 2000,
            },
        )(),
    )

    class _FakePool:
        def next_key(self) -> str:
            return "sk-test-123"

    monkeypatch.setattr(openrouter_keys, "build_openrouter_key_pool", lambda: _FakePool())

    config = build_langextract_config()

    assert config.model_id == "test-model"
    assert config.provider == "openai"
    # max_output_tokens BẮT BUỘC có mặt: thiếu nó thì LangExtract không gửi
    # max_tokens, OpenRouter tính hạn mức theo trần model rồi trả 402
    # "requires more credits" — lỗi bị nuốt, chỉ hiện ra là structured_extract
    # = None (bug thật, 2026-08-20).
    assert config.provider_kwargs == {
        "api_key": "sk-test-123",
        "base_url": "https://openrouter.test/api/v1",
        "max_output_tokens": 2000,
    }


def test_extract_structured_signals_maps_extraction_to_its_section(monkeypatch):
    import langextract
    from langextract.data import AnnotatedDocument, Extraction

    def _fake_extract(*, text_or_documents, **kwargs):
        if text_or_documents == "Nội dung trang 1":
            return AnnotatedDocument(
                text=text_or_documents,
                extractions=[Extraction(extraction_class="action", extraction_text="Nộp báo cáo")],
            )
        return AnnotatedDocument(text=text_or_documents, extractions=[])

    monkeypatch.setattr(langextract, "extract", _fake_extract)

    signals = extract_structured_signals(
        [("Trang 1", "Nội dung trang 1"), ("Trang 2", "Không có gì đáng chú ý")],
        config=object(),
    )

    assert signals == [{"class": "action", "text": "Nộp báo cáo", "section": "Trang 1"}]


def test_extract_structured_signals_skips_failing_section_keeps_others(monkeypatch):
    import langextract
    from langextract.data import AnnotatedDocument, Extraction

    def _fake_extract(*, text_or_documents, **kwargs):
        if text_or_documents == "lỗi rate limit":
            raise RuntimeError("rate limited")
        return AnnotatedDocument(
            text=text_or_documents,
            extractions=[Extraction(extraction_class="key_point", extraction_text="section ổn")],
        )

    monkeypatch.setattr(langextract, "extract", _fake_extract)

    signals = extract_structured_signals(
        [("A", "lỗi rate limit"), ("B", "section thứ 2")],
        config=object(),
    )

    assert signals == [{"class": "key_point", "text": "section ổn", "section": "B"}]
