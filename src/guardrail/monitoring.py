"""Small dependency-free metrics and alerting primitives for guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class GuardrailMetrics:
    total_requests: int = 0
    blocked_requests: int = 0
    rate_limit_hits: int = 0
    judge_evaluations: int = 0
    judge_failures: int = 0

    @property
    def block_rate(self) -> float:
        return self.blocked_requests / self.total_requests if self.total_requests else 0.0

    @property
    def judge_fail_rate(self) -> float:
        return self.judge_failures / self.judge_evaluations if self.judge_evaluations else 0.0


@dataclass(frozen=True)
class MonitoringAlertEvent:
    name: str
    severity: str
    value: float
    threshold: float
    message: str


class MetricsCollector:
    """Thread-safe counters; labels/details should never contain raw content."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total = 0
        self._blocked = 0
        self._rate_limit = 0
        self._judge_total = 0
        self._judge_failed = 0

    def record_request(self, *, blocked: bool = False) -> None:
        with self._lock:
            self._total += 1
            self._blocked += int(blocked)

    def record_rate_limit_hit(self) -> None:
        with self._lock:
            self._rate_limit += 1

    def record_judge(self, *, passed: bool) -> None:
        with self._lock:
            self._judge_total += 1
            self._judge_failed += int(not passed)

    def snapshot(self) -> GuardrailMetrics:
        with self._lock:
            return GuardrailMetrics(self._total, self._blocked, self._rate_limit, self._judge_total, self._judge_failed)


class MonitoringAlert:
    """Alert when any safety/availability signal crosses its threshold."""

    def __init__(
        self,
        *,
        block_rate_threshold: float = 0.20,
        rate_limit_hits_threshold: int = 20,
        judge_fail_rate_threshold: float = 0.10,
    ) -> None:
        self.block_rate_threshold = block_rate_threshold
        self.rate_limit_hits_threshold = rate_limit_hits_threshold
        self.judge_fail_rate_threshold = judge_fail_rate_threshold

    def check_metrics(
        self, metrics: GuardrailMetrics | MetricsCollector | dict[str, Any]
    ) -> list[MonitoringAlertEvent]:
        if isinstance(metrics, MetricsCollector):
            metrics = metrics.snapshot()
        if isinstance(metrics, dict):
            metrics = GuardrailMetrics(**metrics)
        alerts: list[MonitoringAlertEvent] = []
        if metrics.block_rate > self.block_rate_threshold:
            alerts.append(
                MonitoringAlertEvent(
                    "block_rate_high",
                    "warning",
                    metrics.block_rate,
                    self.block_rate_threshold,
                    "Guardrail block rate exceeded threshold",
                )
            )
        if metrics.rate_limit_hits > self.rate_limit_hits_threshold:
            alerts.append(
                MonitoringAlertEvent(
                    "rate_limit_hits_high",
                    "critical",
                    float(metrics.rate_limit_hits),
                    float(self.rate_limit_hits_threshold),
                    "Rate-limit hits increased above threshold",
                )
            )
        if metrics.judge_fail_rate > self.judge_fail_rate_threshold:
            alerts.append(
                MonitoringAlertEvent(
                    "judge_fail_rate_high",
                    "critical",
                    metrics.judge_fail_rate,
                    self.judge_fail_rate_threshold,
                    "Grounding/judge failure rate exceeded threshold",
                )
            )
        return alerts
