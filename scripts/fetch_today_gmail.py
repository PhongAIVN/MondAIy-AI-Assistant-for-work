"""Print today's Gmail messages that are eligible for the agent context.

Usage (from the repository root)::

    python scripts/fetch_today_gmail.py --user-id <authenticated-user-id>

The script deliberately requires an explicit user id; it never guesses an
account from the database. Results come from ``search_gmail_messages``, so the
same deterministic noise filter used by the conversational agent is applied.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.agents.tools.time_tool import app_timezone, now
from src.db import engine
from src.services.gmail_tools import search_gmail_messages


def today_window(current: datetime) -> tuple[datetime, datetime]:
    """Return the app-timezone interval from local midnight through now."""
    return current.replace(hour=0, minute=0, second=0, microsecond=0), current


def format_output(
    messages: list[dict[str, Any]],
    time_from: datetime,
    time_to: datetime,
    *,
    include_text: bool,
) -> dict[str, Any]:
    """Make a reviewable JSON payload without printing body text by default."""
    visible = []
    for message in messages:
        item = {
            "id": message.get("id"),
            "subject": message.get("subject"),
            "from": message.get("author_id") or message.get("author_name"),
            "sent_at": str(message.get("sent_at") or ""),
            "importance": message.get("importance"),
            "importance_score": message.get("importance_score"),
            "reasons": message.get("classification_reasons", []),
            "deep_link": message.get("deep_link"),
        }
        if include_text:
            item["text_preview"] = str(
                message.get("normalized_text") or message.get("text") or message.get("snippet") or ""
            )[:500]
        visible.append(item)
    return {
        "timezone": str(app_timezone()),
        "time_from": time_from.isoformat(),
        "time_to": time_to.isoformat(),
        "eligible_count": len(visible),
        "messages": visible,
    }


async def run(user_id: str, *, query: str, include_text: bool) -> dict[str, Any]:
    current = now()
    time_from, time_to = today_window(current)
    with Session(engine) as db:
        messages = await search_gmail_messages(db, user_id, time_from, time_to, query=query)
    return format_output(messages, time_from, time_to, include_text=include_text)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Xem email hôm nay sau Gmail agent filter")
    parser.add_argument("--user-id", required=True, help="ID user đã xác thực, không phải email")
    parser.add_argument("--query", default="", help="Từ khoá hoặc Gmail search syntax (tuỳ chọn)")
    parser.add_argument("--include-text", action="store_true", help="In tối đa 500 ký tự nội dung mỗi email")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(
        asyncio.run(run(args.user_id, query=args.query, include_text=args.include_text)),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
