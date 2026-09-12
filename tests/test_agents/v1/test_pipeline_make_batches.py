import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.nodes.make_batches import make_batches_node
from src.db import Base
from src.models.run import Run

# make_batches_node ghi audit CP0 (PipelineBatch) nên cần 1 Session + 1 Run có
# thật — sqlite in-memory riêng cho test, không đụng DB dev/prod.
_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture
def state():
    db = _SessionLocal()
    run = Run(
        user_id=1,
        sources=[],
        range_from=datetime.now(UTC),
        range_to=datetime.now(UTC),
        idempotency_key=f"test-make-batches-node-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        yield {"db": db, "run_id": run.id, "filtered": []}
    finally:
        db.close()


def _items(count: int) -> list[dict]:
    return [{"id": f"m{i}"} for i in range(count)]


def test_make_batches_splits_into_groups_of_6(state):
    state["filtered"] = _items(51)

    result = make_batches_node(state)

    assert [len(batch) for batch in result["batches"]] == [6, 6, 6, 6, 6, 6, 6, 6, 3]


def test_make_batches_returns_single_batch_when_under_limit(state):
    state["filtered"] = _items(5)

    result = make_batches_node(state)

    assert len(result["batches"]) == 1
    assert len(result["batches"][0]) == 5


def test_make_batches_returns_empty_list_when_no_filtered_items(state):
    result = make_batches_node(state)

    assert result["batches"] == []


def test_make_batches_returns_exact_multiple_without_trailing_empty_batch(state):
    state["filtered"] = _items(36)

    result = make_batches_node(state)

    assert [len(batch) for batch in result["batches"]] == [6, 6, 6, 6, 6, 6]


def test_make_batches_tags_each_item_with_its_batch_id(state):
    state["filtered"] = _items(3)

    result = make_batches_node(state)

    batch_ids = {item["_pipeline_batch_id"] for item in result["batches"][0]}
    assert len(batch_ids) == 1
