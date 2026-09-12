import re
from copy import deepcopy

import pytest

from src.guardrail.pii import PiiRedactor

_EMAIL_TOKEN_PATTERN = re.compile(r"\[email:[0-9a-f]{12}\]")
_PHONE_TOKEN_PATTERN = re.compile(r"\[phone:[0-9a-f]{12}\]")
_LEAKED_EMAIL_PATTERN = re.compile(
    r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+(?:@|%40)(?:[a-z0-9-]+\.)+[a-z]{2,63}",
    re.IGNORECASE,
)


def test_same_email_is_redacted_to_same_deterministic_token() -> None:
    redacted = PiiRedactor("test-only-salt").redact_text(
        "Gửi tới learner@example.com rồi nhắc lại learner@example.com"
    )

    tokens = _EMAIL_TOKEN_PATTERN.findall(redacted)
    assert len(tokens) == 2
    assert tokens[0] == tokens[1]
    assert "learner@example.com" not in redacted


def test_distinct_emails_get_distinct_tokens() -> None:
    redacted = PiiRedactor("test-only-salt").redact_text(
        "Người gửi first@example.com, người nhận second@example.com"
    )

    tokens = _EMAIL_TOKEN_PATTERN.findall(redacted)
    assert len(tokens) == 2
    assert len(set(tokens)) == 2
    assert "first@example.com" not in redacted
    assert "second@example.com" not in redacted


def test_vietnamese_and_international_phone_numbers_are_redacted() -> None:
    redacted = PiiRedactor("test-only-salt").redact_text(
        "Gọi 0912345678 hoặc +84987654321 để xác nhận"
    )

    assert "0912345678" not in redacted
    assert "+84987654321" not in redacted
    assert len(_PHONE_TOKEN_PATTERN.findall(redacted)) == 2


def test_url_encoded_authuser_email_is_redacted_without_changing_the_url() -> None:
    encoded_email = "learner%40gmail.com"
    source_url = (
        "https://mail.google.com/mail/u/0/?authuser="
        f"{encoded_email}#all/1a03b95c0d0a7cb7"
    )

    redacted = PiiRedactor("test-only-salt").redact_text(source_url)
    token = _EMAIL_TOKEN_PATTERN.search(redacted)

    assert token is not None
    assert redacted == source_url.replace(encoded_email, token.group())


def test_text_without_pii_is_returned_unchanged() -> None:
    text = "Xin chào, đây là bản nhắc công việc lúc 08:01 ICT."

    assert PiiRedactor("test-only-salt").redact_text(text) == text


def test_empty_salt_fails_at_redactor_initialization() -> None:
    with pytest.raises(ValueError, match="LANGSMITH_PII_SALT"):
        PiiRedactor("")


def test_redactor_recurses_through_dict_list_dict_without_mutating_input() -> None:
    payload = {
        "trace": [
            {
                "input": "Liên hệ nested@example.com",
                "metadata": {"phone": "0912345678", "attempt": 1},
            }
        ]
    }
    original = deepcopy(payload)

    redacted = PiiRedactor("test-only-salt")(payload)

    assert payload == original
    assert redacted["trace"][0]["metadata"]["attempt"] == 1
    assert "nested@example.com" not in redacted["trace"][0]["input"]
    assert _EMAIL_TOKEN_PATTERN.search(redacted["trace"][0]["input"])
    assert _PHONE_TOKEN_PATTERN.fullmatch(redacted["trace"][0]["metadata"]["phone"])


def test_real_leaked_trace_contains_no_email_after_redaction() -> None:
    encoded_email = "hoaianthai345%40gmail.com"
    trace = (
        "nguồn: https://mail.google.com/mail/u/0/?authuser="
        f"{encoded_email}#all/1a03b95c0d0a7cb7\n"
        "Người gửi: Đức Dũng (Jira)\n"
        "Xin chào HoàiAn Thái, Đây là bản nhắc công việc lúc 08:01 ICT"
    )

    redacted = PiiRedactor("test-only-salt").redact_text(trace)
    token = _EMAIL_TOKEN_PATTERN.search(redacted)

    assert token is not None
    assert _LEAKED_EMAIL_PATTERN.search(redacted) is None
    assert redacted == trace.replace(encoded_email, token.group())
