"""Node LangGraph: tải + trích text từ attachment Gmail (pdf/docx/xlsx/ảnh)
trước khi vào extract_batch.

Đặt sau `evidence_node` (cần `item["importance"]` từ `filter_node` để
cost-gate — chỉ mail critical/important mới đáng tải file) và trước
`make_batches_node`. Mutate item trong `state["filtered"]` tại chỗ (thêm
`item["attachment_text"]`), theo đúng pattern `evidence_node` — không cần key
mới trong `PipelineState`.

Mỗi attachment: guardrail an toàn (`src/guardrail/attachment_safety.py`) →
tải bytes qua `GmailConnector.download_attachment` → route theo mimeType tới
`src/services/attachment_extract.py` → `sanitize_untrusted_text` (nội dung
file cũng là dữ liệu không tin cậy y hệt thân mail) → ghi audit
`PipelineAttachmentExtract`. Lỗi 1 attachment không sập cả node — append vào
`errors`, item khác vẫn xử lý tiếp.
"""

from __future__ import annotations

import asyncio
import logging

from src.agents.pipeline.state import PipelineState
from src.config import get_settings
from src.connectors.registry import resolve_connector
from src.guardrail.attachment_safety import (
    AttachmentRejectedError,
    assert_safe_to_download,
    assert_uncompressed_size_ok,
    configure_pillow_pixel_cap,
    ensure_openpyxl_defusedxml_active,
    run_with_timeout,
    validate_image_bytes,
)
from src.guardrail.input import sanitize_untrusted_text
from src.models.connection import Connection
from src.models.pipeline_audit import PipelineAttachmentExtract
from src.services.attachment_extract import (
    build_langextract_config,
    extract_docx_text,
    extract_image_text,
    extract_pdf_text,
    extract_structured_signals,
    extract_xlsx_text,
)
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# critical/important một mình quá chặt trong thực tế: thang điểm ở
# filter_classify.py cần >= 60 mới tới "important", mà mail công việc bình
# thường (sender + recipient + action) hay dừng ở 50-55 -> file đính kèm không
# bao giờ được tải, tóm tắt mất hẳn phần nội dung file. Mở tới "relevant"
# (>= 35) NHƯNG chỉ khi mail thật sự đính kèm loại file nằm trong allow-list —
# cost-gate vẫn còn, chỉ là không còn cắt nhầm mail công việc thường.
_ELIGIBLE_IMPORTANCE = {"critical", "important"}
_ELIGIBLE_IMPORTANCE_WITH_SUPPORTED_FILE = _ELIGIBLE_IMPORTANCE | {"relevant"}

_PDF_MIME = "application/pdf"
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg"})
_SUPPORTED_MIME_TYPES = frozenset({_PDF_MIME, _DOCX_MIME, _XLSX_MIME}) | _IMAGE_MIME_TYPES


async def _extract_attachment_sections(
    connector,
    message_id: str,
    attachment: dict,
    settings,
    llm_factory,
) -> list[tuple[str, str]]:
    """Guardrail + tải + trích cho ĐÚNG 1 attachment. Raise
    `AttachmentRejectedError` khi bị chặn bởi chính sách (mimeType/kích thước/nghi
    zip-bomb) — caller phân biệt được với lỗi hệ thống thật để ghi status
    đúng, không phải để bắt lỗi bất ngờ.

    Trả `[(nhãn_section, text), ...]` — thống nhất 1 kiểu trả về cho mọi loại
    file (pdf/docx/xlsx đã tự tách theo trang/sheet/heading; ảnh bọc thành 1
    section "Ảnh" cho đồng nhất), để node build attachment_text dùng chung 1
    đường xử lý dù structured extraction bật hay tắt."""
    mime_type = attachment.get("mimeType", "")
    size_bytes = int(attachment.get("sizeBytes") or 0)
    attachment_id = attachment.get("attachmentId")

    assert_safe_to_download(mime_type, size_bytes, settings.attachment_max_bytes)
    if not attachment_id:
        raise AttachmentRejectedError("thiếu attachmentId trong metadata, không tải được bytes", code="other")

    timeout = settings.attachment_extraction_timeout_seconds
    file_bytes = await run_with_timeout(
        connector.download_attachment(message_id, attachment_id), timeout
    )
    assert_uncompressed_size_ok(file_bytes, mime_type, settings.attachment_max_bytes)

    if mime_type == _PDF_MIME:
        return await run_with_timeout(asyncio.to_thread(extract_pdf_text, file_bytes), timeout)
    if mime_type == _DOCX_MIME:
        return await run_with_timeout(asyncio.to_thread(extract_docx_text, file_bytes), timeout)
    if mime_type == _XLSX_MIME:
        return await run_with_timeout(asyncio.to_thread(extract_xlsx_text, file_bytes), timeout)
    if mime_type in _IMAGE_MIME_TYPES:
        await run_with_timeout(asyncio.to_thread(validate_image_bytes, file_bytes), timeout)
        # Chỉ nhánh ảnh mới cần LLM. Dựng ở đây, sau khi đã qua guardrail
        # mimeType/kích thước, để file bị từ chối không kéo theo một client thừa.
        text = await run_with_timeout(
            extract_image_text(file_bytes, mime_type, llm_factory()), timeout
        )
        return [("Ảnh", text)] if text.strip() else []
    # assert_safe_to_download đã chặn mimeType lạ từ trước — nhánh này chỉ
    # chạm tới nếu ALLOWED_MIME_TYPES và _SUPPORTED_MIME_TYPES lệch nhau.
    raise AttachmentRejectedError(f"mimeType không có route trích xuất: {mime_type}", code="type")


async def attachment_extract_node(state: PipelineState) -> dict:
    settings = get_settings()
    filtered = state.get("filtered", [])
    errors = list(state.get("errors", []))

    if not settings.attachment_extraction_enabled or not filtered:
        return {"filtered": filtered, "errors": errors}

    ensure_openpyxl_defusedxml_active()
    configure_pillow_pixel_cap(settings.attachment_max_image_pixels)

    db = state["db"]
    run_id = state["run_id"]

    # Dựng LLM lười, chỉ khi thật sự có file cần đọc. Trước đây gọi get_llm()
    # ngay tại đây, nên một run mà mọi email đều không có đính kèm — hoặc chỉ có
    # loại file không hỗ trợ — vẫn dựng client OpenAI kèm HTTP client của nó rồi
    # bỏ không dùng. Đó cũng là lý do nhóm test "bỏ qua email không đính kèm"
    # đỏ suốt: chúng cố ý chạy không có API key, mà client thì từ chối key rỗng
    # ngay lúc khởi tạo, trước cả khi node kịp quyết định bỏ qua.
    cached_llm: list = []

    def llm_when_needed():
        if not cached_llm:
            cached_llm.append(get_llm())
        return cached_llm[0]

    connection_cache: dict[int | None, Connection | None] = {}
    audit_rows: list[PipelineAttachmentExtract] = []

    # 1 config dùng chung cho cả run (1 API key, không xoay vòng giữa chừng —
    # đơn giản hoá có chủ đích, xem plan). None khi tắt flag hoặc chưa cài/
    # cấu hình được LangExtract — mọi nơi dùng nó bên dưới tự fallback.
    langextract_config = build_langextract_config() if settings.attachment_structured_extraction_enabled else None

    for item in filtered:
        attachments = item.get("attachments") or []
        # Không còn khoá cứng ở "google": Jira/Outlook nay cũng thu metadata
        # file đính kèm. Cổng thật sự là "connector này có tải file được không",
        # kiểm bằng chính khả năng của nó chứ không bằng tên provider.
        if not attachments:
            continue
        has_supported_file = any(a.get("mimeType") in _SUPPORTED_MIME_TYPES for a in attachments)
        eligible = _ELIGIBLE_IMPORTANCE_WITH_SUPPORTED_FILE if has_supported_file else _ELIGIBLE_IMPORTANCE
        if item.get("importance") not in eligible:
            continue

        connection_id = item.get("connection_id")
        if connection_id not in connection_cache:
            connection_cache[connection_id] = db.get(Connection, connection_id) if connection_id else None
        connection = connection_cache[connection_id]
        if connection is None:
            continue

        try:
            connector_cls, _ = resolve_connector(connection.provider, item.get("source_id", ""))
        except ValueError as exc:
            logger.info("Bỏ qua attachment của %s: %s", connection.provider, exc)
            continue
        if not hasattr(connector_cls, "download_attachment"):
            # Connector chưa cài đường tải file (vd Calendar) — có metadata
            # cũng không lấy được nội dung, bỏ qua im lặng thay vì ném lỗi.
            continue

        connector = connector_cls(connection, db)
        message_id = item["id"]
        # Ưu tiên attachment thuộc allow-list trước, cắt tối đa N cái/mail —
        # 1 email đính kèm 10 file không được kéo cả 10 vào 1 run.
        ranked = sorted(attachments, key=lambda a: a.get("mimeType") not in _SUPPORTED_MIME_TYPES)
        selected = ranked[: settings.attachment_max_per_message]

        collected_sections: list[str] = []
        for attachment in selected:
            filename = attachment.get("filename", "(không tên)")
            mime_type = attachment.get("mimeType", "")
            size_bytes = int(attachment.get("sizeBytes") or 0)
            status = "failed"
            sections: list[tuple[str, str]] = []
            try:
                sections = await _extract_attachment_sections(
                    connector, message_id, attachment, settings, llm_when_needed
                )
                status = "ok" if any(text.strip() for _, text in sections) else "ok_empty"
            except AttachmentRejectedError as exc:
                status = {"type": "skipped_type", "size": "skipped_size"}.get(exc.code, "skipped_other")
                logger.info("Bỏ qua attachment %s (%s): %s", filename, message_id, exc)
            except TimeoutError:
                status = "failed"
                errors.append(f"attachment_extract timeout ({filename}, mail {message_id})")
            except Exception as exc:  # noqa: BLE001 - 1 file lỗi không được sập cả node
                status = "failed"
                errors.append(f"attachment_extract lỗi ({filename}, mail {message_id}): {exc}")

            # Cố dùng LangExtract (structured, có provenance section) nếu bật
            # flag + config hợp lệ; bất kỳ lỗi nào ở bước này (rate limit, key
            # sai, model từ chối...) đều fallback về nối phẳng section — 1
            # feature tùy chọn không được làm mất hẳn attachment_text.
            structured_signals: list[dict[str, str]] | None = None
            if sections and langextract_config is not None:
                try:
                    structured_signals = await run_with_timeout(
                        asyncio.to_thread(extract_structured_signals, sections, langextract_config),
                        settings.attachment_extraction_timeout_seconds,
                    )
                except Exception as exc:  # noqa: BLE001 - fallback nối phẳng, không sập node
                    logger.info(
                        "LangExtract lỗi (%s, mail %s), fallback nối phẳng section: %s", filename, message_id, exc
                    )

            if structured_signals:
                body = "\n".join(f"[{signal['section']}] {signal['text']}" for signal in structured_signals)
            else:
                body = "\n\n".join(f"[{label}]\n{text}" for label, text in sections if text.strip())

            clean_text = sanitize_untrusted_text(body) if body else ""
            clean_text = clean_text[: settings.attachment_max_extracted_chars]
            if clean_text:
                collected_sections.append(f"[Đính kèm: {filename}]\n{clean_text}")

            audit_rows.append(
                PipelineAttachmentExtract(
                    run_id=run_id,
                    normalized_message_id=item.get("_pipeline_normalized_message_id"),
                    filename=filename,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    status=status,
                    extracted_text=clean_text,
                    extracted_chars=len(clean_text),
                    structured_extract=structured_signals,
                )
            )

        if collected_sections:
            item["attachment_text"] = "\n\n".join(collected_sections)

    for row in audit_rows:
        db.add(row)
    if audit_rows:
        db.commit()

    return {"filtered": filtered, "errors": errors}
