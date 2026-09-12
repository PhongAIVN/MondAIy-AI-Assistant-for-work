"""Cấu hình duy nhất cho dữ liệu outbound sang LangSmith."""

from __future__ import annotations

from functools import lru_cache

import langsmith
from langsmith.utils import tracing_is_enabled

from src.config import get_settings
from src.guardrail.pii import PiiRedactor


@lru_cache(maxsize=1)
def configure_langsmith_client() -> None:
    """Cài client global trước khi API hoặc worker tạo trace đầu tiên."""
    if not tracing_is_enabled():
        return

    settings = get_settings()
    anonymizer = None
    if settings.langsmith_pii_redaction_enabled:
        anonymizer = PiiRedactor(settings.langsmith_pii_salt.get_secret_value())

    client = langsmith.Client(
        anonymizer=anonymizer,
        hide_inputs=settings.langsmith_hide_inputs,
        hide_outputs=settings.langsmith_hide_outputs,
    )
    langsmith.configure(client=client)
