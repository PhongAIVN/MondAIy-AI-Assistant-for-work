"""Chạy golden dataset eval/golden_dataset/evidence_verification/ qua code
thật của evidence_node/verify_node (TAPB — Evidence Selection + Fact
Verification, xem docs/projects/engineering/outlook-detail.drawio)."""

import json
from pathlib import Path

import pytest

from src.agents.pipeline.nodes.evidence import select_evidence
from src.agents.pipeline.nodes.verify import verify_node

_DATASET_DIR = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset" / "evidence_verification"


def _load(name: str) -> list[dict]:
    return json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _load("evidence_selection_cases.json"), ids=lambda c: c["id"])
def test_evidence_selection_case(case):
    text = case["input"]["text"]
    expected = case["expected"]
    max_sentences = expected.get("max_sentences", 6)

    selected = select_evidence(text, max_sentences=max_sentences)

    if expected.get("unchanged"):
        assert selected == text, case["description"]
        return

    for snippet in expected.get("contains", []):
        assert snippet in selected, case["description"]
    for snippet in expected.get("excludes", []):
        assert snippet not in selected, case["description"]

    if "order" in expected:
        positions = [selected.find(snippet) for snippet in expected["order"]]
        assert all(p != -1 for p in positions), case["description"]
        assert positions == sorted(positions), case["description"]

    if expected.get("no_crash"):
        max_count = expected["max_selected_sentence_count"]
        assert len(selected.split(". ")) <= max_count, case["description"]


@pytest.mark.parametrize("case", _load("fact_verification_cases.json"), ids=lambda c: c["id"])
def test_fact_verification_case(case):
    payload = case["input"]
    expected = case["expected"]
    item = {
        "message": {"id": "gold-1", "provider": payload["provider"], "text": payload["text"]},
        "title": "Golden case",
        "time_expression": payload["time_expression"],
        "assignee_hint": payload["assignee_hint"],
        "evidence_quote": payload["text"],
    }

    result = verify_node({"extracted": [item]})

    verified = result["extracted"][0]
    assert verified["time_expression"] == expected["time_expression"], case["description"]
    assert verified["assignee_hint"] == expected["assignee_hint"], case["description"]
