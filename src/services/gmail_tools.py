"""Bounded, read-only Gmail access used by the in-app agent tools."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.connectors.base import Source
from src.connectors.gmail import GmailConnector
from src.models.connection import Connection
from src.models.message import Message
from src.services.connections import preferred_connection
from src.services.filter_classify import FilterConfig, filter_and_classify
from src.services.gmail_recall import GmailSweep, GmailSweepFamily, GmailSweepReceipt, build_gmail_sweep_plan

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 12
# Fetch a bounded candidate pool first.  Filtering after Gmail's previous
# 12-result limit meant newsletters could crowd actionable mail out before the
# deterministic classifier had a chance to rank it.
MAX_FILTER_CANDIDATES = 50
MAX_FULL_FETCH_PER_SWEEP = 16
GMAIL_SWEEP_CONCURRENCY = 3


def _cache_query_terms(query: str) -> list[str]:
    """Extract plain terms from a bounded Gmail query for local-index lookup."""
    # Gmail operator groups ({to:me ...}) describe mailbox metadata that the
    # normalized offline Message row does not retain. Treat them as broad
    # recall locally; the same deterministic classifier is applied afterward.
    if "{" in query or "}" in query:
        return []
    return [
        term.casefold()
        for term in re.findall(r"[\w@.-]{3,}", query, flags=re.UNICODE)
        if ":" not in term and term not in {"after", "before", "from", "to", "cc", "subject", "is"}
    ]


def _cached_gmail_messages(
    db: Session,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
    query: str,
    max_results: int,
) -> tuple[bool, list[dict]]:
    """Read the persisted Gmail index; bool says whether the window is indexed."""
    try:
        rows = db.scalars(
            select(Message)
            .where(
                Message.user_id == str(user_id),
                Message.provider == "google",
                Message.sent_at >= time_from,
                Message.sent_at < time_to,
            )
            .order_by(Message.sent_at.desc())
            .limit(MAX_FILTER_CANDIDATES)
        ).all()
    except Exception:
        # Log để phân biệt lỗi DB thật (connection chết, cột đổi tên) khỏi
        # "cache rỗng chưa index" — cả 2 trước đây đều im lặng trả về giống
        # hệt nhau, không cách nào debug được cái nào đang xảy ra.
        logger.exception("Đọc Gmail index từ DB thất bại — coi như chưa index, fallback fetch trực tiếp")
        return False, []
    if not rows:
        return False, []
    terms = _cache_query_terms(query)
    items = []
    for row in rows:
        haystack = f"{row.author_id or ''} {row.author_name or ''} {row.subject or ''} {row.text or ''}".casefold()
        if terms and not any(term in haystack for term in terms):
            continue
        items.append(
            {
                "id": row.external_id,
                "source_id": row.source_id,
                "provider": row.provider,
                "thread_id": row.thread_id,
                "author_id": row.author_id,
                "author_name": row.author_name,
                "is_self": row.is_self,
                "is_dm": row.is_dm,
                # Metadata hộp thư dựng lại đầy đủ: nếu thiếu, filter_classify
                # coi mail là "không có dữ liệu người nhận" và bỏ qua luôn
                # bước lọc mail-không-gửi-cho-mình.
                "subject": row.subject or "",
                "snippet": row.snippet or "",
                "to": list(row.to_addresses or []),
                "cc": list(row.cc_addresses or []),
                "mailbox_email": row.mailbox_email,
                "is_unread": bool(row.is_unread),
                "has_marketing_boilerplate": bool(row.has_marketing_boilerplate),
                "text": row.text,
                "normalized_text": row.text,
                "sent_at": row.sent_at,
                "deep_link": row.deep_link,
                "capture_mode": "offline_index",
            }
        )
    return True, items[:max_results]


def _connection_for_user(db: Session, user_id: str) -> Connection:
    connection = preferred_connection(db, user_id, "google")
    if connection is None:
        raise ValueError("Chưa có kết nối Gmail đang hoạt động cho người dùng này.")
    return connection


async def search_gmail_messages(
    db: Session,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
    query: str = "",
    max_results: int = MAX_SEARCH_RESULTS,
) -> list[dict]:
    """Return only useful mail from one user's mailbox in a bounded window.

    Gmail's ``after``/``before`` operators make the time boundary enforceable at
    the provider. A deterministic classifier then removes newsletter,
    transactional and low-signal messages before any agent tool sees them.
    """
    indexed, cached = _cached_gmail_messages(db, user_id, time_from, time_to, query, max_results)
    if indexed:
        window_days = max(14, (time_to - time_from).days + 1)
        # user_email lấy từ chính hàng cache (mailbox_email đã stamp lúc ingest)
        # để đường này không phải mở connection, nhưng vẫn chấm điểm recipient
        # và lọc not_addressed giống hệt đường gọi API bên dưới.
        mailbox_email = next((item.get("mailbox_email") for item in cached if item.get("mailbox_email")), None)
        filtered = filter_and_classify(
            cached,
            FilterConfig(user_email=mailbox_email, lookback_days=window_days),
            now=time_to,
        )
        return sorted(
            filtered["items"],
            key=lambda item: (item.get("importance_score", 0), item.get("sent_at") or datetime.min.replace(tzinfo=UTC)),
            reverse=True,
        )[: max(1, min(max_results, MAX_SEARCH_RESULTS))]

    connection = _connection_for_user(db, user_id)
    connector = GmailConnector(connection, db)
    result_limit = min(max(1, max_results), MAX_SEARCH_RESULTS)
    gmail_query = " ".join(
        part
        for part in (
            query.strip(),
            f"after:{int(time_from.timestamp())}",
            f"before:{int(time_to.timestamp())}",
        )
        if part
    )

    token = await connector._access_token()
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
        page = await connector._get(
            client,
            "/messages",
            params={"q": gmail_query, "maxResults": MAX_FILTER_CANDIDATES},
        )
        messages: list[dict] = []
        # Gmail metadata is cheap; full MIME bodies are not. Fetch a small
        # ranked slice for the interactive path while keeping the broad ID
        # pool for recall. A later exact read can still fetch any selected ID.
        fetch_limit = min(MAX_FILTER_CANDIDATES, max(12, result_limit * 2))
        for item in page.get("messages", [])[:fetch_limit]:
            raw = await connector._get(client, f"/messages/{item['id']}", params={"format": "full"})
            messages.append(connector.normalize(raw, Source(id="INBOX", name="INBOX")))

    window_days = max(14, (time_to - time_from).days + 1)
    filtered = filter_and_classify(
        messages,
        FilterConfig(user_email=connection.provider_user_id, lookback_days=window_days),
        # The provider has already enforced ``time_to``. Using it as the filter
        # reference keeps explicit historical searches from being rejected as
        # stale relative to wall-clock time.
        now=time_to,
    )
    ranked = sorted(
        filtered["items"],
        key=lambda item: (
            item.get("importance_score", 0),
            item.get("sent_at") or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return ranked[:result_limit]


async def read_gmail_message(db: Session, user_id: str, message_id: str) -> dict:
    """Read one exact message from the scoped user's mailbox."""
    connection = _connection_for_user(db, user_id)
    connector = GmailConnector(connection, db)
    token = await connector._access_token()
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=20) as client:
        raw = await connector._get(client, f"/messages/{message_id}", params={"format": "full"})
    return connector.normalize(raw, Source(id="INBOX", name="INBOX"))


async def search_gmail_deadline_candidates(
    db: Session,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
    query: str = "",
) -> tuple[list[dict], list[GmailSweepReceipt]]:
    """Run bounded Gmail recall families and return clues plus coverage receipts.

    Results are routing clues only.  The caller must read an exact message or
    thread before turning a clue into a verified work item.
    """
    candidates: dict[str, dict] = {}
    receipts: list[GmailSweepReceipt] = []
    plan = build_gmail_sweep_plan(time_from, time_to)
    if query.strip():
        base = plan[0]
        plan.append(GmailSweep(GmailSweepFamily.TARGETED, query.strip(), base.time_from, base.time_to))
    semaphore = asyncio.Semaphore(GMAIL_SWEEP_CONCURRENCY)

    async def run_sweep(sweep: GmailSweep) -> tuple[GmailSweep, list[dict] | None, Exception | None]:
        async with semaphore:
            try:
                found = await search_gmail_messages(
                    db, user_id, sweep.time_from, sweep.time_to,
                    query=sweep.query, max_results=8,
                )
                return sweep, found, None
            except Exception as exc:  # retain partial coverage instead of claiming no work
                return sweep, None, exc

    sweep_results = await asyncio.gather(*(run_sweep(sweep) for sweep in plan))
    for sweep, found, error in sweep_results:
        if error is not None:
            receipts.append(GmailSweepReceipt(
                sweep.family, sweep.time_from, sweep.time_to,
                status="partial", error=str(error)[:240],
            ))
            continue
        for message in found:
            candidates.setdefault(str(message.get("id")), message)
        receipts.append(GmailSweepReceipt(
            sweep.family, sweep.time_from, sweep.time_to,
            message_count=len(found),
        ))
    return list(candidates.values()), receipts
