"""Read-only agent tools for the optional AnythingLLM Gmail bridge."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from types import MappingProxyType

from langchain_core.tools import tool

from src.services.gmail_bridge import (
    bridge_available,
    build_bridge_queries,
    read_bridge_thread,
    search_bridge_threads,
)

logger = logging.getLogger(__name__)
_user_id: ContextVar[str | None] = ContextVar("gmail_bridge_user_id", default=None)

GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS = MappingProxyType(
    {
        "gmail_bridge_search": "Gmail bridge chưa được bật hoặc chưa được cấp cho user hiện tại; luồng Gmail OAuth hiện tại vẫn được giữ nguyên.",
        "gmail_bridge_read_thread": "Gmail bridge chưa được bật hoặc chưa được cấp cho user hiện tại.",
    }
)


def set_gmail_bridge_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_gmail_bridge_scope() -> None:
    _user_id.set(None)


def _format_thread(item: dict) -> str:
    flags = ", ".join(
        name for name, enabled in (
            ("unread", item.get("is_unread")),
            ("important", item.get("is_important")),
            ("starred", item.get("has_starred_messages")),
        ) if enabled
    )
    suffix = f"; flags={flags}" if flags else ""
    return (
        f"Thread ID: {item.get('id', '')}\n"
        f"Tiêu đề: {item.get('subject', '(không có tiêu đề)')}\n"
        f"Thời gian gần nhất: {item.get('sent_at') or 'không rõ'}\n"
        f"Số message: {item.get('message_count', 0)}{suffix}\n"
        f"Nguồn: {item.get('source', 'anythingllm_gmail_bridge')}"
        + (f"\nLink: {item['deep_link']}" if item.get("deep_link") else "")
    )


@tool
async def gmail_bridge_search(query: str = "", time_from: str = "", time_to: str = "", max_results: int = 20) -> str:
    """Search Gmail through an optional AnythingLLM-compatible read bridge.

    This deliberately runs complementary queries: one constrained by sent date,
    and one over a wider history looking for the requested terms in message
    content. It does not modify Gmail.
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được mailbox của ai nên chưa đọc Gmail bridge."
    if not bridge_available(user_id):
        return GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS["gmail_bridge_search"]

    from src.agents.tools.time_tool import parse_timestamp

    start = parse_timestamp(time_from)
    end = parse_timestamp(time_to)
    if start is None or end is None or start.moment >= end.moment:
        return "Cần time_from và time_to hợp lệ để bridge tìm Gmail có giới hạn."
    try:
        queries = build_bridge_queries(query, start.moment, end.moment)
        threads = await search_bridge_threads(queries, max(1, min(int(max_results), 50)))
    except Exception as exc:
        logger.warning("Gmail bridge search failed for scoped user: %s", exc)
        return f"Gmail bridge coverage: partial (bridge_error: {exc})"
    if not threads:
        return "Gmail bridge không tìm thấy thread phù hợp; kết quả này không phủ định các luồng Gmail khác."
    return "Gmail bridge coverage: complete; queries=" + str(len(queries)) + "\n\n" + "\n\n".join(_format_thread(item) for item in threads)


@tool
async def gmail_bridge_read_thread(thread_id: str) -> str:
    """Read one bridge thread after its ID was returned by gmail_bridge_search."""
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được mailbox của ai nên chưa đọc Gmail bridge."
    if not bridge_available(user_id):
        return GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS["gmail_bridge_read_thread"]
    if not thread_id.strip():
        return "Cần thread_id từ gmail_bridge_search."
    try:
        messages = await read_bridge_thread(thread_id)
    except Exception as exc:
        logger.warning("Gmail bridge thread read failed: %s", exc)
        return f"Gmail bridge coverage: partial (bridge_error: {exc})"
    if not messages:
        return "Gmail bridge không trả về message nào cho thread này."
    return "\n\n".join(str(message) for message in messages)
