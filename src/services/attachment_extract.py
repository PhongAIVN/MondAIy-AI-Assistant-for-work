"""Trích text từ file đính kèm Gmail theo loại file.

Mọi hàm ở đây chỉ "extract" — KHÔNG tự chạy guardrail. Caller
(`attachment_extract_node`) chịu trách nhiệm gọi
`assert_safe_to_download`/`assert_uncompressed_size_ok`/`validate_image_bytes`
(src/guardrail/attachment_safety.py) TRƯỚC khi gọi vào đây, và
`sanitize_untrusted_text` (src/guardrail/input.py) SAU khi có kết quả — tách
rời "đọc file an toàn" khỏi "trích nội dung" khỏi "làm sạch trước khi đưa
LLM đọc", mỗi lớp một trách nhiệm.
"""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Any

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader

from src.config import get_settings

logger = logging.getLogger(__name__)

# Sheet lớn không đẩy nguyên vào context — cắt bớt, không phải tóm tắt.
_MAX_XLSX_ROWS = 200
_MAX_XLSX_COLS = 20

_IMAGE_PROMPT = (
    "Mô tả hoặc trích nội dung ảnh này bằng tiếng Việt: nếu ảnh có chữ thì "
    "trích lại nguyên văn, nếu là biểu đồ/ảnh chụp màn hình thì mô tả ngắn "
    "gọn nội dung chính. Chỉ dựa vào những gì thấy trong ảnh, không suy diễn "
    "hay bịa thêm thông tin không có trong ảnh."
)


def extract_pdf_text(file_bytes: bytes) -> list[tuple[str, str]]:
    """Chỉ đọc được PDF có text layer thật (file số hoá sẵn hoặc đã OCR từ
    trước). PDF chỉ là ảnh scan (không có text layer) trả về danh sách rỗng —
    KHÔNG tự động fallback OCR/vision cho PDF, ngoài scope đợt đầu.

    Trả `[(nhãn_section, text), ...]` theo từng trang thay vì 1 chuỗi phẳng —
    giữ biên giới trang để extract_structured_signals gắn được provenance
    (trích từ trang nào), và để caller vẫn nối phẳng được như cũ nếu cần."""
    reader = PdfReader(BytesIO(file_bytes))
    sections: list[tuple[str, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            sections.append((f"Trang {index}", text))
    return sections


def extract_docx_text(file_bytes: bytes) -> list[tuple[str, str]]:
    """Nối `paragraphs` (thân văn bản) + duyệt riêng `tables` — nội dung ô
    bảng không nằm trong `paragraphs` của python-docx.

    Gom paragraph theo heading (`style.name` bắt đầu "Heading") nếu văn bản
    có cấu trúc heading; không có heading nào thì gộp thành 1 section duy
    nhất. Table (không gắn được với heading cụ thể) luôn là section riêng."""
    document = DocxDocument(BytesIO(file_bytes))
    sections: list[tuple[str, str]] = []
    current_label = "Toàn bộ văn bản"
    current_lines: list[str] = []

    def _flush() -> None:
        if current_lines:
            sections.append((current_label, "\n".join(current_lines)))

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = (paragraph.style.name if paragraph.style else "") or ""
        if style_name.startswith("Heading"):
            _flush()
            current_label = text
            current_lines = []
        else:
            current_lines.append(text)
    _flush()

    table_lines: list[str] = []
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                table_lines.append(" | ".join(cells))
    if table_lines:
        sections.append(("Bảng", "\n".join(table_lines)))

    return sections


def extract_xlsx_text(file_bytes: bytes) -> list[tuple[str, str]]:
    """`data_only=True` lấy giá trị đã tính sẵn, không lấy công thức thô.
    Mỗi sheet serialize thành bảng text đơn giản, cắt số dòng/cột theo
    ngưỡng — sheet hàng nghìn dòng không đẩy nguyên vào context LLM.

    Trả `[(nhãn_sheet, text), ...]` — trước đây nối luôn thành 1 chuỗi trước
    khi return, mất biên giới sheet."""
    workbook = load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    try:
        sections: list[tuple[str, str]] = []
        for sheet in workbook.worksheets:
            rows_text: list[str] = []
            truncated = False
            for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_index >= _MAX_XLSX_ROWS:
                    truncated = True
                    break
                cells = [str(value) for value in row[:_MAX_XLSX_COLS] if value is not None]
                if cells:
                    rows_text.append(" | ".join(cells))
            if truncated:
                rows_text.append(f"... (đã cắt bớt, chỉ hiện {_MAX_XLSX_ROWS} dòng đầu)")
            if rows_text:
                sections.append((f"Sheet: {sheet.title}", "\n".join(rows_text)))
        return sections
    finally:
        workbook.close()


_STRUCTURED_EXTRACTION_PROMPT = (
    "Trích các đoạn text nguyên văn thể hiện: 'action' (yêu cầu hành động cụ "
    "thể cần làm), 'deadline' (mốc thời gian/hạn chót), 'key_point' (điểm/ý "
    "chính đáng chú ý khác, vd nhận xét/yêu cầu sửa cụ thể). Chỉ trích "
    "nguyên văn có thật trong text, không suy diễn, không dịch. Đoạn text "
    "chỉ mang tính thông báo/xã giao không có tín hiệu nào thì để trống."
)


def build_langextract_config() -> Any | None:
    """Dựng `ModelConfig` cho LangExtract trỏ vào cùng OpenRouter đang dùng
    cho toàn bộ pipeline — trả `None` nếu chưa cài package hoặc chưa cấu
    hình API key, caller tự fallback về nối text phẳng như cũ, không raise."""
    try:
        from langextract.factory import ModelConfig
    except ImportError:
        return None

    from src.services.openrouter_keys import build_openrouter_key_pool

    settings = get_settings()
    try:
        pool = build_openrouter_key_pool()
    except ValueError:
        return None

    return ModelConfig(
        model_id=settings.model_name,
        provider="openai",
        provider_kwargs={
            "api_key": pool.next_key(),
            "base_url": settings.openrouter_base_url,
            "max_output_tokens": settings.attachment_structured_extraction_max_output_tokens,
        },
    )


def extract_structured_signals(sections: list[tuple[str, str]], config: Any) -> list[dict[str, str]]:
    """Với mỗi section (trang/sheet/heading), gọi LangExtract trích các đoạn
    verbatim thuộc class action/deadline/key_point. Đồng bộ (khớp
    `lx.extract` là hàm sync) — caller bọc `asyncio.to_thread`.

    1 section lỗi (rate limit, model từ chối...) không được làm mất section
    khác — bỏ qua section đó, giữ nguyên các section còn lại."""
    import langextract as lx
    from langextract.data import ExampleData, Extraction

    examples = [
        ExampleData(
            text="Vui lòng nộp báo cáo tiến độ trước thứ Sáu ngày 22/08.",
            extractions=[
                Extraction(extraction_class="action", extraction_text="Vui lòng nộp báo cáo tiến độ"),
                Extraction(extraction_class="deadline", extraction_text="trước thứ Sáu ngày 22/08"),
            ],
        ),
        ExampleData(
            text="Cảm ơn bạn đã tham gia buổi họp hôm qua, mọi thứ diễn ra suôn sẻ.",
            extractions=[],
        ),
    ]

    signals: list[dict[str, str]] = []
    for section_label, text in sections:
        if not text.strip():
            continue
        try:
            result = lx.extract(
                text_or_documents=text,
                prompt_description=_STRUCTURED_EXTRACTION_PROMPT,
                examples=examples,
                config=config,
                show_progress=False,
            )
        except Exception as exc:  # noqa: BLE001 - 1 section lỗi không được sập cả file
            # Phải log: nuốt im lặng khiến lỗi cấu hình thật (402 hết credit,
            # key sai, model từ chối) chỉ hiện ra dưới dạng structured_extract
            # = None, không phân biệt được với "file không có tín hiệu nào".
            logger.info("LangExtract bỏ qua section %s: %s", section_label, exc)
            continue
        for extraction in result.extractions or []:
            extraction_text = (extraction.extraction_text or "").strip()
            if not extraction_text:
                continue
            signals.append(
                {"class": extraction.extraction_class, "text": extraction_text, "section": section_label}
            )
    return signals


async def extract_image_text(file_bytes: bytes, mime_type: str, llm: Any) -> str:
    """Gọi vision LLM để mô tả/OCR ảnh — không có cách nào trích text từ ảnh
    bằng thư viện thuần mà giữ được ngữ cảnh biểu đồ/ảnh chụp màn hình."""
    settings = get_settings()
    if settings.mock_llm:
        return ""

    data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
    response = await llm.ainvoke(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _IMAGE_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
    )
    content = getattr(response, "content", response)
    return str(content).strip()
