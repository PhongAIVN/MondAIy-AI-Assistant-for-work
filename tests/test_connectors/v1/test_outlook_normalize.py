import pytest

from src.connectors.base import Source
from src.connectors.outlook import OutlookConnector


class _FakeConnection:
    def __init__(self, provider_user_id: str | None) -> None:
        self.provider_user_id = provider_user_id


def _connector(provider_user_id: str | None = "me@outlook.com") -> OutlookConnector:
    return OutlookConnector(_FakeConnection(provider_user_id), db=None)


def _synthetic_message(
    *,
    from_email: str = "mentor@example.com",
    from_name: str = "Mentor",
    subject: str = "Deadline nộp báo cáo",
    content: str = "<p>Vui lòng nộp báo cáo trước <b>thứ Sáu</b>.</p>",
    content_type: str = "html",
    is_read: bool = False,
) -> dict:
    return {
        "id": "AAMkAG-1",
        "subject": subject,
        "from": {"emailAddress": {"address": from_email, "name": from_name}},
        "toRecipients": [{"emailAddress": {"address": "me@outlook.com", "name": "Me"}}],
        "ccRecipients": [],
        "receivedDateTime": "2026-08-13T09:00:00Z",
        "body": {"contentType": content_type, "content": content},
        "bodyPreview": "Vui lòng nộp báo cáo trước thứ Sáu.",
        "isRead": is_read,
        "conversationId": "conv-1",
        "webLink": "https://outlook.office.com/mail/inbox/id/AAMkAG-1",
        "hasAttachments": False,
    }


def test_normalize_strips_html_body_to_plain_text():
    connector = _connector()
    result = connector.normalize(_synthetic_message(), Source(id="inbox", name="Hộp thư chính"))

    assert "Vui lòng nộp báo cáo trước" in result["text"]
    assert "<b>" not in result["text"]
    assert result["provider"] == "outlook"
    assert result["id"] == "AAMkAG-1"
    assert result["subject"] == "Deadline nộp báo cáo"


def test_normalize_keeps_plain_text_body_as_is():
    connector = _connector()
    raw = _synthetic_message(content="Vui lòng nộp báo cáo trước thứ Sáu.", content_type="text")

    result = connector.normalize(raw, Source(id="inbox", name="Hộp thư chính"))

    assert result["text"] == "Vui lòng nộp báo cáo trước thứ Sáu."


def test_normalize_is_self_true_when_sender_matches_connection():
    connector = _connector("mentor@example.com")
    result = connector.normalize(
        _synthetic_message(from_email="mentor@example.com"), Source(id="inbox", name="Hộp thư chính")
    )

    assert result["is_self"] is True


def test_normalize_is_self_false_when_sender_differs():
    connector = _connector("me@outlook.com")
    result = connector.normalize(
        _synthetic_message(from_email="mentor@example.com"), Source(id="inbox", name="Hộp thư chính")
    )

    assert result["is_self"] is False


def test_normalize_is_unread_from_is_read_flag():
    connector = _connector()
    result = connector.normalize(_synthetic_message(is_read=False), Source(id="inbox", name="Hộp thư chính"))
    assert result["is_unread"] is True

    result_read = connector.normalize(_synthetic_message(is_read=True), Source(id="inbox", name="Hộp thư chính"))
    assert result_read["is_unread"] is False


def test_normalize_to_and_cc_addresses_lowercased():
    connector = _connector()
    raw = _synthetic_message()
    raw["toRecipients"] = [{"emailAddress": {"address": "Student@Example.com", "name": "Student"}}]
    raw["ccRecipients"] = [{"emailAddress": {"address": "Mentor2@Example.com", "name": "Mentor2"}}]

    result = connector.normalize(raw, Source(id="inbox", name="Hộp thư chính"))

    assert result["to"] == ["student@example.com"]
    assert result["cc"] == ["mentor2@example.com"]


def test_deep_link_uses_graph_web_link_directly():
    connector = _connector()
    raw = _synthetic_message()

    assert connector.deep_link(raw) == "https://outlook.office.com/mail/inbox/id/AAMkAG-1"


def test_deep_link_empty_string_when_web_link_missing():
    connector = _connector()
    raw = _synthetic_message()
    del raw["webLink"]

    assert connector.deep_link(raw) == ""


@pytest.mark.asyncio
async def test_list_sources_returns_only_inbox():
    connector = _connector()
    sources = await connector.list_sources()

    assert len(sources) == 1
    assert sources[0].id == "inbox"
