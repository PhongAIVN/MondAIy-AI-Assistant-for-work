import asyncio
import io
import zipfile

import pytest

from src.guardrail.attachment_safety import (
    AttachmentRejectedError,
    assert_safe_to_download,
    assert_uncompressed_size_ok,
    configure_pillow_pixel_cap,
    ensure_openpyxl_defusedxml_active,
    run_with_timeout,
    validate_image_bytes,
)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_assert_safe_to_download_rejects_disallowed_mime_type():
    with pytest.raises(AttachmentRejectedError, match="mimeType") as excinfo:
        assert_safe_to_download("application/x-msdownload", 100, max_bytes=1000)
    assert excinfo.value.code == "type"


def test_assert_safe_to_download_rejects_oversized_file():
    with pytest.raises(AttachmentRejectedError, match="vượt trần") as excinfo:
        assert_safe_to_download("application/pdf", 2000, max_bytes=1000)
    assert excinfo.value.code == "size"


def test_assert_safe_to_download_allows_within_limits():
    assert_safe_to_download("application/pdf", 500, max_bytes=1000)


def test_assert_uncompressed_size_ok_ignores_non_zip_mime_types():
    # PDF/image không phải zip container — hàm không cần mở gì cả.
    assert_uncompressed_size_ok(b"not a zip", "application/pdf", max_bytes=10)


def test_assert_uncompressed_size_ok_rejects_bad_zip():
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with pytest.raises(AttachmentRejectedError, match="không phải zip"):
        assert_uncompressed_size_ok(b"not actually a zip file", docx_mime, max_bytes=10_000)


def test_assert_uncompressed_size_ok_rejects_zip_bomb():
    # Nén 1 chuỗi lặp lại lớn — kích thước nén nhỏ, giải nén vượt trần.
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    bomb = _zip_bytes({"big.xml": b"0" * 200_000})
    assert len(bomb) < 5_000  # nén rất gọn nhờ toàn số 0 lặp lại
    with pytest.raises(AttachmentRejectedError, match="zip-bomb") as excinfo:
        assert_uncompressed_size_ok(bomb, xlsx_mime, max_bytes=50_000)
    assert excinfo.value.code == "size"


def test_assert_uncompressed_size_ok_allows_normal_docx_zip():
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    small = _zip_bytes({"word/document.xml": b"<xml>hello</xml>"})
    assert_uncompressed_size_ok(small, docx_mime, max_bytes=1_000_000)


def test_ensure_openpyxl_defusedxml_active_does_not_raise():
    # defusedxml đã cài trong requirements của repo — chỉ cần không raise/crash.
    ensure_openpyxl_defusedxml_active()


def test_configure_pillow_pixel_cap_tightens_default():
    from PIL import Image

    original = Image.MAX_IMAGE_PIXELS
    try:
        configure_pillow_pixel_cap(1234)
        assert Image.MAX_IMAGE_PIXELS == 1234
    finally:
        Image.MAX_IMAGE_PIXELS = original


def _png_bytes(width: int, height: int) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_validate_image_bytes_accepts_normal_image():
    validate_image_bytes(_png_bytes(10, 10))


def test_validate_image_bytes_rejects_corrupt_bytes():
    from PIL import UnidentifiedImageError

    with pytest.raises(UnidentifiedImageError):
        validate_image_bytes(b"not an image at all")


def test_validate_image_bytes_rejects_pixel_bomb():
    from PIL import Image

    original = Image.MAX_IMAGE_PIXELS
    try:
        configure_pillow_pixel_cap(100)
        with pytest.raises(Image.DecompressionBombError):
            validate_image_bytes(_png_bytes(50, 50))
    finally:
        Image.MAX_IMAGE_PIXELS = original


@pytest.mark.asyncio
async def test_run_with_timeout_returns_result_within_deadline():
    async def quick():
        return "ok"

    assert await run_with_timeout(quick(), seconds=1) == "ok"


@pytest.mark.asyncio
async def test_run_with_timeout_raises_on_slow_task():
    async def slow():
        await asyncio.sleep(1)
        return "too late"

    with pytest.raises(asyncio.TimeoutError):
        await run_with_timeout(slow(), seconds=0.05)
