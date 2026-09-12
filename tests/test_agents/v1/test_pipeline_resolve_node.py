import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.nodes.resolve import resolve_node
from src.db import Base
from src.models.run import Run

# Bài kiểm tra engineering cho CP2 (make_batches và resolve ngày giờ/danh tính) —
# chạy resolve_node đầu-cuối trên dữ liệu shape Gmail thật (extract_batch ->
# resolve), ghi audit CP0 (PipelineResolvedItem) vào sqlite in-memory. Đây KHÔNG
# phải fixture QC do Dũng soạn — điều kiện dừng ghi trong ticket vẫn cần fixture
# riêng từ QC trước khi đóng ticket.
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
        idempotency_key=f"test-resolve-node-{uuid.uuid4()}",
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        yield {"db": db, "run_id": run.id, "user_email": "phong@student.mondaiy.vn", "extracted": []}
    finally:
        db.close()


def _gmail_message(to: list[str]) -> dict:
    return {
        "id": "18f2a9c7b3e4d501",
        "provider": "google",
        "source_id": "INBOX",
        "to": to,
        "cc": [],
        "is_self": False,
    }


def test_resolve_node_resolves_due_at_and_assignee_when_evidence_is_direct_and_explicit(state):
    state["extracted"] = [
        {
            "message": _gmail_message(to=["phong@student.mondaiy.vn"]),
            "title": "Nộp báo cáo tuần 3",
            "assignee_hint": "",
            "time_expression": "23:59 thứ Sáu (GMT+7)",
            "evidence_quote": "vui lòng nộp báo cáo tuần 3 trước 23:59 thứ Sáu (GMT+7)",
            "confidence": 0.93,
        }
    ]

    result = resolve_node(state)
    item = result["resolved"][0]

    assert item["due_at"] is not None
    assert item["ambiguous"] is False
    assert item["assignee"] == "phong@student.mondaiy.vn"
    assert item["assignee_ambiguous"] is False


def test_resolve_node_leaves_due_at_blank_when_time_expression_lacks_timezone(state):
    state["extracted"] = [
        {
            "message": _gmail_message(to=["phong@student.mondaiy.vn"]),
            "title": "Đăng ký slot demo dự án",
            "assignee_hint": "",
            "time_expression": "trước Chủ Nhật",
            "evidence_quote": "Vui lòng đăng ký trước Chủ Nhật",
            "confidence": 0.81,
        }
    ]

    result = resolve_node(state)
    item = result["resolved"][0]

    assert item["due_at"] is None
    assert item["ambiguous"] is True
    # thời gian mơ hồ không kéo theo danh tính mơ hồ — 2 cờ độc lập nhau
    assert item["assignee_ambiguous"] is False


def test_resolve_node_does_not_guess_assignee_when_message_not_addressed_to_user(state):
    state["extracted"] = [
        {
            "message": _gmail_message(to=["ban-to-chuc@mondaiy.vn"]),
            "title": "Review PR trước buổi họp nhóm",
            "assignee_hint": "Nam",
            "time_expression": "",
            "evidence_quote": "Nam ơi review PR giúp mình trước buổi họp",
            "confidence": 0.7,
        }
    ]

    result = resolve_node(state)
    item = result["resolved"][0]

    assert item["assignee"] is None
    assert item["assignee_ambiguous"] is True


def test_resolve_node_persists_audit_row_per_item(state):
    state["extracted"] = [
        {
            "message": _gmail_message(to=["phong@student.mondaiy.vn"]),
            "title": "A",
            "assignee_hint": "",
            "time_expression": "",
            "evidence_quote": "a",
            "confidence": 0.5,
        },
        {
            "message": _gmail_message(to=["phong@student.mondaiy.vn"]),
            "title": "B",
            "assignee_hint": "",
            "time_expression": "",
            "evidence_quote": "b",
            "confidence": 0.5,
        },
    ]

    result = resolve_node(state)

    assert len(result["resolved"]) == 2
    assert all(item["_pipeline_resolved_item_id"] is not None for item in result["resolved"])
