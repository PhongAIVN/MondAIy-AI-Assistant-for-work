from datetime import datetime
from zoneinfo import ZoneInfo

from src.agents.tools.planner_workspace_tool import _minute, reset_planner_workspace_scope, set_planner_workspace_scope
from src.services.intent_router.tool_planning import ToolPlanContext, plan_tool_calls

ICT = ZoneInfo("Asia/Ho_Chi_Minh")


def test_planner_clock_parser_rejects_ambiguous_time():
    assert _minute("16:05") == 965
    try:
        _minute("chiều")
    except ValueError:
        pass
    else:
        raise AssertionError("Giờ mơ hồ không được đưa vào Workday Contract")


def test_chat_planning_query_forces_week_planner_tool():
    context = ToolPlanContext(
        query="Lên kế hoạch tuần này cho tôi",
        routing_context="Lên kế hoạch tuần này cho tôi",
        now=datetime(2026, 8, 29, 9, tzinfo=ICT),
        available_tools=frozenset({"generate_planner_plan"}),
    )
    calls = plan_tool_calls([], context)
    assert calls == [{"name": "generate_planner_plan", "args": {"days": 7}, "id": "auto-planner-workspace"}]


def test_chat_can_set_happy_time_when_the_user_states_both_times():
    context = ToolPlanContext(
        query="Đặt Happy Time từ 16:00 đến 17:00",
        routing_context="Đặt Happy Time từ 16:00 đến 17:00",
        now=datetime(2026, 8, 29, 9, tzinfo=ICT),
        available_tools=frozenset({"configure_planner_workday"}),
    )
    assert plan_tool_calls([], context) == [{
        "name": "configure_planner_workday",
        "args": {"happy_time_start": "16:00", "happy_time_end": "17:00", "happy_time_enabled": True},
        "id": "auto-planner-config",
    }]


def test_planner_scope_is_explicit_and_resettable():
    set_planner_workspace_scope("user-1")
    reset_planner_workspace_scope()
