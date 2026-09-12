"""Phòng thủ file đính kèm nguy hiểm.

Khác `input.py` (phòng LLM-input text sau khi đã có text) — module này phòng
lớp tấn công TRƯỚC đó: chính file đính kèm được dùng để khai thác parser
(zip-bomb, ảnh decompression-bomb, mimeType/kích thước không hợp lệ).

Không cố phòng mọi CVE có thể có trong pypdf/python-docx/openpyxl/Pillow —
mục tiêu là chặn các lớp tấn công phổ biến nhất bằng kiểm tra rẻ,
deterministic, trước khi nội dung chạm parser thật.

Ghi chú quan trọng (đã verify bằng cách đọc source 2 lib, không đoán):
- `python-docx` tự dựng parser lxml riêng với `resolve_entities=False`
  (`docx/oxml/parser.py`) — đã an toàn XXE/entity-expansion sẵn, không cần
  patch thêm.
- `openpyxl` tự chuyển sang `defusedxml.ElementTree` khi thấy package
  `defusedxml` có cài (`openpyxl/xml/__init__.py`, biến `DEFUSEDXML`) — chỉ
  cần có mặt trong requirements, không cần gọi API nào để "bật".
- Cả hai đều KHÔNG phòng zip-bomb (kích thước sau giải nén phình so với file
  nén) — đây là lớp phòng thủ thật sự module này phải tự làm.
- `Pillow` đã có `Image.MAX_IMAGE_PIXELS` mặc định (~89.5 triệu) tự raise khi
  vượt — `configure_pillow_pixel_cap` chỉ tightening thêm cho mục đích
  chi phí/context, không phải xây từ đầu.
"""

from __future__ import annotations

import asyncio
import logging
import zipfile
from collections.abc import Awaitable
from io import BytesIO
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# mimeType Gmail trả cho các loại file được hỗ trợ trích nội dung.
ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
        "image/png",
        "image/jpeg",
    }
)

# docx/xlsx là file zip+XML bên trong — cần check kích thước sau giải nén
# trước khi cho python-docx/openpyxl mở thật.
_ZIP_MIME_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)


class AttachmentRejectedError(Exception):
    """File bị từ chối trước khi tải hoặc trước khi parse.

    Đây là quyết định chính sách (mimeType/kích thước/nghi zip-bomb), không
    phải lỗi hệ thống — caller nên bắt riêng để ghi status thay vì coi là
    exception bất ngờ. `code` cho caller phân loại status audit mà không cần
    string-match vào message (message chỉ để log/debug).
    """

    def __init__(self, message: str, *, code: str = "other") -> None:
        super().__init__(message)
        self.code = code


def assert_safe_to_download(mime_type: str, size_bytes: int, max_bytes: int) -> None:
    """Chạy TRƯỚC khi gọi Gmail API tải bytes — chặn sớm, đỡ tốn round-trip."""
    if mime_type not in ALLOWED_MIME_TYPES:
        raise AttachmentRejectedError(f"mimeType không được hỗ trợ: {mime_type}", code="type")
    if size_bytes <= 0:
        raise AttachmentRejectedError("size_bytes không hợp lệ", code="other")
    if size_bytes > max_bytes:
        raise AttachmentRejectedError(
            f"file vượt trần {max_bytes} bytes (khai báo {size_bytes} bytes)", code="size"
        )


def assert_uncompressed_size_ok(file_bytes: bytes, mime_type: str, max_bytes: int) -> None:
    """Chặn zip-bomb: đọc `ZipInfo.file_size` (kích thước sau giải nén) của
    từng entry TRƯỚC khi cho python-docx/openpyxl giải nén thật.

    defusedxml (openpyxl) và `resolve_entities=False` (python-docx) chỉ phòng
    entity-expansion bên trong XML — không phòng zip container tự nó chứa
    nội dung giải nén khổng lồ so với kích thước file nén.
    """
    if mime_type not in _ZIP_MIME_TYPES:
        return
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
            total_uncompressed = sum(info.file_size for info in archive.infolist())
    except zipfile.BadZipFile as exc:
        raise AttachmentRejectedError(f"file không phải zip hợp lệ: {exc}", code="other") from exc
    if total_uncompressed > max_bytes:
        raise AttachmentRejectedError(
            f"kích thước sau giải nén vượt trần ({total_uncompressed} > {max_bytes} bytes) — nghi zip-bomb",
            code="size",
        )


def ensure_openpyxl_defusedxml_active() -> None:
    """Cảnh báo nếu openpyxl vì lý do gì đó (thiếu package, env var override)
    không dùng được defusedxml — để không âm thầm mất lớp phòng XXE cho XLSX.

    Không raise: đây là log cảnh báo vận hành, không phải điều kiện chặn 1
    file cụ thể.
    """
    from openpyxl.xml import DEFUSEDXML

    if not DEFUSEDXML:
        logger.warning(
            "openpyxl không dùng defusedxml (thiếu package hoặc OPENPYXL_DEFUSEDXML=False) — "
            "XLSX đính kèm có thể dính XXE nếu bị khai thác. Kiểm tra lại requirements/env."
        )


def configure_pillow_pixel_cap(max_pixels: int) -> None:
    """Tightening `Image.MAX_IMAGE_PIXELS` mặc định của Pillow — gọi 1 lần
    trước khi mở ảnh đính kèm bất kỳ."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = max_pixels


def validate_image_bytes(file_bytes: bytes) -> None:
    """Mở ảnh qua Pillow chỉ để validate — `MAX_IMAGE_PIXELS` chỉ có tác
    dụng khi thực sự gọi `Image.open()`, set biến thôi chưa kiểm tra gì.
    `verify()` raise `DecompressionBombError`/`UnidentifiedImageError` nếu
    ảnh vượt trần pixel hoặc không phải ảnh hợp lệ, không cần giữ ảnh mở lại
    sau đó vì ta chỉ forward bytes gốc cho vision LLM, không tự decode pixel."""
    from PIL import Image

    with Image.open(BytesIO(file_bytes)) as image:
        image.verify()


async def run_with_timeout(awaitable: Awaitable[T], seconds: float) -> T:
    """Timeout chung cho mọi bước extract — file méo/cố ý ác ý có thể làm
    parser treo lâu bất thường. Caller bọc hàm sync bằng
    `asyncio.to_thread(...)` trước khi truyền vào đây."""
    return await asyncio.wait_for(awaitable, timeout=seconds)
