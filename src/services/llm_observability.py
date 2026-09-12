"""Thu usage LLM mà không đưa định danh thật hoặc nội dung vào metric."""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_settings
from src.db import SessionLocal
from src.models.llm_usage import LLMUsageEvent
from src.observability import (
    LLM_CALL_DURATION,
    LLM_CALLS,
    LLM_ESTIMATED_COST,
    LLM_PRICING_UNKNOWN,
    LLM_TOKENS,
    LLM_USAGE_MISSING,
    LLM_USER_ATTRIBUTION_MISSING,
    LLM_USER_ESTIMATED_COST,
    LLM_USER_TOKENS,
    pseudonymous_llm_user_hash,
)
from src.services.llm_usage_scope import current_llm_usage_user as current_agent_user_id

logger = logging.getLogger(__name__)


def _usage_from(response: LLMResult) -> tuple[int, int] | None:
    """Ưu tiên usage_metadata trên AIMessage, rồi mới đọc token_usage chuẩn cũ."""
    totals = [0, 0]
    found = False
    for generation_group in response.generations:
        for generation in generation_group:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if not isinstance(usage, dict):
                continue
            if "input_tokens" not in usage or "output_tokens" not in usage:
                continue
            totals[0] += int(usage["input_tokens"])
            totals[1] += int(usage["output_tokens"])
            found = True
    if found:
        return totals[0], totals[1]

    token_usage = (response.llm_output or {}).get("token_usage")
    if not isinstance(token_usage, dict):
        return None
    if "prompt_tokens" not in token_usage or "completion_tokens" not in token_usage:
        return None
    return int(token_usage["prompt_tokens"]), int(token_usage["completion_tokens"])


def _configured_price(model: str) -> tuple[float, float] | None:
    price = get_settings().llm_model_pricing_usd_per_million.get(model)
    if not isinstance(price, dict) or "input" not in price or "output" not in price:
        return None
    return float(price["input"]), float(price["output"])


def _persist_usage(
    *,
    model: str,
    lane: str,
    duration_seconds: float,
    status: str,
    user_id: str | None,
    usage: tuple[int, int] | None = None,
    cost: float | None = None,
    price_available: bool = False,
) -> None:
    event = LLMUsageEvent(
        user_id=user_id,
        model=model,
        lane=lane,
        input_tokens=usage[0] if usage is not None else None,
        output_tokens=usage[1] if usage is not None else None,
        estimated_cost_usd=cost,
        duration_ms=max(0, round(duration_seconds * 1000)),
        status=status,
        usage_available=usage is not None,
        price_available=price_available,
    )
    try:
        with SessionLocal() as db:
            db.add(event)
            db.commit()
    except SQLAlchemyError:
        # Observability không được làm hỏng câu trả lời, nhưng lỗi ghi ledger
        # phải hiện trong log để không biến mất như một sample "0 token" giả.
        logger.exception("Không ghi được LLM usage ledger model=%s lane=%s", model, lane)


def _record_success(
    *,
    model: str,
    lane: str,
    duration_seconds: float,
    usage: tuple[int, int] | None,
    user_id: str | None,
) -> None:
    LLM_CALL_DURATION.labels(model, lane).observe(duration_seconds)
    LLM_CALLS.labels(model, lane, "success").inc()
    if usage is None:
        LLM_USAGE_MISSING.labels(model, lane).inc()
        logger.warning("LLM response lacks usage_metadata model=%s lane=%s", model, lane)
        _persist_usage(
            model=model,
            lane=lane,
            duration_seconds=duration_seconds,
            status="success",
            user_id=user_id,
        )
        return

    input_tokens, output_tokens = usage
    LLM_TOKENS.labels(model, lane, "input").inc(input_tokens)
    LLM_TOKENS.labels(model, lane, "output").inc(output_tokens)
    price = _configured_price(model)
    cost: float | None = None
    if price is None:
        LLM_PRICING_UNKNOWN.labels(model, lane).inc()
        logger.warning("LLM price is not configured model=%s lane=%s", model, lane)
    else:
        cost = (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
        LLM_ESTIMATED_COST.labels(model, lane).inc(cost)
    _record_user_usage(user_id=user_id, usage=usage, cost=cost)
    _persist_usage(
        model=model,
        lane=lane,
        duration_seconds=duration_seconds,
        status="success",
        user_id=user_id,
        usage=usage,
        cost=cost,
        price_available=price is not None,
    )


def _record_user_usage(
    *, user_id: str | None, usage: tuple[int, int], cost: float | None
) -> None:
    """Chỉ xuất usage theo user khi có scope và secret để tạo HMAC."""
    if user_id is None:
        LLM_USER_ATTRIBUTION_MISSING.labels("no_user_scope").inc()
        return
    secret = get_settings().app_secret_key
    if not secret:
        LLM_USER_ATTRIBUTION_MISSING.labels("hash_secret_missing").inc()
        return
    digest = pseudonymous_llm_user_hash(user_id, secret)
    LLM_USER_TOKENS.labels(digest, "input").inc(usage[0])
    LLM_USER_TOKENS.labels(digest, "output").inc(usage[1])
    if cost is not None:
        LLM_USER_ESTIMATED_COST.labels(digest).inc(cost)


class LLMObservabilityCallback(BaseCallbackHandler):
    """Đo tại callback raw model nên structured-output parser không làm mất usage."""

    def __init__(self, model: str, lane: str) -> None:
        self._model = model
        self._lane = lane
        self._started: dict[UUID, tuple[float, str | None]] = {}
        self._lock = Lock()

    def _start(self, run_id: UUID) -> None:
        with self._lock:
            self._started[run_id] = (time.perf_counter(), current_agent_user_id())

    def on_chat_model_start(self, _serialized: dict[str, Any], _messages: list, *, run_id: UUID, **_kwargs: Any) -> None:
        self._start(run_id)

    def on_llm_start(self, _serialized: dict[str, Any], _prompts: list[str], *, run_id: UUID, **_kwargs: Any) -> None:
        self._start(run_id)

    def _pop_start(self, run_id: UUID) -> tuple[float, str | None]:
        with self._lock:
            started = self._started.pop(run_id, None)
        if started is not None:
            return started
        return time.perf_counter(), current_agent_user_id()

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **_kwargs: Any) -> None:
        started, user_id = self._pop_start(run_id)
        try:
            usage = _usage_from(response)
        except (TypeError, ValueError, OverflowError):
            usage = None
            logger.warning("LLM response has invalid usage_metadata model=%s lane=%s", self._model, self._lane)
        _record_success(
            model=self._model,
            lane=self._lane,
            duration_seconds=time.perf_counter() - started,
            usage=usage,
            user_id=user_id,
        )

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **_kwargs: Any) -> None:
        started, user_id = self._pop_start(run_id)
        status = "timeout" if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.casefold() else "error"
        duration = time.perf_counter() - started
        LLM_CALL_DURATION.labels(self._model, self._lane).observe(duration)
        LLM_CALLS.labels(self._model, self._lane, status).inc()
        _persist_usage(
            model=self._model,
            lane=self._lane,
            duration_seconds=duration,
            status=status,
            user_id=user_id,
        )


def llm_callbacks(model: str, lane: str | None) -> list[BaseCallbackHandler]:
    """Callback list dùng chung cho mọi ChatOpenAI client trong repo."""
    return [LLMObservabilityCallback(model, lane or "unclassified")]


def record_llm_without_usage_metadata(
    *, model: str, lane: str, duration_seconds: float, error: BaseException | None = None
) -> None:
    """Ghi provider không expose LangChain usage; tuyệt đối không đoán token."""
    status = "success"
    if error is not None:
        status = "timeout" if isinstance(error, TimeoutError) or "timeout" in type(error).__name__.casefold() else "error"
    LLM_CALL_DURATION.labels(model, lane).observe(duration_seconds)
    LLM_CALLS.labels(model, lane, status).inc()
    if error is None:
        LLM_USAGE_MISSING.labels(model, lane).inc()
    _persist_usage(
        model=model,
        lane=lane,
        duration_seconds=duration_seconds,
        status=status,
        user_id=current_agent_user_id(),
    )
