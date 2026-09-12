from __future__ import annotations

import logging

import pytest
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from src.agents import graph as graph_module
from src.agents.nodes import core_nodes
from src.observability import record_agent_outcome


def _sample_value(name: str, **labels: str) -> float:
    payload = generate_latest().decode("utf-8")
    for family in text_string_to_metric_families(payload):
        for sample in family.samples:
            if sample.name == name and all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0


def test_agent_outcome_records_deduplicated_allowlisted_metrics() -> None:
    before_turns = _sample_value("p004_agent_turns_total", guardrail_blocked="true")
    before_input = _sample_value(
        "p004_agent_guardrail_blocked_turns_total", stage="input", reason="prompt_injection"
    )
    before_tool = _sample_value(
        "p004_agent_guardrail_blocked_turns_total", stage="tool", reason="tool_policy"
    )
    before_grounding = _sample_value("p004_agent_grounding_results_total", status="abstain")
    before_backend = _sample_value(
        "p004_agent_intent_backend_total", backend="shared_rag_embedding_unavailable"
    )
    before_iterations_count = _sample_value("p004_agent_tool_iterations_count")
    before_iterations_sum = _sample_value("p004_agent_tool_iterations_sum")

    record_agent_outcome(
        {
            "guardrail": {
                "decision": "block",
                "reason": "prompt_injection",
                "tool_decisions": [
                    {"decision": "block", "reason": "tool_policy"},
                    {"decision": "block", "reason": "tool_policy"},
                ],
            },
            "grounding_status": "abstain",
            "intent_trace": {"backend": "shared_rag_embedding_unavailable"},
        },
        3,
        [],
        set(),
    )

    assert _sample_value("p004_agent_turns_total", guardrail_blocked="true") == before_turns + 1
    assert _sample_value(
        "p004_agent_guardrail_blocked_turns_total", stage="input", reason="prompt_injection"
    ) == before_input + 1
    assert _sample_value(
        "p004_agent_guardrail_blocked_turns_total", stage="tool", reason="tool_policy"
    ) == before_tool + 1
    assert _sample_value("p004_agent_grounding_results_total", status="abstain") == before_grounding + 1
    assert _sample_value(
        "p004_agent_intent_backend_total", backend="shared_rag_embedding_unavailable"
    ) == before_backend + 1
    assert _sample_value("p004_agent_tool_iterations_count") == before_iterations_count + 1
    assert _sample_value("p004_agent_tool_iterations_sum") == before_iterations_sum + 3


def test_agent_outcome_rejects_unbounded_labels_and_pii_from_scrape(
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_value = "raw-user-77:thai.metric@example.test"

    with caplog.at_level(logging.WARNING, logger="src.observability"):
        record_agent_outcome(
            {
                "guardrail": {"decision": "block", "reason": private_value},
                "grounding_status": private_value,
                "intent_trace": {"backend": private_value},
            },
            99,
            [(private_value, "ok"), ("calculate", private_value)],
            {"calculate"},
        )

    scrape = generate_latest().decode("utf-8")
    assert private_value not in scrape
    assert "thai.metric@example.test" not in scrape
    assert len([record for record in caplog.records if "ngoài allowlist" in record.getMessage()]) == 5
    assert any("tool_iterations không hợp lệ" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_tool_calls_classify_every_observation_with_required_precedence() -> None:
    observations = [
        {
            "name": "calculate",
            "output": "Công cụ calculate lỗi: denied",
            "data": {"error": "denied"},
            "guardrail": {"decision": "block"},
        },
        {"name": "current_datetime", "output": "Chưa có kết nối tới nguồn", "data": {"error": "offline"}},
        {
            "name": "gmail_bridge_search",
            "output": "Gmail bridge chưa được bật hoặc chưa được cấp cho user hiện tại; luồng Gmail OAuth hiện tại vẫn được giữ nguyên.",
        },
        {
            "name": "gmail_bridge_read_thread",
            "output": "Gmail bridge chưa được bật hoặc chưa được cấp cho user hiện tại.",
        },
        {"name": "list_tasks", "output": "Công cụ list_tasks lỗi: timeout"},
        {"name": "draft_task", "output": "tool trả lỗi có cấu trúc", "data": {"error": "invalid"}},
        {"name": "relative_time", "output": "Chưa có quyền đọc nguồn này"},
        {"name": "suggest_tasks", "output": "{}", "data": {"proposals": []}},
        {"name": "program_schedule", "output": "có 2 lịch"},
    ]
    expected = [
        ("calculate", "blocked"),
        ("current_datetime", "not_connected"),
        ("gmail_bridge_search", "not_connected"),
        ("gmail_bridge_read_thread", "not_connected"),
        ("list_tasks", "error"),
        ("draft_task", "error"),
        ("relative_time", "error"),
        ("suggest_tasks", "empty"),
        ("program_schedule", "ok"),
    ]
    before = {(tool, outcome): _sample_value("p004_agent_tool_calls_total", tool=tool, outcome=outcome) for tool, outcome in expected}

    await core_nodes.measure_outcome_node({"observations": observations, "tool_iterations": 1})

    for tool, outcome in expected:
        assert _sample_value("p004_agent_tool_calls_total", tool=tool, outcome=outcome) == before[(tool, outcome)] + 1


def test_gmail_bridge_not_connected_match_is_exact_and_preserves_blocked_precedence() -> None:
    canonical = "Gmail bridge chưa được bật hoặc chưa được cấp cho user hiện tại."

    assert core_nodes._tool_observation_outcome({"output": canonical}) == "not_connected"
    assert core_nodes._tool_observation_outcome({"output": "Gmail bridge chưa được bật lại thành công."}) == "ok"
    assert core_nodes._tool_observation_outcome(
        {"output": canonical, "guardrail": {"decision": "block"}}
    ) == "blocked"


def test_tool_metric_allowlist_is_derived_from_bound_tool_objects() -> None:
    expected = {tool.name for tool in [*core_nodes._BASE_TOOLS, core_nodes.web_search]}

    assert core_nodes._metric_tool_names() == expected
    assert core_nodes.web_search.name in core_nodes._metric_tool_names()


@pytest.mark.asyncio
async def test_measure_outcome_node_runs_once_after_multiple_tool_loops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[tuple[dict, int]] = []

    async def fake_think(state: dict) -> dict:
        iterations = state.get("tool_iterations", 0)
        if iterations < 2:
            return {"pending_tool_calls": [{"name": "read_test", "args": {}}]}
        return {
            "pending_tool_calls": [],
            "metadata": {"intent_trace": {"backend": "llm_structured_output"}},
        }

    async def fake_action(state: dict) -> dict:
        iteration = state.get("tool_iterations", 0)
        return {
            "pending_tool_calls": [],
            "latest_observations": [{"name": "calculate", "output": str(iteration + 1)}],
            "tool_iterations": iteration + 1,
        }

    async def fake_observe(state: dict) -> dict:
        return {
            "observations": [*(state.get("observations") or []), *(state.get("latest_observations") or [])],
            "latest_observations": [],
        }

    async def fake_respond(_state: dict) -> dict:
        return {"response": "done"}

    monkeypatch.setattr(graph_module, "think_node", fake_think)
    monkeypatch.setattr(graph_module, "action_node", fake_action)
    monkeypatch.setattr(graph_module, "observe_node", fake_observe)
    monkeypatch.setattr(graph_module, "respond_node", fake_respond)
    monkeypatch.setattr(
        core_nodes,
        "record_agent_outcome",
        lambda metadata, iterations, outcomes, allowed: recorded.append((metadata, iterations, outcomes, allowed)),
    )

    result = await graph_module.build_graph().ainvoke({"query": "test"})

    assert result["response"] == "done"
    assert result["tool_iterations"] == 2
    assert recorded == [
        (
            {"intent_trace": {"backend": "llm_structured_output"}},
            2,
            [("calculate", "ok"), ("calculate", "ok")],
            core_nodes._metric_tool_names(),
        )
    ]


@pytest.mark.asyncio
async def test_measure_outcome_node_runs_once_on_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[tuple[dict, int]] = []

    async def fake_think(_state: dict) -> dict:
        return {"error": "provider failed"}

    monkeypatch.setattr(graph_module, "think_node", fake_think)
    monkeypatch.setattr(
        core_nodes,
        "record_agent_outcome",
        lambda metadata, iterations, outcomes, allowed: recorded.append((metadata, iterations, outcomes, allowed)),
    )

    result = await graph_module.build_graph().ainvoke({"query": "test"})

    assert result["error"] == "provider failed"
    assert recorded == [({}, 0, [], core_nodes._metric_tool_names())]
