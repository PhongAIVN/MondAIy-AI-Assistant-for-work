"""Metadata file đính kèm của Jira.

`normalize()` trước đây trả cứng `"attachments": []`, nên
attachment_extract_node không có gì để tải và tóm tắt Jira mất hẳn phần nội
dung file — đúng lỗi đã sửa cho Gmail.
"""

from src.connectors.jira import _extract_attachment_metadata


def test_extractable_files_are_mapped_to_the_shared_shape():
    fields = {
        "attachment": [
            {"id": "10001", "filename": "review.pdf", "mimeType": "application/pdf", "size": 2048,
             "content": "https://api.atlassian.com/.../10001"},
        ]
    }

    [item] = _extract_attachment_metadata(fields)

    assert item["filename"] == "review.pdf"
    assert item["mimeType"] == "application/pdf"
    assert item["sizeBytes"] == 2048
    assert item["attachmentId"] == "10001"
    assert item["contentUrl"].endswith("10001")


def test_files_the_pipeline_cannot_read_are_dropped_at_the_connector():
    """Lọc ngay ở connector để metadata của zip/exe không chiếm chỗ trong
    attachment_max_per_message rồi bị node loại sau."""
    fields = {
        "attachment": [
            {"id": "1", "filename": "src.zip", "mimeType": "application/zip", "size": 10},
            {"id": "2", "filename": "ok.docx", "size": 10,
             "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ]
    }

    result = _extract_attachment_metadata(fields)

    assert [item["filename"] for item in result] == ["ok.docx"]


def test_an_issue_without_attachments_is_not_a_crash():
    assert _extract_attachment_metadata({}) == []
    assert _extract_attachment_metadata({"attachment": None}) == []
