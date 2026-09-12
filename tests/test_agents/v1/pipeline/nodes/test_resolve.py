from datetime import UTC, datetime

from src.agents.pipeline.nodes.resolve import resolve_node
from tests.test_agents.v1.pipeline.conftest import gmail_item, jira_item


def test_resolve_never_guesses_missing_deadline_or_assignee(pipeline_state):
    pipeline_state["extracted"] = [
        {
            "message": {**gmail_item(), "to": ["other@example.com"]},
            "title": "Review",
            "assignee_hint": "",
            "time_expression": "",
            "evidence_quote": "Review this",
            "confidence": 0.6,
        }
    ]

    item = resolve_node(pipeline_state)["resolved"][0]

    assert item["due_at"] is None
    assert item["assignee"] is None
    assert item["ambiguous"] is False


def test_resolve_uses_structured_due_at_and_assignee_for_jira_without_guessing(pipeline_state):
    due = datetime(2026, 8, 15, tzinfo=UTC)
    pipeline_state["extracted"] = [
        {
            "message": jira_item(),
            "title": "Hoàn thành báo cáo tuần 3",
            "assignee_hint": "acc-phong-01",
            "time_expression": "",
            "evidence_quote": "Đội cần nộp trước thứ Sáu.",
            "confidence": 1.0,
            "structured_due_at": due,
            "structured_assignee": "acc-phong-01",
            "structured_assignee_ambiguous": False,
        }
    ]

    item = resolve_node(pipeline_state)["resolved"][0]

    assert item["due_at"] == due
    assert item["all_day"] is True
    assert item["ambiguous"] is False
    assert item["assignee"] == "acc-phong-01"
    assert item["assignee_ambiguous"] is False


def test_resolve_structured_due_at_none_stays_none_not_reguessed(pipeline_state):
    pipeline_state["extracted"] = [
        {
            "message": jira_item(),
            "title": "Việc không có hạn",
            "assignee_hint": "",
            "time_expression": "trước thứ Sáu",  # nếu bị đoán lại sẽ ra due_at khác None
            "evidence_quote": "...",
            "confidence": 1.0,
            "structured_due_at": None,
            "structured_assignee": None,
            "structured_assignee_ambiguous": True,
        }
    ]

    item = resolve_node(pipeline_state)["resolved"][0]

    assert item["due_at"] is None
    assert item["assignee"] is None
    assert item["assignee_ambiguous"] is True
