"""Chạy bộ golden dataset NHÁP (eval/golden_dataset/resolve_make_batches/) qua
code thật. Bộ dataset này do kỹ sư soạn, CHƯA phải fixture chính thức của
Dũng (PO/QC) — xem README.md trong thư mục đó. Test này chỉ chứng minh code
khớp với draft, không phải bằng chứng điều kiện dừng CP2 đã đạt."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.identity_resolve import resolve_assignee
from src.agents.pipeline.nodes.make_batches import make_batches_node
from src.agents.pipeline.time_resolve import resolve_due_at
from src.db import Base
from src.models.run import Run

_DATASET_DIR = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset" / "resolve_make_batches"

_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)


def _load(name: str) -> list[dict]:
    return json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def batches_state():
    db = _SessionLocal()
    run = Run(
        user_id=1,
        sources=[],
        range_from=datetime.now(UTC),
        range_to=datetime.now(UTC),
        idempotency_key=f"test-golden-make-batches-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        yield {"db": db, "run_id": run.id}
    finally:
        db.close()


@pytest.mark.parametrize("case", _load("resolve_cases.json"), ids=lambda c: c["id"])
def test_resolve_case(case):
    payload = case["input"]
    expected = case["expected"]

    due_at = resolve_due_at(payload["time_expression"])
    ambiguous = due_at is None and bool(payload["time_expression"])
    assignee, assignee_ambiguous = resolve_assignee(payload["assignee_hint"], payload["message"], payload["user_email"])

    assert (due_at is not None) == expected["due_at_resolvable"], case["description"]
    assert ambiguous == expected["ambiguous"], case["description"]
    assert assignee == expected["assignee"], case["description"]
    assert assignee_ambiguous == expected["assignee_ambiguous"], case["description"]


@pytest.mark.parametrize("case", _load("make_batches_cases.json"), ids=lambda c: c["id"])
def test_make_batches_case(case, batches_state):
    batches_state["filtered"] = [{"id": f"m{i}"} for i in range(case["filtered_count"])]

    result = make_batches_node(batches_state)

    sizes = [len(batch) for batch in result["batches"]]
    assert sizes == case["expected_batch_sizes"], case["description"]
