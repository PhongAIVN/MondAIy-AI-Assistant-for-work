from src.agents.pipeline.routing import route_after_filter


def test_summary_mode_routes_to_evidence_only_flow():
    assert route_after_filter({"mode": "summary"}) == "summary"


def test_task_mode_routes_to_extraction_flow():
    assert route_after_filter({"mode": "task_extraction"}) == "task_extraction"


def test_missing_mode_is_backward_compatible():
    assert route_after_filter({}) == "task_extraction"
