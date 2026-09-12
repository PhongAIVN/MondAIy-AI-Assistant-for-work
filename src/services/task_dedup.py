"""Khử trùng task do agent tạo, theo thứ tự rẻ trước và fail-open."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.agents.pipeline.nodes.cluster import _normalize_title, _titles_match
from src.config import get_settings
from src.models.task import Task

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("proposed", "confirmed")


@dataclass(frozen=True)
class TaskDedupDecision:
    task: Task | None = None
    layer: str | None = None
    similarity_score: float | None = None
    degraded_reason: str | None = None


def acquire_user_lock(db: Session, user_id: str) -> None:
    """Tuần tự hoá create/match theo user trên Postgres để chặn race insert."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    lock_key = int.from_bytes(hashlib.sha256(user_id.encode()).digest()[:8], "big", signed=True)
    db.execute(select(func.pg_advisory_xact_lock(lock_key)))


def candidate_fingerprint(title: str, detail: str, due_at: datetime) -> str:
    """Định danh audit không chứa nội dung gốc của task đến."""
    raw = f"{_normalize_title(title)}\n{detail.strip()}\n{due_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _due_distance_seconds(left: datetime | None, right: datetime | None) -> float | None:
    if left is None or right is None:
        return None
    if left.tzinfo is None or right.tzinfo is None:
        # SQLite làm rơi tzinfo nhưng giữ nguyên giờ trên mặt đồng hồ đã ghi.
        # So wall time trong test; Postgres đi nhánh aware và chuẩn hoá UTC.
        return abs((left.replace(tzinfo=None) - right.replace(tzinfo=None)).total_seconds())
    return abs((left - right).total_seconds())


def _title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize_title(left), _normalize_title(right)).ratio()


def _details_conflict(left: str, right: str) -> bool:
    left_normalized = _normalize_title(left)
    right_normalized = _normalize_title(right)
    if not left_normalized or not right_normalized:
        return False
    return SequenceMatcher(None, left_normalized, right_normalized).ratio() < 0.95


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("embedding vector has zero norm")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def _embed_task_titles(titles: list[str]) -> list[list[float]]:
    settings = get_settings()
    client = OpenAIEmbeddings(
        model=settings.task_dedup_embedding_model,
        api_key=settings.openai_api_key,
        timeout=settings.task_dedup_embedding_timeout_seconds,
        max_retries=0,
    )
    return client.embed_documents(titles)


def find_duplicate_task(
    db: Session,
    *,
    user_id: str,
    title: str,
    detail: str,
    due_at: datetime | None,
    all_day: bool,
) -> TaskDedupDecision:
    """Tìm task active cùng hạn theo exact → fuzzy dùng chung → semantic."""
    if due_at is None:
        return TaskDedupDecision()

    settings = get_settings()
    proximity = timedelta(hours=settings.task_dedup_due_proximity_hours)
    exact_raw = db.scalar(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status.in_(_ACTIVE_STATUSES),
            Task.due_at.is_not(None),
            Task.due_at >= due_at - proximity,
            Task.due_at <= due_at + proximity,
            Task.title == title.strip(),
            Task.all_day == bool(all_day),
        )
        .order_by(Task.id.desc())
        .limit(1)
    )
    if (
        exact_raw is not None
        and not _details_conflict(detail, exact_raw.detail)
        and (raw_distance := _due_distance_seconds(due_at, exact_raw.due_at)) is not None
        and raw_distance < proximity.total_seconds()
    ):
        return TaskDedupDecision(task=exact_raw, layer="exact", similarity_score=1.0)

    candidates = list(
        db.scalars(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status.in_(_ACTIVE_STATUSES),
                Task.due_at.is_not(None),
                Task.due_at >= due_at - proximity,
                Task.due_at <= due_at + proximity,
                Task.all_day == bool(all_day),
            )
            .order_by(Task.updated_at.desc(), Task.id.desc())
            .limit(settings.task_dedup_candidate_limit)
        ).all()
    )
    candidates = [
        row
        for row in candidates
        if (distance := _due_distance_seconds(due_at, row.due_at)) is not None
        and distance < proximity.total_seconds()
        and not _details_conflict(detail, row.detail)
    ]
    if not candidates:
        return TaskDedupDecision()

    normalized = _normalize_title(title)
    exact = next((row for row in candidates if _normalize_title(row.title) == normalized), None)
    if exact is not None:
        return TaskDedupDecision(task=exact, layer="exact", similarity_score=1.0)

    fuzzy_matches = [
        row
        for row in candidates
        if _titles_match(row.title, title)
        and _title_similarity(row.title, title) >= settings.task_dedup_fuzzy_threshold
    ]
    if fuzzy_matches:
        matched = max(fuzzy_matches, key=lambda row: _title_similarity(row.title, title))
        return TaskDedupDecision(
            task=matched,
            layer="fuzzy",
            similarity_score=_title_similarity(matched.title, title),
        )

    if not settings.task_dedup_semantic_enabled:
        return TaskDedupDecision(degraded_reason="semantic_disabled")
    if not settings.openai_api_key:
        return TaskDedupDecision(degraded_reason="missing_openai_api_key")

    try:
        vectors = _embed_task_titles([title, *(row.title for row in candidates)])
        if len(vectors) != len(candidates) + 1:
            raise ValueError("embedding response count does not match request")
        scored = [
            (row, _cosine_similarity(vectors[0], vector))
            for row, vector in zip(candidates, vectors[1:], strict=True)
        ]
    except Exception as exc:
        logger.warning("Task semantic dedup hạ cấp: error_type=%s", type(exc).__name__)
        return TaskDedupDecision(degraded_reason=f"embedding_error:{type(exc).__name__}")

    matched, score = max(scored, key=lambda item: item[1])
    if score < settings.task_dedup_semantic_threshold:
        return TaskDedupDecision()
    return TaskDedupDecision(task=matched, layer="semantic", similarity_score=score)
