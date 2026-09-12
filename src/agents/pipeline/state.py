from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TypedDict

from sqlalchemy.orm import Session


class SourceRef(TypedDict):
    connection_id: int
    source_id: str


class PipelineState(TypedDict, total=False):
    """State cho pipeline task-extraction (TAPB-121) — 9 node tuần tự.

    `db` đi kèm trong state vì graph chạy trong tiến trình, không cần
    serialize; mỗi node dùng cùng 1 Session cho toàn bộ lần sync.
    """

    db: Session
    run_id: int
    user_id: str
    sources: list[SourceRef]
    time_from: datetime
    time_to: datetime
    timezone: str
    # "vi" | "en" — ngôn ngữ title/summary/detail LLM viết ra cho run này.
    # evidence_quote/time_expression không bị ảnh hưởng, luôn giữ ngôn ngữ
    # gốc của nguồn (xem extract_batch.py/reduce.py).
    language: str
    user_email: str
    trusted_senders: list[str]
    trusted_sender_domains: list[str]
    program_domains: list[str]
    # summary bypasses task extraction; task_extraction runs the full graph.
    mode: str
    # Gọi từ fetch_node mỗi khi 1 item tải xong — báo tiến trình qua SSE
    # ngay trong lúc node fetch còn chạy, không đợi LangGraph node return
    # (stream_mode="updates" chỉ emit khi node xong). Không serialize được
    # nên chỉ dùng được vì graph chạy trong 1 tiến trình, không có checkpointer.
    publish_progress: Callable[[str, int, str], None]

    raw_messages: list[dict]
    normalized: list[dict]
    filtered: list[dict]
    batches: list[list[dict]]
    extracted: list[dict]
    resolved: list[dict]
    clusters: list[dict]
    tasks_persisted: list[dict]
    # id các task đề xuất bị thu hồi vì nguồn nay đã bị lọc (persist.py).
    tasks_retracted: list[int]
    summary_items: list[dict]
    errors: list[str]
    filter_rejected: list[dict]
    filter_stats: dict
    verification_stats: dict
