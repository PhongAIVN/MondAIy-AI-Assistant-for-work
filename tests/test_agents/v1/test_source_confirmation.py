from datetime import UTC, datetime

import pytest

from src.agents.nodes import core_nodes
from src.services.conversational_routing import ResolvedAction, resolve_conversational_route
from src.services.intent_router import ToolPlanContext, plan_tool_calls


@pytest.mark.asyncio
async def test_uncertain_project_source_asks_for_confirmation_before_tools(monkeypatch):
    monkeypatch.setattr(core_nodes, "get_settings", lambda: type("Settings", (), {"llm_routing_enabled": False})())
    result = await core_nodes.think_node({"query": "Trong dự án Parkwave tôi đã làm được những gì?"})

    assert "Parkwave" in result["response"]
    assert "Jira" in result["response"]
    assert result["metadata"]["source_confirmation_pending"] is True
    assert result["metadata"]["source_trace"]["confidence"] == 0.72
    assert "pending_tool_calls" not in result


@pytest.mark.asyncio
async def test_ambiguous_month_asks_for_year_before_tools(monkeypatch):
    monkeypatch.setattr(core_nodes.time_tool, "now", lambda: datetime(2026, 8, 12, tzinfo=UTC))

    result = await core_nodes.think_node({"query": "tóm tắt việc tôi đã làm trong tháng 7"})

    assert "tháng 7 năm 2026" in result["response"]
    assert result["metadata"]["temporal_trace"]["confidence"] == 0.62
    assert result["metadata"]["temporal_confirmation_pending"] is True
    assert "pending_tool_calls" not in result


@pytest.mark.asyncio
async def test_explicit_jira_followup_continues_without_confirmation_loop(monkeypatch):
    class _LLM:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages, **kwargs):
            return type("Message", (), {"content": "", "tool_calls": []})()

    monkeypatch.setattr(core_nodes, "get_llm", lambda: _LLM())
    monkeypatch.setattr(core_nodes, "get_settings", lambda: type("Settings", (), {"llm_routing_enabled": False})())
    monkeypatch.setattr(core_nodes, "_tools", lambda: [])
    result = await core_nodes.think_node(
        {
            "query": "ở Jira ấy",
            "history": [{"role": "user", "content": "Trong dự án Parkwave tôi đã làm được những gì?"}],
        }
    )

    assert result["metadata"]["source_trace"]["confidence"] == 0.97
    assert result["metadata"]["source_trace"]["candidate_sources"] == ["jira"]


@pytest.mark.parametrize(
    "source,resource",
    [
        ("gmail", "Gmail tuần này"),
        ("google_sheets", "https://docs.google.com/spreadsheets/d/abc_123/edit"),
        ("google_docs", "https://docs.google.com/document/d/doc_123/edit"),
        ("jira", "Parkwave trên Jira"),
        ("calendar", "Calendar hôm nay"),
        ("discord", "Discord chương trình"),
    ],
)
def test_explain_followup_is_source_symmetric_and_does_not_read_again(source, resource):
    route = resolve_conversational_route(
        "tại sao",
        [
            {"role": "user", "content": f"Đọc {resource}"},
            {
                "role": "assistant",
                "content": "Không đọc được.",
                "extras": {
                    "routing": {
                        "action": "READ",
                        "source": source,
                        "resource_ref": resource,
                        "status": "error",
                        "error_code": "source_unavailable",
                    }
                },
            },
        ],
    )

    assert route.action is ResolvedAction.EXPLAIN
    assert route.source == source
    assert route.resource_ref == resource
    assert route.referent == "prior_error"
    assert route.tool_policy == "no_new_tool"


def test_retry_followup_reuses_exact_source_and_resource():
    sheet_url = "https://docs.google.com/spreadsheets/d/abc_123/edit"
    route = resolve_conversational_route(
        "thử lại",
        [
            {
                "role": "assistant",
                "content": "Không đọc được.",
                "extras": {"routing": {"source": "google_sheets", "resource_ref": sheet_url, "status": "error"}},
            }
        ],
    )

    assert route.action is ResolvedAction.RETRY
    assert route.source == "google_sheets"
    assert route.resource_ref == sheet_url
    assert route.tool_policy == "selected_source_only"


def test_current_explicit_source_wins_over_previous_source():
    route = resolve_conversational_route(
        "Kiểm tra Gmail",
        [{"role": "assistant", "content": "...", "extras": {"routing": {"source": "discord"}}}],
    )

    assert route.action is ResolvedAction.SWITCH_SOURCE
    assert route.source == "gmail"
    assert route.selection_basis == "current_explicit"


def test_contextual_followup_keeps_persisted_google_sheet():
    sheet_url = "https://docs.google.com/spreadsheets/d/abc_123/edit"
    route = resolve_conversational_route(
        "ở quản lý công việc",
        [
            {
                "role": "assistant",
                "content": "Mình chưa nhận diện được cấu trúc bảng.",
                "extras": {
                    "routing": {
                        "action": "READ",
                        "source": "google_sheets",
                        "resource_ref": sheet_url,
                        "status": "error",
                    }
                },
            }
        ],
    )

    assert route.action is ResolvedAction.READ
    assert route.source == "google_sheets"
    assert route.resource_ref == sheet_url
    assert route.selection_basis == "persisted_result"
    assert route.tool_policy == "selected_source_only"
    assert route.resource_locator == "quan ly cong viec"

    calls = plan_tool_calls(
        [{"name": "list_tasks", "args": {"status": "proposed"}, "id": "model-task"}],
        ToolPlanContext(
            query="ở quản lý công việc",
            routing_context=route.resource_ref or "",
            now=datetime(2026, 8, 21, tzinfo=UTC),
            available_tools=frozenset({"list_tasks", "google_sheets_task_proposals"}),
            conversational_route=route.trace(),
        ),
    )
    assert calls == [
        {
            "name": "google_sheets_task_proposals",
            "args": {"spreadsheet_url": sheet_url, "sheet_name": "quan ly cong viec"},
            "id": "route-google-sheets",
        }
    ]


def test_deictic_followup_keeps_persisted_source():
    route = resolve_conversational_route(
        "còn trong bảng đó",
        [
            {
                "role": "assistant",
                "content": "Đã đọc bảng.",
                "extras": {
                    "routing": {
                        "action": "READ",
                        "source": "google_sheets",
                        "resource_ref": "https://docs.google.com/spreadsheets/d/abc_123/edit",
                        "status": "success",
                    }
                },
            }
        ],
    )

    assert route.action is ResolvedAction.READ
    assert route.source == "google_sheets"
    assert route.selection_basis == "persisted_result"


def test_new_unrelated_query_does_not_inherit_old_discord_source():
    route = resolve_conversational_route(
        "Giải thích sandbox là gì",
        [{"role": "assistant", "content": "...", "extras": {"routing": {"source": "discord"}}}],
    )

    assert route.action is ResolvedAction.ANSWER_FROM_CONTEXT
    assert route.source is None
    assert route.tool_policy == "no_new_tool"


def test_ambiguous_prior_multi_source_result_requires_clarification():
    route = resolve_conversational_route(
        "tại sao",
        [{"role": "assistant", "content": "...", "extras": {"routing": {"sources": ["gmail", "jira"]}}}],
    )

    assert route.action is ResolvedAction.CLARIFY
    assert route.source is None
    assert route.clarification_question


def test_all_sources_followup_continues_and_plans_all_sources():
    context = ToolPlanContext(
        query="tất cả",
        routing_context="Trong dự án Parkwave tôi đã làm được những gì? Parkwave, lấy từ tất cả nguồn",
        now=datetime(2026, 8, 12, tzinfo=UTC),
        available_tools=frozenset(
            {
                "list_tasks",
                "jira_search_issues",
                "gmail_deadline_sweep",
                "calendar_search_events",
                "discord_search_program",
            }
        ),
    )

    planned = plan_tool_calls([], context)
    assert {call["name"] for call in planned} == {
        "list_tasks",
        "jira_search_issues",
        "gmail_deadline_sweep",
        "calendar_search_events",
        "discord_search_program",
    }
