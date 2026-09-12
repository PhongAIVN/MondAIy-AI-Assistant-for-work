"""Read-only AnythingLLM-compatible Gmail bridge.

The official AnythingLLM Gmail Agent bridge exposes a small Apps Script HTTP
API.  This adapter deliberately implements only search/read operations and
keeps credentials in Settings, never in tool arguments or logs.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.config import get_settings

MAX_QUERY_CHARS = 400
MAX_QUERY_VARIANTS = 4
HISTORICAL_LOOKBACK_DAYS = 180


def bridge_available(user_id: str | None) -> bool:
    settings = get_settings()
    return bool(
        user_id
        and settings.anythingllm_gmail_bridge_enabled
        and settings.anythingllm_gmail_bridge_url
        and settings.anythingllm_gmail_bridge_api_key
        and settings.anythingllm_gmail_bridge_user_id == user_id
    )


def _gmail_date(moment: datetime) -> str:
    return moment.strftime("%Y/%m/%d")


def _quote_terms(text: str) -> list[str]:
    folded = text.casefold()
    terms: list[str] = []
    for token in re.findall(r"[\wÀ-ỹ@.-]{3,}", text, flags=re.UNICODE):
        if token.casefold() in {"gmail", "email", "mail", "deadline", "tháng", "month"}:
            continue
        if token.casefold() not in {item.casefold() for item in terms}:
            terms.append(token)
    if re.search(r"deadline|due|hạn|han|nộp|nop|submit", folded):
        terms.extend(["deadline", "due", "submit", "hạn chót"])
    return terms[:8]


def _month_terms(query: str) -> list[str]:
    folded = query.casefold()
    found: list[str] = []
    months = {
        1: ("january", "jan", "tháng 1", "thang 1"),
        2: ("february", "feb", "tháng 2", "thang 2"),
        3: ("march", "mar", "tháng 3", "thang 3"),
        4: ("april", "apr", "tháng 4", "thang 4"),
        5: ("may", "tháng 5", "thang 5"),
        6: ("june", "jun", "tháng 6", "thang 6"),
        7: ("july", "jul", "tháng 7", "thang 7"),
        8: ("august", "aug", "tháng 8", "thang 8"),
        9: ("september", "sep", "tháng 9", "thang 9"),
        10: ("october", "oct", "tháng 10", "thang 10"),
        11: ("november", "nov", "tháng 11", "thang 11"),
        12: ("december", "dec", "tháng 12", "thang 12"),
    }
    match = re.search(r"(?:tháng|thang|month)\s*(\d{1,2})", folded)
    if match and 1 <= int(match.group(1)) <= 12:
        found.extend(months[int(match.group(1))])
    return found


def build_bridge_queries(query: str, time_from: datetime, time_to: datetime) -> list[str]:
    """Build complementary Gmail queries, including content outside the date window."""
    direct_terms = _quote_terms(query)
    month_terms = _month_terms(query)
    content = "{" + " ".join(direct_terms + month_terms) + "}"
    content = content if content != "{}" else "{deadline due submit}"
    sent_window = f"after:{_gmail_date(time_from)} before:{_gmail_date(time_to)}"
    history_start = time_from - timedelta(days=HISTORICAL_LOOKBACK_DAYS)
    history_end = max(time_to, datetime.now(UTC)) + timedelta(days=1)

    queries = [
        f"{content} {sent_window}",
        f"{content} after:{_gmail_date(history_start)} before:{_gmail_date(history_end)}",
    ]
    if month_terms:
        month_content = "{" + " ".join(month_terms + ["deadline", "due", "submit"]) + "}"
        queries.append(f"{month_content} after:{_gmail_date(history_start)} before:{_gmail_date(history_end)}")
    unique: list[str] = []
    for item in queries:
        item = " ".join(item.split())[:MAX_QUERY_CHARS]
        if item not in unique:
            unique.append(item)
    return unique[:MAX_QUERY_VARIANTS]


def _payload_data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    if isinstance(data, dict):
        for key in ("threads", "messages", "results"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


async def _post(action: str, body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    payload = {"key": settings.anythingllm_gmail_bridge_api_key, "action": action, **body}
    async with httpx.AsyncClient(timeout=settings.anythingllm_gmail_bridge_timeout_seconds) as client:
        response = await client.post(settings.anythingllm_gmail_bridge_url, json=payload)
        response.raise_for_status()
        result = response.json()
    if isinstance(result, dict) and result.get("status") not in (None, "ok", "success"):
        raise RuntimeError(f"bridge_status={result.get('status')}")
    return result if isinstance(result, dict) else {"data": result}


def normalize_thread(item: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or item.get("threadId") or ""),
        "subject": item.get("subject") or "(no subject)",
        "sent_at": item.get("lastMessageDate") or item.get("date") or "",
        "message_count": item.get("messageCount", 0),
        "is_unread": bool(item.get("isUnread", False)),
        "is_important": bool(item.get("isImportant", False)),
        "has_starred_messages": bool(item.get("hasStarredMessages", False)),
        "deep_link": item.get("permalink") or "",
        "query": query,
        "source": "anythingllm_gmail_bridge",
    }


async def search_bridge_threads(queries: list[str], max_results: int) -> list[dict[str, Any]]:
    settings = get_settings()
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for query in queries[:MAX_QUERY_VARIANTS]:
        result = await _post("search", {"query": query[:MAX_QUERY_CHARS], "limit": min(max_results, settings.anythingllm_gmail_bridge_max_results), "start": 0})
        for item in _payload_data(result):
            normalized = normalize_thread(item, query)
            key = normalized["id"] or f"{normalized['subject']}|{normalized['sent_at']}"
            if key in seen:
                continue
            seen.add(key)
            output.append(normalized)
            if len(output) >= max_results:
                return output
    return output


async def read_bridge_thread(thread_id: str) -> list[dict[str, Any]]:
    result = await _post("read_thread", {"threadId": thread_id.strip(), "includeAttachments": False})
    return _payload_data(result)
