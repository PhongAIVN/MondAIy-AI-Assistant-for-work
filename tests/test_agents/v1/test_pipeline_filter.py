import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.nodes.filter import filter_node
from src.db import Base
from src.models.run import Run

# filter_node ghi audit CP0 (PipelineFilteredMessage) nên cần 1 Session +
# 1 Run có thật — sqlite in-memory riêng cho test, không đụng DB dev/prod.
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
        idempotency_key=f"test-filter-node-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        yield {"db": db, "run_id": run.id, "normalized": []}
    finally:
        db.close()


def _msg(text: str) -> dict:
    return {"id": "m1", "text": text}


def test_filter_keeps_message_with_action_keyword(state):
    state["normalized"] = [_msg("Vui lòng nộp báo cáo trước cuối tuần.")]
    result = filter_node(state)
    assert len(result["filtered"]) == 1


def test_filter_keeps_message_with_date_pattern(state):
    state["normalized"] = [_msg("Họp vào thứ Sáu tuần này.")]
    result = filter_node(state)
    assert len(result["filtered"]) == 1


def test_filter_drops_message_with_no_signal(state):
    state["normalized"] = [_msg("Chúc mừng sinh nhật bạn nhé!")]
    result = filter_node(state)
    assert len(result["filtered"]) == 0


def test_filter_prefers_recall_keeps_ambiguous_but_relevant_message(state):
    # Ưu tiên recall cao — 1 tín hiệu hành động (reply) đã đủ giữ lại.
    state["normalized"] = [_msg("Reply khi rảnh nhé")]
    result = filter_node(state)
    assert len(result["filtered"]) == 1
