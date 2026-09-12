from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import openpyxl
import pytest

from src.services.filter_classify import FilterConfig, filter_and_classify

GOLDEN_XLSX = Path(__file__).with_name("mondaiy_email_filter_golden_100_vi_research_augmented.xlsx")
SHEET_NAME = "email_filter_50"
USER_EMAIL = "an@example.com"

# Excel column positions in SHEET_NAME. Kept numeric to avoid source-encoding
# issues with Vietnamese column names on Windows shells.
COL_ID = 0
COL_LABEL = 2
COL_SUBJECT = 4
COL_SENDER = 5
COL_RECIPIENT = 6
COL_SENT_AT = 7
COL_BODY = 8


@dataclass(frozen=True)
class FilterMetrics:
    total: int
    keep: int
    drop: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float
    recall: float
    f1: float


def _slug_email(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    local = re.sub(r"[^a-z0-9]+", ".", text).strip(".") or "sender"
    return f"{local[:48]}@example.test"


def _recipient_addresses(value: object) -> list[str]:
    addresses: list[str] = []
    for part in re.split(r"[;,]", str(value or "")):
        name = part.strip()
        if not name:
            continue
        addresses.append(f"An <{USER_EMAIL}>" if name.casefold() == "an" else name)
    return addresses


def _golden_items() -> tuple[list[dict], dict[str, bool]]:
    workbook = openpyxl.load_workbook(GOLDEN_XLSX, read_only=True, data_only=True)
    sheet = workbook[SHEET_NAME]
    items: list[dict] = []
    gold: dict[str, bool] = {}

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or not row[COL_ID]:
            continue

        message_id = str(row[COL_ID])
        sender = row[COL_SENDER] or ""
        sender_addr = _slug_email(sender)
        body = row[COL_BODY] or ""
        sent_at = datetime.fromisoformat(str(row[COL_SENT_AT])).replace(tzinfo=UTC)

        items.append(
            {
                "id": message_id,
                "source_id": "INBOX",
                "provider": "google",
                "author_id": sender_addr,
                "author_name": sender,
                "from": f"{sender} <{sender_addr}>",
                "to": _recipient_addresses(row[COL_RECIPIENT]),
                "subject": row[COL_SUBJECT] or "",
                "text": body,
                "normalized_text": body,
                "snippet": body[:240],
                "sent_at": sent_at,
                "label_ids": ["INBOX"],
                "is_unread": True,
                "deep_link": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
            }
        )
        gold[message_id] = str(row[COL_LABEL]).upper() == "KEEP"

    return items, gold


def _run_agent_mail_filter() -> tuple[FilterMetrics, list[str], list[str]]:
    """Evaluate the deterministic filter used by Gmail agent entry points.

    Agent paths:
    - src.services.gmail_tools.search_gmail_messages -> filter_and_classify
    - src.agents.pipeline.nodes.filter.filter_node -> filter_and_classify
    """
    items, gold = _golden_items()
    result = filter_and_classify(
        items,
        FilterConfig(
            user_email=USER_EMAIL,
            approved_labels=frozenset({"INBOX"}),
            lookback_days=30,
        ),
        now=datetime(2026, 8, 14, tzinfo=UTC),
    )

    predicted_keep = {item["id"]: True for item in result["items"]}
    for item in result["rejected"]:
        predicted_keep.setdefault(item["id"], False)

    tp = sum(predicted_keep[mid] and expected for mid, expected in gold.items())
    fp = sum(predicted_keep[mid] and not expected for mid, expected in gold.items())
    fn = sum((not predicted_keep[mid]) and expected for mid, expected in gold.items())
    tn = sum((not predicted_keep[mid]) and not expected for mid, expected in gold.items())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    false_negatives = [mid for mid, expected in gold.items() if expected and not predicted_keep[mid]]
    false_positives = [mid for mid, expected in gold.items() if not expected and predicted_keep[mid]]
    metrics = FilterMetrics(
        total=len(gold),
        keep=sum(gold.values()),
        drop=len(gold) - sum(gold.values()),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=precision,
        recall=recall,
        f1=f1,
    )
    return metrics, false_negatives, false_positives


def test_agent_mail_filter_precision_recall_f1_on_golden_xlsx():
    metrics, false_negatives, false_positives = _run_agent_mail_filter()

    assert metrics.total == 100
    assert metrics.keep == 57
    assert metrics.drop == 43
    assert metrics.tp == 57
    assert metrics.fp == 0
    assert metrics.fn == 0
    assert metrics.tn == 43
    assert metrics.precision == pytest.approx(1.0)
    assert metrics.recall == pytest.approx(1.0)
    assert metrics.f1 == pytest.approx(1.0)
    assert false_negatives == []
    assert false_positives == []
