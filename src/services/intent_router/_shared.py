"""Helper text-normalization dùng chung giữa gmail.py/calendar.py/tool_planning.py."""

from __future__ import annotations

import unicodedata


def _fold(value: str) -> str:
    """Accent-insensitive copy so Vietnamese keyboard/transport variants route consistently."""
    return (
        "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char))
        .replace("đ", "d")
        .replace("Đ", "D")
    )
