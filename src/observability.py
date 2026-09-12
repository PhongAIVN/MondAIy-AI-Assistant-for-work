"""Low-cardinality operational metrics for the P-004 API."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
from collections.abc import Collection, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import get_args

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select
from starlette.responses import Response

from src.config import get_settings
from src.db import SessionLocal

logger = logging.getLogger(__name__)


class _RatingScalarCollector:
    """Xuất snapshot scalar rating; `None` nghĩa là không có sample."""

    _SPECS = (
        ("p004_product_rating_avg", "Average P-004 app rating"),
        ("p004_product_rating_avg_30d", "Average P-004 app rating in the last 30 days"),
        (
            "p004_product_rating_last_timestamp_seconds",
            "Unix timestamp of the latest P-004 app rating",
        ),
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._values: tuple[float | None, float | None, float | None] = (None, None, None)

    def replace(
        self,
        average: float | None,
        average_30d: float | None,
        last_timestamp: float | None,
    ) -> None:
        with self._lock:
            self._values = (average, average_30d, last_timestamp)

    def collect(self) -> Iterable[GaugeMetricFamily]:
        with self._lock:
            values = self._values
        for (name, documentation), value in zip(self._SPECS, values, strict=True):
            if value is None:
                continue
            metric = GaugeMetricFamily(name, documentation)
            metric.add_metric([], value)
            yield metric


_RATING_SCALARS = _RatingScalarCollector()
REGISTRY.register(_RATING_SCALARS)

REQUESTS = Counter(
    "p004_http_requests_total",
    "HTTP requests handled by the P-004 API",
    ("method", "route_group", "status"),
)
LATENCY = Histogram(
    "p004_http_request_duration_seconds",
    "HTTP request duration by low-cardinality route group",
    ("method", "route_group"),
)
PRODUCT_USERS = Gauge("p004_product_users_total", "Total registered P-004 users")
PRODUCT_ACTIVE_USERS = Gauge("p004_product_active_users_7d", "Users with product activity in the last 7 days")
PRODUCT_CONNECTIONS = Gauge("p004_product_connections_total", "P-004 source connections", ("provider", "status"))
PRODUCT_RUNS = Gauge("p004_product_runs_total", "P-004 pipeline runs", ("status",))
PRODUCT_BRIEFS = Gauge("p004_product_briefs_total", "Generated P-004 briefs")
PRODUCT_TASKS = Gauge("p004_product_tasks_total", "P-004 tasks", ("status",))
PRODUCT_TELEMETRY = Gauge(
    "p004_product_telemetry_events_total",
    "Allowlisted product telemetry events",
    ("name", "surface"),
)
PRODUCT_TELEMETRY_AVG_DURATION = Gauge(
    "p004_product_telemetry_avg_duration_ms", "Average duration of product telemetry events", ("name",)
)
PRODUCT_RATING_COUNT = Gauge("p004_product_rating_count", "P-004 app ratings by star value", ("rating",))
PRODUCT_RATINGS_BY_TRIGGER = Gauge(
    "p004_product_ratings_by_trigger", "P-004 app ratings by allowlisted trigger", ("trigger",)
)
LLM_TOKENS = Gauge(
    "p004_llm_tokens_total",
    "LLM tokens reported by the provider",
    ("model", "lane", "direction"),
)
LLM_ESTIMATED_COST = Gauge(
    "p004_llm_estimated_cost_usd_total",
    "Estimated LLM cost in USD from the configured price table",
    ("model", "lane"),
)
LLM_CALL_DURATION = Histogram(
    "p004_llm_call_duration_seconds",
    "End-to-end LLM call duration",
    ("model", "lane"),
)
LLM_CALLS = Gauge(
    "p004_llm_calls_total",
    "LLM calls by terminal status",
    ("model", "lane", "status"),
)
LLM_USAGE_MISSING = Gauge(
    "p004_llm_usage_metadata_missing_total",
    "Successful LLM calls without provider usage metadata",
    ("model", "lane"),
)
LLM_PRICING_UNKNOWN = Gauge(
    "p004_llm_pricing_unknown_total",
    "LLM calls with token usage but no configured model price",
    ("model", "lane"),
)
LLM_USER_TOKENS = Gauge(
    "p004_llm_user_tokens_total",
    "LLM tokens attributed to an internal pseudonymous user",
    ("user_hash", "direction"),
)
LLM_USER_ESTIMATED_COST = Gauge(
    "p004_llm_user_estimated_cost_usd_total",
    "Estimated LLM cost attributed to an internal pseudonymous user",
    ("user_hash",),
)
LLM_USER_ATTRIBUTION_MISSING = Gauge(
    "p004_llm_user_attribution_missing_total",
    "LLM calls that could not be attributed to a pseudonymous user",
    ("reason",),
)
LLM_PERSISTED_AVG_DURATION = Gauge(
    "p004_llm_persisted_avg_duration_seconds",
    "Average LLM call duration across API and worker processes",
    ("model", "lane"),
)
AGENT_TURNS = Counter(
    "p004_agent_turns_total",
    "Completed agent turns by guardrail outcome",
    ("guardrail_blocked",),
)
AGENT_GUARDRAIL_BLOCKS = Counter(
    "p004_agent_guardrail_blocked_turns_total",
    "Agent turns blocked by an allowlisted guardrail reason",
    ("stage", "reason"),
)
AGENT_GROUNDING = Counter(
    "p004_agent_grounding_results_total",
    "Measured final grounding outcomes",
    ("status",),
)
AGENT_TOOL_ITERATIONS = Histogram(
    "p004_agent_tool_iterations",
    "Tool-loop iterations completed per agent turn",
    buckets=(0, 1, 2, 3, 4),
)
AGENT_INTENT_BACKEND = Counter(
    "p004_agent_intent_backend_total",
    "Agent turns by allowlisted intent-classification backend",
    ("backend",),
)
AGENT_TOOL_CALLS = Counter(
    "p004_agent_tool_calls_total",
    "Agent tool observations by allowlisted tool and terminal outcome",
    ("tool", "outcome"),
)

_GUARDRAIL_REASONS = frozenset(
    {"prompt_injection", "secret_request", "abusive_generation_request", "tool_policy"}
)
_GROUNDING_STATUSES = frozenset({"grounded", "uncertain", "abstain", "reject"})
_INTENT_BACKENDS = frozenset(
    {"exact_guardrail", "llm_structured_output", "shared_rag_embedding", "shared_rag_embedding_unavailable"}
)
_TOOL_OUTCOMES = frozenset({"ok", "empty", "not_connected", "error", "blocked"})
_RATING_VALUES = frozenset(range(1, 6))
_COVERAGE_COMPONENTS = frozenset({"backend", "agent"})
_COVERAGE_SUMMARY_PATH = Path(__file__).resolve().parents[1] / "observability" / "coverage-summary.json"


def pseudonymous_llm_user_hash(user_id: str, secret: str) -> str:
    """Tạo mã user ổn định cho metric mà không xuất định danh nội bộ."""
    return hmac.new(
        secret.encode("utf-8"),
        f"p004-llm-usage-v1:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]


def record_agent_outcome(
    metadata: dict,
    tool_iterations: int,
    tool_outcomes: Iterable[tuple[str, str]],
    allowed_tools: Collection[str],
) -> None:
    """Đo một lần ở node cuối graph; mọi label động đều qua allowlist."""
    guardrail = metadata.get("guardrail")
    guardrail = guardrail if isinstance(guardrail, dict) else {}
    blocked: set[tuple[str, str]] = set()
    if guardrail.get("decision") == "block":
        blocked.add(("input", str(guardrail.get("reason") or "")))
    for decision in guardrail.get("tool_decisions") or []:
        if isinstance(decision, dict) and decision.get("decision") == "block":
            blocked.add(("tool", str(decision.get("reason") or "")))

    AGENT_TURNS.labels("true" if blocked else "false").inc()
    for stage, reason in blocked:
        if reason in _GUARDRAIL_REASONS:
            AGENT_GUARDRAIL_BLOCKS.labels(stage, reason).inc()
        else:
            logger.warning("Bỏ metric guardrail reason ngoài allowlist: %s", reason)

    grounding_status = metadata.get("grounding_status")
    if grounding_status in _GROUNDING_STATUSES:
        AGENT_GROUNDING.labels(str(grounding_status)).inc()
    elif grounding_status is not None:
        logger.warning("Bỏ metric grounding status ngoài allowlist: %s", grounding_status)

    if isinstance(tool_iterations, int) and 0 <= tool_iterations <= 4:
        AGENT_TOOL_ITERATIONS.observe(tool_iterations)
    else:
        logger.warning("Bỏ metric tool_iterations không hợp lệ: %r", tool_iterations)

    intent_trace = metadata.get("intent_trace")
    backend = intent_trace.get("backend") if isinstance(intent_trace, dict) else None
    if backend in _INTENT_BACKENDS:
        AGENT_INTENT_BACKEND.labels(str(backend)).inc()
    elif backend is not None:
        logger.warning("Bỏ metric intent backend ngoài allowlist: %s", backend)

    for tool, outcome in tool_outcomes:
        if tool not in allowed_tools:
            logger.warning("Bỏ metric tool ngoài allowlist: %s", tool)
            continue
        if outcome not in _TOOL_OUTCOMES:
            logger.warning("Bỏ metric tool outcome ngoài allowlist: %s", outcome)
            continue
        AGENT_TOOL_CALLS.labels(tool, outcome).inc()


def _rating_trigger_allowlist() -> frozenset[str]:
    """Dẫn xuất label từ contract request thay vì chép lại Literal trigger."""
    from src.api.ratings import RatingCreateRequest

    annotation = RatingCreateRequest.model_fields["trigger"].annotation
    return frozenset(value for value in get_args(annotation) if isinstance(value, str))


def _collect_rating_metrics(db, rating_model, *, now: datetime | None = None) -> None:
    """Phản chiếu aggregate rating; không đọc feedback hoặc user_id."""
    PRODUCT_RATING_COUNT.clear()
    PRODUCT_RATINGS_BY_TRIGGER.clear()
    now = now or datetime.now(UTC)
    valid_ratings = tuple(sorted(_RATING_VALUES))

    invalid_ratings = db.scalar(
        select(func.count(rating_model.id)).where(rating_model.rating.not_in(valid_ratings))
    )
    if invalid_ratings:
        logger.warning("Bỏ %s rating ngoài allowlist 1..5", invalid_ratings)

    for rating, count in db.execute(
        select(rating_model.rating, func.count(rating_model.id))
        .where(rating_model.rating.in_(valid_ratings))
        .group_by(rating_model.rating)
    ).all():
        PRODUCT_RATING_COUNT.labels(str(rating)).set(count)

    valid_rows = rating_model.rating.in_(valid_ratings)
    average = db.scalar(select(func.avg(rating_model.rating)).where(valid_rows))
    average_30d = db.scalar(
        select(func.avg(rating_model.rating)).where(
            valid_rows,
            rating_model.created_at >= now - timedelta(days=30),
        )
    )
    allowed_triggers = _rating_trigger_allowlist()
    for trigger, count in db.execute(
        select(rating_model.trigger, func.count(rating_model.id))
        .where(valid_rows)
        .group_by(rating_model.trigger)
    ).all():
        trigger = str(trigger)
        if trigger not in allowed_triggers:
            logger.warning("Bỏ metric rating trigger ngoài allowlist: %s", trigger)
            continue
        PRODUCT_RATINGS_BY_TRIGGER.labels(trigger).set(count)

    latest = db.scalar(select(func.max(rating_model.created_at)).where(valid_rows))
    if latest is not None and latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    _RATING_SCALARS.replace(
        float(average) if average is not None else None,
        float(average_30d) if average_30d is not None else None,
        latest.timestamp() if latest is not None else None,
    )


def _coverage_metric_families() -> Iterable[GaugeMetricFamily]:
    try:
        payload = json.loads(_COVERAGE_SUMMARY_PATH.read_text(encoding="utf-8"))
        generated_at = payload["generated_at"]
        components = payload["components"]
        if isinstance(generated_at, bool) or not isinstance(generated_at, int | float):
            raise ValueError("generated_at phải là unix timestamp")
        if not math.isfinite(float(generated_at)) or float(generated_at) <= 0:
            raise ValueError("generated_at phải hữu hạn và dương")
        if not isinstance(components, dict):
            raise ValueError("components phải là object")
        missing_components = _COVERAGE_COMPONENTS.difference(components)
        if missing_components:
            raise ValueError(f"thiếu coverage component: {', '.join(sorted(missing_components))}")

        values: list[tuple[str, float]] = []
        for component, raw_value in components.items():
            if component not in _COVERAGE_COMPONENTS:
                logger.warning("Bỏ metric coverage component ngoài allowlist: %s", component)
                continue
            if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
                raise ValueError(f"coverage {component} phải là số")
            value = float(raw_value)
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError(f"coverage {component} phải trong khoảng 0..100")
            values.append((component, value))
        if not values:
            raise ValueError("không có coverage component hợp lệ")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Không đọc được coverage summary %s: %s", _COVERAGE_SUMMARY_PATH, exc)
        return

    coverage = GaugeMetricFamily(
        "p004_test_coverage_percent", "Committed test coverage by allowlisted component", labels=["component"]
    )
    for component, value in values:
        coverage.add_metric([component], value)
    updated = GaugeMetricFamily(
        "p004_test_coverage_updated_timestamp_seconds", "Unix timestamp when committed coverage was generated"
    )
    updated.add_metric([], float(generated_at))
    yield coverage
    yield updated


class _CoverageCollector:
    def collect(self) -> Iterable[GaugeMetricFamily]:
        yield from _coverage_metric_families()


REGISTRY.register(_CoverageCollector())

# Nhịp đập của các vòng nền trong worker. Là Gauge chứ không phải Counter vì
# worker chạy ở tiến trình khác: API đọc trạng thái đã lưu trong DB rồi phản
# chiếu ra, chứ không phải tự đếm.
WORKER_LAST_TICK_AGE = Gauge(
    "p004_worker_last_tick_age_seconds",
    "Seconds since a background worker loop last completed a tick",
    ("loop",),
)
WORKER_TICKS = Gauge("p004_worker_ticks_total", "Background worker loop ticks", ("loop",))
WORKER_ERRORS = Gauge("p004_worker_errors_total", "Background worker loop ticks that raised", ("loop",))
WORKER_PROCESSED = Gauge("p004_worker_processed_total", "Items produced by background worker loops", ("loop",))


def collect_product_metrics() -> None:
    """Refresh aggregate product metrics without exporting private content."""
    from src.models.app_rating import AppRating
    from src.models.brief import Brief
    from src.models.connection import Connection
    from src.models.llm_usage import LLMUsageEvent
    from src.models.run import Run
    from src.models.task import Task
    from src.models.telemetry import TelemetryEvent
    from src.models.user import User

    db = SessionLocal()
    try:
        PRODUCT_USERS.set(db.scalar(select(func.count(User.id))) or 0)

        since = datetime.now(UTC) - timedelta(days=7)
        active_ids = {
            str(uid)
            for (uid,) in db.execute(
                select(TelemetryEvent.user_id)
                .where(TelemetryEvent.created_at >= since, TelemetryEvent.user_id.is_not(None))
                .distinct()
            ).all()
        }
        active_ids.update(
            str(uid) for (uid,) in db.execute(select(Run.user_id).where(Run.created_at >= since).distinct()).all()
        )
        PRODUCT_ACTIVE_USERS.set(len(active_ids))

        PRODUCT_CONNECTIONS.clear()
        for provider, status, count in db.execute(
            select(Connection.provider, Connection.status, func.count(Connection.id)).group_by(
                Connection.provider, Connection.status
            )
        ).all():
            PRODUCT_CONNECTIONS.labels(str(provider), str(status)).set(count)

        PRODUCT_RUNS.clear()
        for status, count in db.execute(select(Run.status, func.count(Run.id)).group_by(Run.status)).all():
            PRODUCT_RUNS.labels(str(status)).set(count)

        PRODUCT_BRIEFS.set(db.scalar(select(func.count(Brief.id))) or 0)

        PRODUCT_TASKS.clear()
        for status, count in db.execute(select(Task.status, func.count(Task.id)).group_by(Task.status)).all():
            PRODUCT_TASKS.labels(str(status)).set(count)

        # Event names/surfaces are bounded by the telemetry allowlist; values and
        # attributes are intentionally never exported.
        for name, surface, count, avg_duration in db.execute(
            select(
                TelemetryEvent.name,
                TelemetryEvent.surface,
                func.count(TelemetryEvent.id),
                func.avg(TelemetryEvent.duration_ms),
            ).group_by(TelemetryEvent.name, TelemetryEvent.surface)
        ).all():
            PRODUCT_TELEMETRY.labels(str(name), str(surface)).set(count)
            if avg_duration is not None:
                PRODUCT_TELEMETRY_AVG_DURATION.labels(str(name)).set(avg_duration)

        _collect_worker_metrics(db)
        _collect_rating_metrics(db, AppRating)
        _collect_llm_usage_metrics(db, LLMUsageEvent)
    finally:
        db.close()


def _collect_llm_usage_metrics(db, usage_model) -> None:
    """Phản chiếu ledger DB chung của API/worker ra aggregate không chứa PII."""
    for metric in (
        LLM_TOKENS,
        LLM_ESTIMATED_COST,
        LLM_CALLS,
        LLM_USAGE_MISSING,
        LLM_PRICING_UNKNOWN,
        LLM_USER_TOKENS,
        LLM_USER_ESTIMATED_COST,
        LLM_USER_ATTRIBUTION_MISSING,
        LLM_PERSISTED_AVG_DURATION,
    ):
        metric.clear()

    for model, lane, status, count in db.execute(
        select(usage_model.model, usage_model.lane, usage_model.status, func.count(usage_model.id)).group_by(
            usage_model.model, usage_model.lane, usage_model.status
        )
    ).all():
        LLM_CALLS.labels(str(model), str(lane), str(status)).set(count)

    for model, lane, input_tokens, output_tokens, cost, avg_duration in db.execute(
        select(
            usage_model.model,
            usage_model.lane,
            func.sum(usage_model.input_tokens),
            func.sum(usage_model.output_tokens),
            func.sum(usage_model.estimated_cost_usd),
            func.avg(usage_model.duration_ms),
        )
        .where(usage_model.status == "success")
        .group_by(usage_model.model, usage_model.lane)
    ).all():
        if input_tokens is not None:
            LLM_TOKENS.labels(str(model), str(lane), "input").set(input_tokens)
        if output_tokens is not None:
            LLM_TOKENS.labels(str(model), str(lane), "output").set(output_tokens)
        if cost is not None:
            LLM_ESTIMATED_COST.labels(str(model), str(lane)).set(cost)
        if avg_duration is not None:
            LLM_PERSISTED_AVG_DURATION.labels(str(model), str(lane)).set(float(avg_duration) / 1000)

    for model, lane, count in db.execute(
        select(usage_model.model, usage_model.lane, func.count(usage_model.id))
        .where(usage_model.status == "success", usage_model.usage_available.is_(False))
        .group_by(usage_model.model, usage_model.lane)
    ).all():
        LLM_USAGE_MISSING.labels(str(model), str(lane)).set(count)
    for model, lane, count in db.execute(
        select(usage_model.model, usage_model.lane, func.count(usage_model.id))
        .where(usage_model.usage_available.is_(True), usage_model.price_available.is_(False))
        .group_by(usage_model.model, usage_model.lane)
    ).all():
        LLM_PRICING_UNKNOWN.labels(str(model), str(lane)).set(count)

    secret = get_settings().app_secret_key
    attributed = db.execute(
        select(
            usage_model.user_id,
            func.sum(usage_model.input_tokens),
            func.sum(usage_model.output_tokens),
            func.sum(usage_model.estimated_cost_usd),
        )
        .where(usage_model.user_id.is_not(None), usage_model.usage_available.is_(True))
        .group_by(usage_model.user_id)
    ).all()
    if not secret:
        LLM_USER_ATTRIBUTION_MISSING.labels("hash_secret_missing").set(len(attributed))
    else:
        for user_id, input_tokens, output_tokens, cost in attributed:
            digest = pseudonymous_llm_user_hash(str(user_id), secret)
            LLM_USER_TOKENS.labels(digest, "input").set(input_tokens or 0)
            LLM_USER_TOKENS.labels(digest, "output").set(output_tokens or 0)
            if cost is not None:
                LLM_USER_ESTIMATED_COST.labels(digest).set(cost)
    unattributed = db.scalar(
        select(func.count(usage_model.id)).where(
            usage_model.user_id.is_(None), usage_model.usage_available.is_(True)
        )
    )
    if unattributed:
        LLM_USER_ATTRIBUTION_MISSING.labels("no_user_scope").set(unattributed)


def _collect_worker_metrics(db) -> None:
    """Phản chiếu nhịp đập worker (bảng `worker_heartbeats`) ra Prometheus.

    Tuổi của nhịp mới là thứ đáng cảnh báo, không phải bản thân mốc thời gian:
    alert viết được thành `p004_worker_last_tick_age_seconds > 3 * chu_kỳ` mà
    không cần Prometheus biết chu kỳ từng vòng là bao nhiêu.
    """
    from src.services.worker_health import read_heartbeats

    now = datetime.now(UTC)
    WORKER_LAST_TICK_AGE.clear()
    WORKER_TICKS.clear()
    WORKER_ERRORS.clear()
    WORKER_PROCESSED.clear()
    for row in read_heartbeats(db):
        loop = str(row.loop)
        # SQLite trả về datetime naive sau khi đọc lại; so sánh thẳng với mốc
        # aware sẽ ném TypeError và làm hỏng cả endpoint /metrics.
        last_tick = row.last_tick_at if row.last_tick_at.tzinfo else row.last_tick_at.replace(tzinfo=UTC)
        WORKER_LAST_TICK_AGE.labels(loop).set((now - last_tick).total_seconds())
        WORKER_TICKS.labels(loop).set(row.tick_count or 0)
        WORKER_ERRORS.labels(loop).set(row.error_count or 0)
        WORKER_PROCESSED.labels(loop).set(row.processed_count or 0)


def route_group(path: str) -> str:
    if path == "/health":
        return "/health"
    if path == "/metrics":
        return "/metrics"
    if path.startswith("/api/v1"):
        return "/api/v1"
    return "/other"


def metrics_response() -> Response:
    collect_product_metrics()
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")
