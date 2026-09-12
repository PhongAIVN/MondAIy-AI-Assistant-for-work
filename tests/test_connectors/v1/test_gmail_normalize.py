import base64

from src.connectors.base import Source
from src.connectors.gmail import GmailConnector


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def _synthetic_message(from_header: str, body_text: str) -> dict:
    """Message Gmail API giả lập, hoàn toàn synthetic — không dùng dữ liệu thật."""
    return {
        "id": "msg-synthetic-001",
        "threadId": "thread-synthetic-001",
        "internalDate": "1735689600000",  # 2025-01-01T00:00:00Z
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": "Test subject"},
            ],
            "body": {"data": _b64(body_text)},
        },
    }


class _FakeConnection:
    def __init__(self, provider_user_id: str) -> None:
        self.provider_user_id = provider_user_id


def _connector(provider_user_id: str) -> GmailConnector:
    return GmailConnector(_FakeConnection(provider_user_id), db=None)


def test_normalize_extracts_plain_text_body():
    connector = _connector("me@example.test")
    raw = _synthetic_message("Sender Name <sender@example.test>", "Vui lòng nộp báo cáo trước thứ Sáu.")
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["text"] == "Vui lòng nộp báo cáo trước thứ Sáu."
    assert result["author_id"] == "sender@example.test"
    assert result["author_name"] == "Sender Name"
    assert result["provider"] == "google"
    assert result["source_id"] == "INBOX"
    assert result["is_dm"] is False


def test_normalize_is_self_true_when_from_matches_connection_email():
    connector = _connector("me@example.test")
    raw = _synthetic_message("Me <ME@Example.test>", "Đã gửi xong.")
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["is_self"] is True


def test_normalize_is_self_false_when_from_differs():
    connector = _connector("me@example.test")
    raw = _synthetic_message("Other <other@example.test>", "Nội dung khác.")
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["is_self"] is False


def test_normalize_flags_marketing_boilerplate_even_though_text_is_stripped():
    # Bug thật: mail marketing (Font Awesome) có "unsubscribe"/preferences
    # link ở cuối thân mail. _strip_boilerplate xoá đúng cụm đó khỏi "text"
    # hiển thị, khiến filter_classify.py mất tín hiệu newsletter và cho mail
    # quảng cáo lọt qua như task thật. has_marketing_boilerplate phải chấm
    # TRƯỚC khi bị xoá.
    connector = _connector("me@example.test")
    body = (
        "Join us Wednesday for a live demo, a few sneak peeks at what's next.\n\n"
        "--\nUnsubscribe: https://example.test/email/preferences/?token=abc"
    )
    raw = _synthetic_message("Marketing <hello@marketing.example.test>", body)
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["has_marketing_boilerplate"] is True
    assert "unsubscribe" not in result["text"].lower()


def test_normalize_marketing_boilerplate_false_for_ordinary_mail():
    connector = _connector("me@example.test")
    raw = _synthetic_message("Mentor <mentor@example.test>", "Vui lòng nộp báo cáo trước thứ Sáu.")
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["has_marketing_boilerplate"] is False


def test_normalize_stamps_mailbox_email_from_connection_not_message_headers():
    # filter_classify.py phải so khớp to/cc với đúng mailbox ĐANG đồng bộ
    # (connection.provider_user_id), khác User.email đăng nhập app — normalize()
    # là nơi duy nhất biết connection nào đang chạy nên phải stamp field này.
    connector = _connector("Me@Example.test")
    raw = _synthetic_message("Sender <sender@example.test>", "Nội dung.")
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["mailbox_email"] == "me@example.test"


def test_normalize_extracts_attachment_id_needed_to_download_bytes():
    connector = _connector("me@example.test")
    raw = _synthetic_message("Sender <sender@example.test>", "Xem file đính kèm.")
    raw["payload"]["parts"] = [
        {
            "filename": "bao-cao.pdf",
            "mimeType": "application/pdf",
            "body": {"size": 12345, "attachmentId": "ATT-xyz-123"},
        }
    ]
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["attachments"] == [
        {
            "filename": "bao-cao.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 12345,
            "attachmentId": "ATT-xyz-123",
        }
    ]


def _html_message(from_header: str, html_body: str) -> dict:
    return {
        "id": "msg-html-001",
        "threadId": "thread-html-001",
        "internalDate": "1735689600000",
        "payload": {
            "mimeType": "text/html",
            "headers": [
                {"name": "From", "value": from_header},
                {"name": "Subject", "value": "Test subject"},
            ],
            "body": {"data": _b64(html_body)},
        },
    }


def test_normalize_strips_hidden_preheader_and_footer_boilerplate_from_html():
    connector = _connector("me@example.test")
    raw = _html_message(
        "Sender <sender@example.test>",
        "<div style=\"display:none\">Preheader ẩn không nên xuất hiện</div>"
        "<p>Vui lòng nộp báo cáo trước thứ Sáu.</p>"
        "<p>Vui lòng không trả lời email này. Copyright © 2026. All rights reserved. Unsubscribe here.</p>",
    )
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert "Preheader ẩn" not in result["text"]
    assert "Unsubscribe" not in result["text"]
    assert "All rights reserved" not in result["text"]
    assert "Vui lòng nộp báo cáo trước thứ Sáu." in result["text"]


def test_normalize_finds_plain_text_inside_multipart():
    connector = _connector("me@example.test")
    raw = {
        "id": "msg-multipart-001",
        "threadId": "thread-multipart-001",
        "internalDate": "1735689600000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [{"name": "From", "value": "sender@example.test"}],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>html</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("plain text body")}},
            ],
        },
    }
    source = Source(id="INBOX", name="Hộp thư chính")

    result = connector.normalize(raw, source)

    assert result["text"] == "plain text body"


def test_deep_link_points_to_gmail_web_ui():
    connector = _connector("me@example.test")
    raw = {"id": "msg-synthetic-001"}

    assert connector.deep_link(raw) == (
        "https://mail.google.com/mail/u/0/?authuser=me%40example.test#all/msg-synthetic-001"
    )


def test_deep_link_omits_authuser_when_account_unknown():
    # Không có provider_user_id (kết nối cũ/thiếu dữ liệu) — vẫn trả link Gmail
    # hợp lệ ở slot mặc định, không throw.
    connector = _connector("")
    raw = {"id": "msg-synthetic-001"}

    assert connector.deep_link(raw) == "https://mail.google.com/mail/u/0/#all/msg-synthetic-001"
