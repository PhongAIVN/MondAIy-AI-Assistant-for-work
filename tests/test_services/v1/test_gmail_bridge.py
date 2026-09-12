from datetime import UTC, datetime

from src.services.gmail_bridge import build_bridge_queries, normalize_thread


def test_deadline_month_builds_sent_and_historical_content_queries():
    queries = build_bridge_queries(
        "deadline tháng 8",
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert len(queries) >= 2
    assert any("after:2026/08/01" in query and "before:2026/09/01" in query for query in queries)
    assert any("after:2026/02/02" in query and "tháng 8" in query for query in queries)
    assert any("deadline" in query and "due" in query for query in queries)


def test_bridge_summary_keeps_thread_provenance_and_flags():
    thread = normalize_thread(
        {
            "id": "thread-1",
            "subject": "August deadline",
            "lastMessageDate": "2026-05-20T10:00:00Z",
            "messageCount": 3,
            "isUnread": True,
            "permalink": "https://mail.google.com/thread-1",
        },
        "{deadline due} after:2026/02/02 before:2026/09/02",
    )
    assert thread["source"] == "anythingllm_gmail_bridge"
    assert thread["is_unread"] is True
    assert thread["query"].startswith("{deadline")
