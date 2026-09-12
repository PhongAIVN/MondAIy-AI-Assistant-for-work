"""Source-neutral evidence fusion, conflict detection and priority ranking."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    content: str
    importance: int
    due_at: datetime | None = None
    topic: str = ""


@dataclass
class EvidenceCluster:
    topic: str
    items: list[Evidence] = field(default_factory=list)
    priority: int = 0
    conflict: bool = False


def _topic(value: str) -> str:
    tokens = re.findall(r"[\wÀ-ỹ]+", value.casefold())
    return " ".join(token for token in tokens if len(token) > 2)[:80]


def fuse_and_rank(items: list[Evidence], now: datetime) -> list[EvidenceCluster]:
    """Fuse same explicit topic, flag conflicting due dates, then rank transparently."""
    clusters: dict[str, EvidenceCluster] = {}
    for item in items:
        key = item.topic or _topic(item.content)
        cluster = clusters.setdefault(key, EvidenceCluster(topic=key))
        cluster.items.append(item)
    for cluster in clusters.values():
        due_dates = {item.due_at.date() for item in cluster.items if item.due_at is not None}
        cluster.conflict = len(due_dates) > 1
        score = max(item.importance for item in cluster.items) + 8 * (len(cluster.items) - 1)
        if any(item.due_at and item.due_at.date() <= now.date() for item in cluster.items):
            score += 30
        if cluster.conflict:
            score += 20
        cluster.priority = score
    return sorted(clusters.values(), key=lambda cluster: cluster.priority, reverse=True)
