"""Metadata file đính kèm của Outlook.

Graph trả `attachments[]` khi được `$expand`; trước đây `normalize()` trả cứng
`"attachments": []`.
"""

from src.connectors.outlook import _extract_attachment_metadata


def test_expanded_attachments_are_mapped_to_the_shared_shape():
    raw = {
        "attachments": [
            {"id": "AAA", "name": "bao-cao.pdf", "contentType": "application/pdf", "size": 4096},
        ]
    }

    [item] = _extract_attachment_metadata(raw)

    assert item == {
        "filename": "bao-cao.pdf",
        "mimeType": "application/pdf",
        "sizeBytes": 4096,
        "attachmentId": "AAA",
    }


def test_inline_images_are_not_treated_as_documents():
    """Ảnh chèn trong chữ ký/thân mail không phải tài liệu đính kèm; trích
    chúng chỉ sinh nhiễu."""
    raw = {
        "attachments": [
            {"id": "1", "name": "logo.png", "contentType": "image/png", "size": 10, "isInline": True},
            {"id": "2", "name": "ke-hoach.xlsx", "size": 10,
             "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ]
    }

    assert [item["filename"] for item in _extract_attachment_metadata(raw)] == ["ke-hoach.xlsx"]


def test_a_message_without_attachments_is_not_a_crash():
    assert _extract_attachment_metadata({}) == []
