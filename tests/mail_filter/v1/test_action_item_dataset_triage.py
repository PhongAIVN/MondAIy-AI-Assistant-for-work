from __future__ import annotations

import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.services.filter_classify import FilterConfig, filter_and_classify, triage_email

ACTION_ITEM_DATASET = Path(__file__).with_name("action-item-dataset.tgz")
USER_EMAIL = "radar-user@example.test"


@dataclass(frozen=True)
class TriageMetrics:
    total: int
    positives: int
    negatives: int
    auto_keep: int
    auto_drop: int
    llm_judge: int
    positive_auto_drop: int
    positive_routed_to_keep_or_judge: int
    auto_precision: float
    auto_recall: float
    auto_f1: float


def _read_archive_text(tar: tarfile.TarFile, member_name: str) -> str:
    extracted = tar.extractfile(member_name)
    assert extracted is not None
    return extracted.read().decode("utf-8", errors="replace")


def _parse_judgments(raw: str) -> dict[str, bool]:
    labels: dict[str, bool] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].startswith("msg-"):
            continue
        labels[parts[0]] = parts[1].upper() == "Y"
    return labels


def _subject_and_body(raw: str) -> tuple[str, str]:
    subject = ""
    lines = raw.splitlines()
    body_start = 0

    for index, line in enumerate(lines):
        if line.startswith("Subject:"):
            subject = line.removeprefix("Subject:").strip()
        if line.strip() == "A:":
            body_start = index + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


def _dataset_items() -> tuple[list[dict], dict[str, bool]]:
    with tarfile.open(ACTION_ITEM_DATASET, "r:gz") as tar:
        judgments_raw = _read_archive_text(tar, "distribute/handStripped/judgments/judgments.txt")
        gold = _parse_judgments(judgments_raw)
        items: list[dict] = []

        for message_name in sorted(gold, key=lambda value: int(value.removeprefix("msg-").removesuffix(".txt"))):
            raw = _read_archive_text(tar, f"distribute/handStripped/messages/{message_name}")
            subject, body = _subject_and_body(raw)
            message_id = message_name.removesuffix(".txt")
            items.append(
                {
                    "id": message_id,
                    "thread_id": message_id,
                    "source_id": "RADAR_ACTION_ITEM",
                    "provider": "google",
                    "author_id": "sender@example.test",
                    "author_name": "RADAR Sender",
                    "from": "RADAR Sender <sender@example.test>",
                    "to": [f"RADAR User <{USER_EMAIL}>"],
                    "subject": subject,
                    "text": body,
                    "normalized_text": body,
                    "snippet": body[:240],
                    "sent_at": datetime(2026, 8, 14, tzinfo=UTC),
                    "label_ids": ["INBOX"],
                    "is_unread": True,
                    "deep_link": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                }
            )

    return items, {key.removesuffix(".txt"): value for key, value in gold.items()}


def _triage_metrics() -> tuple[TriageMetrics, Counter[str], list[str]]:
    items, gold = _dataset_items()
    config = FilterConfig(user_email=USER_EMAIL, approved_labels=frozenset({"INBOX"}), lookback_days=30)

    decisions = {item["id"]: triage_email(item, config).decision for item in items}
    counts = Counter(decisions.values())

    auto_keep_ids = {message_id for message_id, decision in decisions.items() if decision == "keep"}
    positive_auto_drop = [
        message_id for message_id, expected in gold.items() if expected and decisions[message_id] == "drop"
    ]

    tp = sum(message_id in auto_keep_ids and expected for message_id, expected in gold.items())
    fp = sum(message_id in auto_keep_ids and not expected for message_id, expected in gold.items())
    fn = sum(message_id not in auto_keep_ids and expected for message_id, expected in gold.items())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    metrics = TriageMetrics(
        total=len(gold),
        positives=sum(gold.values()),
        negatives=len(gold) - sum(gold.values()),
        auto_keep=counts["keep"],
        auto_drop=counts["drop"],
        llm_judge=counts["llm_judge"],
        positive_auto_drop=len(positive_auto_drop),
        positive_routed_to_keep_or_judge=sum(
            expected and decisions[message_id] in {"keep", "llm_judge"} for message_id, expected in gold.items()
        ),
        auto_precision=precision,
        auto_recall=recall,
        auto_f1=f1,
    )
    return metrics, counts, positive_auto_drop


def test_action_item_dataset_routes_stripped_uncertain_mail_to_llm_judge():
    metrics, counts, positive_auto_drop = _triage_metrics()

    assert metrics.total == 744
    assert metrics.positives == 328
    assert metrics.negatives == 416
    assert metrics.positive_auto_drop == 0
    assert metrics.positive_routed_to_keep_or_judge == metrics.positives
    assert metrics.llm_judge >= 700
    assert counts == {"llm_judge": 744}
    assert positive_auto_drop == []


def test_binary_filter_passes_llm_judge_route_to_existing_extractor():
    items, _gold = _dataset_items()
    result = filter_and_classify(
        items[:5],
        FilterConfig(user_email=USER_EMAIL, approved_labels=frozenset({"INBOX"}), lookback_days=30),
        now=datetime(2026, 8, 14, tzinfo=UTC),
    )

    assert result["candidate_count"] == 5
    assert result["rejected_count"] == 0
    assert {item["triage_decision"] for item in result["items"]} == {"llm_judge"}
    assert {item["filter_route"] for item in result["items"]} == {"llm_extraction"}
    assert {item["triage_reason"] for item in result["items"]} == {"uncertain_stripped_text"}


def test_auto_decision_metrics_are_explicitly_not_final_llm_metrics():
    metrics, _counts, _positive_auto_drop = _triage_metrics()

    assert metrics.auto_precision == pytest.approx(0.0)
    assert metrics.auto_recall == pytest.approx(0.0)
    assert metrics.auto_f1 == pytest.approx(0.0)
