"""Che định danh trước khi payload rời hệ thống qua observability."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"(?P<local>[a-z0-9.!#$%&'*+/=?^_`{|}~-]+)"
    r"@(?P<domain>(?:[a-z0-9-]+\.)+[a-z]{2,63})"
    r"(?![\w.-])",
    re.IGNORECASE,
)
_ENCODED_EMAIL_PATTERN = re.compile(
    r"(?<![\w.%+-])"
    r"(?P<local>[a-z0-9.!#$&'*+_-]+)"
    r"%40(?P<domain>(?:[a-z0-9-]+\.)+[a-z]{2,63})"
    r"(?![\w.-])",
    re.IGNORECASE,
)
_VN_MOBILE_PATTERN = re.compile(
    r"(?<![\w+])(?P<phone>(?:\+84|0)[\s().-]*[35789](?:[\s().-]*\d){8})(?!\d)"
)
_INTERNATIONAL_PHONE_PATTERN = re.compile(
    r"(?<![\w+])(?P<phone>\+[1-9](?:[\s().-]*\d){7,14})(?!\d)"
)


class PiiRedactor:
    """Redactor thuần với token HMAC ổn định trong cùng một salt."""

    def __init__(self, salt: str) -> None:
        if not salt or not salt.strip():
            raise ValueError("LANGSMITH_PII_SALT is required when LangSmith PII redaction is enabled")
        self._key = salt.encode("utf-8")

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.redact(payload)

    def redact(self, value: Any) -> Any:
        """Tạo bản sao đã che; không sửa payload đầu vào."""
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {
                self.redact_text(key) if isinstance(key, str) else key: self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        return value

    def redact_text(self, text: str) -> str:
        """Che email và phone, giữ nguyên mọi phần không khớp."""
        redacted = _ENCODED_EMAIL_PATTERN.sub(self._replace_encoded_email, text)
        redacted = _EMAIL_PATTERN.sub(self._replace_email, redacted)
        redacted = _VN_MOBILE_PATTERN.sub(self._replace_phone, redacted)
        return _INTERNATIONAL_PHONE_PATTERN.sub(self._replace_phone, redacted)

    def _token(self, kind: str, canonical_value: str) -> str:
        digest = hmac.new(
            self._key,
            f"{kind}:{canonical_value}".encode(),
            hashlib.sha256,
        ).hexdigest()[:12]
        return f"[{kind}:{digest}]"

    def _replace_email(self, match: re.Match[str]) -> str:
        canonical = f"{match.group('local')}@{match.group('domain')}".lower()
        return self._token("email", canonical)

    def _replace_encoded_email(self, match: re.Match[str]) -> str:
        canonical = f"{match.group('local')}@{match.group('domain')}".lower()
        return self._token("email", canonical)

    def _replace_phone(self, match: re.Match[str]) -> str:
        raw = match.group("phone")
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("0") and len(digits) == 10:
            canonical = f"+84{digits[1:]}"
        else:
            canonical = f"+{digits}"
        return self._token("phone", canonical)
