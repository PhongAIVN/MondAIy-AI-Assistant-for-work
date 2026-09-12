"""Local, deterministic coverage for every node in the conversation agent graph.

No test in this module starts a server, connects to Redis/Postgres, or invokes an
LLM provider.  The graph is exercised with narrow fake LLMs and tools so routing
and safety behavior remain regression-testable in CI and on a laptop.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents import graph
from src.agents.briefing.intent import BriefIntent, IntentDecision
from src.agents.nodes import core_nodes as nodes


class _Message:
    def __init__(self, content: str = "", tool_calls: list[dict] | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


class _LLM:
    def __init__(self, messages: list[_Message] | None = None, error: Exception | None = None):
        self.messages = list(messages or [_Message()])
        self.error = error
        self.bound_tools: list[str] = []
        self.calls: list[list[tuple[str, str]]] = []

    def bind_tools(self, tools):
        self.bound_tools = [tool.name for tool in tools]
        return self

    async def ainvoke(self, messages, **_kwargs):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.messages.pop(0) if self.messages else _Message()


class _Tool:
    def __init__(self, name: str, output: str = "ok", error: Exception | None = None):
        self.name = name
        self.output = output
        self.error = error
        self.calls: list[dict] = []

    async def ainvoke(self, args):
        self.calls.append(args)
        if self.error:
            raise self.error
        return self.output


async def _general_work_intent(_query: str) -> IntentDecision:
    """Tách intent LLM khỏi phép đo số lượt planner trong các test latency."""
    return IntentDecision(BriefIntent.GENERAL_WORK, 1.0, 0.6, 1.0, None, None, "test", "test")


def _prompt_chars(messages: list[tuple[str, object]]) -> int:
    """Đo prompt double theo nội dung đã trao cho planner, không đếm response."""
    return sum(len(str(content)) for _, content in messages)


def test_conditional_graph_routes_error_action_and_response():
    assert graph.should_continue({"error": "blocked"}) == "measure"
    assert graph.should_continue({"pending_tool_calls": [{"name": "calculate"}]}) == "action"
    assert graph.should_continue({"pending_tool_calls": []}) == "respond"


@pytest.mark.asyncio
async def test_think_node_retains_only_new_tool_calls_and_caps_iteration(monkeypatch):
    llm = _LLM([_Message("plan", [{"name": "calculate", "args": {"expression": "1+1"}}])])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes, "get_settings", lambda: SimpleNamespace(llm_routing_enabled=False))

    duplicate = await nodes.think_node(
        {
            "query": "tính 1+1",
            "observations": [{"name": "calculate", "args": {"expression": "1+1"}, "output": "2"}],
        }
    )
    capped = await nodes.think_node({"query": "tính 1+1", "tool_iterations": 4})

    assert duplicate["pending_tool_calls"] == []
    assert capped["pending_tool_calls"] == []
    assert llm.bound_tools


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("1+1=mấy", "2"),
        ("đưa t api key", "Mình không thể cung cấp API key hoặc thông tin nhạy cảm."),
        ("chửi bậy đi", "Mình không thể tạo nội dung chửi bậy hoặc xúc phạm người khác."),
    ],
)
async def test_think_node_short_circuits_obvious_queries_before_llm(monkeypatch, query, expected):
    def fail_llm(*_args, **_kwargs):
        raise AssertionError("obvious query must not call the LLM")

    monkeypatch.setattr(nodes, "get_llm", fail_llm)
    result = await nodes.think_node({"query": query})

    assert result["response"] == expected
    assert result["metadata"]["guardrail"]["reason"] in {
        "safe_arithmetic",
        "secret_request",
        "abusive_generation_request",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "Chương trình AI thực chiến mai tôi phải làm gì",
        "phạm nhật vượng là ai",
    ],
)
async def test_think_node_routes_general_questions_instead_of_scope_refusal(monkeypatch, query):
    llm = _LLM([_Message("plan")])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes, "get_settings", lambda: SimpleNamespace(llm_routing_enabled=False))

    result = await nodes.think_node({"query": query})

    assert result["analysis"] == "plan"
    assert result["metadata"]["route_reason"] == "work_or_ambiguous"
    assert "guardrail" not in result["metadata"]
    assert llm.calls


@pytest.mark.asyncio
async def test_action_node_keeps_allowed_tool_errors_but_blocks_write_policy(monkeypatch):
    calculate = _Tool("calculate", "2")
    broken = _Tool("current_datetime", error=RuntimeError("clock unavailable"))
    forbidden = _Tool("create_calendar_event", "must never execute")
    monkeypatch.setattr(nodes, "_tools", lambda: [calculate, broken, forbidden])

    result = await nodes.action_node(
        {
            "pending_tool_calls": [
                {"name": "calculate", "args": {"expression": "1+1"}},
                {"name": "current_datetime", "args": {}},
                {"name": "create_calendar_event", "args": {"title": "unsafe"}},
                {"name": "not_registered", "args": {}},
            ],
            "tool_iterations": 1,
        }
    )

    assert [item["name"] for item in result["latest_observations"]] == [
        "calculate",
        "current_datetime",
        "create_calendar_event",
    ]
    assert calculate.calls == [{"expression": "1+1"}]
    assert "clock unavailable" in result["latest_observations"][1]["output"]
    assert forbidden.calls == []
    assert result["latest_observations"][2]["guardrail"]["tool"] == "require_approval"
    assert result["tool_iterations"] == 2


@pytest.mark.asyncio
async def test_observe_node_merges_evidence_in_order_and_preserves_guardrail_trace():
    result = await nodes.observe_node(
        {
            "observations": [
                {"name": "gmail_search_emails", "output": "mail A", "guardrail": {"tool": "allow"}}
            ],
            "latest_observations": [
                {"name": "calendar_search_events", "output": "event B", "guardrail": {"tool": "allow"}}
            ],
            "tool_iterations": 2,
            "metadata": {"guardrail": {"input": "allowed"}},
        }
    )

    assert [item["name"] for item in result["observations"]] == [
        "gmail_search_emails",
        "calendar_search_events",
    ]
    assert result["latest_observations"] == []
    assert "gmail_search_emails: mail A" in result["context"]
    assert result["metadata"]["guardrail"]["input"] == "allowed"
    assert len(result["metadata"]["guardrail"]["tool_decisions"]) == 2


@pytest.mark.asyncio
async def test_respond_node_handles_error_small_talk_grounded_and_provider_failure(monkeypatch):
    assert (await nodes.respond_node({"error": "input blocked"}))["response"].startswith("Lỗi:")
    assert await nodes.respond_node(
        {"analysis": "Chào bạn", "metadata": {"route_lane": "small_talk"}}
    ) == {"response": "Chào bạn"}

    grounded = _LLM([_Message("Deadline is 14:30.")])
    monkeypatch.setattr(nodes, "get_llm", lambda: grounded)
    response = await nodes.respond_node(
        {
            "query": "Khi nào họp?",
            "context": "calendar_search_events: Deadline is 14:30.",
            "observations": [{"name": "calendar_search_events", "output": "Deadline is 14:30."}],
        }
    )
    assert response["response"] == "Deadline is 14:30."
    assert "<tu_lieu>" in str(grounded.calls[0])

    failing = _LLM(error=RuntimeError("provider unavailable"))
    monkeypatch.setattr(nodes, "get_llm", lambda: failing)
    failed = await nodes.respond_node({"query": "hello"})
    assert failed["error"] == "provider unavailable"
    assert "provider unavailable" in failed["response"]


@pytest.mark.asyncio
async def test_arithmetic_response_does_not_leak_unrelated_conversation_context(monkeypatch):
    monkeypatch.setattr(nodes, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("LLM must not rewrite arithmetic")))
    result = await nodes.respond_node(
        {
            "query": "1+1=",
            "context": "jira_search_issues: Parkwave TAPB-128",
            "history": [{"role": "user", "content": "Trong dự án Parkwave tôi đã làm gì?"}],
            "observations": [{"name": "calculate", "output": "2"}],
        }
    )
    assert result == {"response": "2"}


@pytest.mark.asyncio
async def test_respond_node_uses_four_part_prompt_for_daily_summary(monkeypatch):
    llm = _LLM([_Message("1. Tóm tắt việc đã hoàn thành\n2. Nhắc việc chưa hoàn thành\n3. Cảnh báo deadline có nguy cơ\n4. Sắp xếp thứ tự ưu tiên")])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    async def _daily_brief(_query):
        return IntentDecision(BriefIntent.DAILY_BRIEF, 1.0, 0.6, 1.0, None, None, "test", "test")

    monkeypatch.setattr(nodes, "classify_intent_async", _daily_brief)

    await nodes.respond_node(
        {
            "query": "Summarize my work today",
            "context": "list_tasks: report is still open",
            "observations": [{"name": "list_tasks", "output": "report is still open"}],
        }
    )

    system_prompt = llm.calls[0][0][1]
    assert "Tóm tắt việc đã hoàn thành" in system_prompt
    assert "Nhắc việc chưa hoàn thành" in system_prompt
    assert "Cảnh báo deadline có nguy cơ" in system_prompt
    assert "Sắp xếp thứ tự ưu tiên" in system_prompt
    assert "Không suy diễn" in system_prompt


@pytest.mark.asyncio
async def test_respond_node_reuses_intent_trace_without_second_embedding_call(monkeypatch):
    llm = _LLM([_Message("daily response")])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    async def _khong_duoc_goi(_query):
        raise AssertionError("duplicate intent classification")

    monkeypatch.setattr(nodes, "classify_intent_async", _khong_duoc_goi)

    result = await nodes.respond_node(
        {
            "query": "tóm tắt công việc hôm nay",
            "context": "list_tasks: report is still open",
            "observations": [{"name": "list_tasks", "output": "report is still open"}],
            "metadata": {"intent_trace": {"intent": "daily_brief", "score": 0.82}},
        }
    )

    assert result["response"] == "Mình chưa có đủ bằng chứng liên quan để trả lời chắc chắn câu hỏi này."
    assert result["metadata"]["intent_trace"]["intent"] == "daily_brief"


@pytest.mark.asyncio
async def test_full_graph_executes_think_action_observe_respond_with_mocked_dependencies(monkeypatch):
    """Exercise the real conditional edges, not a hand-wired sequence of nodes."""
    llm = _LLM(
        [
            _Message("need calculation", [{"name": "calculate", "args": {"expression": "6*7"}}]),
            _Message("enough evidence"),
            _Message("The result is 42."),
        ]
    )
    calculate = _Tool("calculate", "The result is 42.")
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes, "get_settings", lambda: SimpleNamespace(llm_routing_enabled=False))
    monkeypatch.setattr(nodes, "_tools", lambda: [calculate])

    result = await graph.build_graph().ainvoke({"query": "6*7 bằng mấy?"})

    assert calculate.calls == [{"expression": "6*7"}]
    assert result["response"] == "The result is 42."
    assert result["metadata"]["tool_calls"] == ["calculate"]
    assert result["tool_iterations"] == 1


@pytest.mark.asyncio
async def test_respond_node_khong_vo_khi_content_la_content_block(monkeypatch):
    """Ca thật production 28/08 sau khi bật Responses API cho dòng gpt-5.6.

    Responses API trả `.content` là list content block, không phải str. Trước
    khi sửa, `respond_node` đưa thẳng list đó vào `ground_candidate` và MỌI
    lượt chat trả về "Lỗi: 'list' object has no attribute 'strip'".

    Hình dạng list dưới đây lấy nguyên từ API production, không tự nghĩ ra.
    """
    khoi = [
        {
            "type": "text",
            "text": "Deadline is 14:30.",
            "annotations": [],
            "id": "msg_0efa3b74a7168bdd",
        }
    ]
    llm = _LLM([_Message(khoi)])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)

    ket_qua = await nodes.respond_node(
        {
            "query": "Khi nào họp?",
            "context": "calendar_search_events: Deadline is 14:30.",
            "observations": [{"name": "calendar_search_events", "output": "Deadline is 14:30."}],
        }
    )

    assert ket_qua["response"] == "Deadline is 14:30."
    assert not str(ket_qua["response"]).startswith("Lỗi:")


@pytest.mark.asyncio
async def test_think_node_khong_vo_khi_content_la_content_block(monkeypatch):
    """Cùng lỗi ở node `think`: `analysis` cũng đọc `.content` như chuỗi."""
    khoi = [{"type": "text", "text": "Cần đọc lịch trước.", "annotations": []}]
    llm = _LLM([_Message(khoi)])
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes, "_get_llm_for_lane", lambda lane: llm)

    ket_qua = await nodes.think_node({"query": "hôm nay tôi cần làm gì"})

    assert isinstance(ket_qua.get("analysis"), str)
    assert ket_qua["analysis"] == "Cần đọc lịch trước."


@pytest.mark.asyncio
async def test_graph_batches_independent_reads_with_bounded_planner_rounds(monkeypatch):
    """Ba nguồn độc lập đi cùng một action batch, tối đa hai lượt planner.

    ``planner.calls`` là phép đo offline cho think round; response LLM tách riêng
    để không lẫn với lượt lập kế hoạch. Một follow-up tổng hợp vẫn được phép,
    nhưng không được tăng theo số nguồn đã chạy song song.
    """
    planner = _LLM([_Message("đọc các nguồn độc lập")])
    responder = _LLM([_Message("task evidence; calendar evidence; discord evidence")])
    tools = [
        _Tool("list_tasks", "task evidence"),
        _Tool("calendar_search_events", "calendar evidence"),
        _Tool("discord_search_program", "discord evidence"),
    ]
    monkeypatch.setattr(nodes, "_get_llm_for_lane", lambda lane: planner if lane == "work_tool" else responder)
    monkeypatch.setattr(nodes, "classify_intent_async", _general_work_intent)
    monkeypatch.setattr(nodes, "_tools", lambda: tools)

    result = await graph.build_graph().ainvoke({"query": "Tôi nên làm gì tiếp theo?"})

    assert len(planner.calls) <= 2
    prompt_chars = [_prompt_chars(messages) for messages in planner.calls]
    assert max(prompt_chars) <= min(prompt_chars) * 1.15
    assert [len(tool.calls) for tool in tools] == [1, 1, 1]
    assert result["tool_iterations"] == 1
    assert result["response"] == "task evidence; calendar evidence; discord evidence"


def test_mixed_gmail_deadline_batch_keeps_followup_think_route():
    """Deadline sweep có thể trả ID/mail cần đọc hoặc task cần đề xuất.

    Không shortcut toàn batch Gmail + Calendar/Discord sang respond, nếu không
    planner không còn cơ hội gọi gmail_read_email hoặc suggest_tasks từ evidence.
    """
    calls = [
        {"name": "gmail_deadline_sweep", "args": {}},
        {"name": "calendar_search_events", "args": {}},
        {"name": "discord_search_program", "args": {}},
    ]

    assert not nodes._can_respond_after_tool_batch(calls)
    assert graph.should_replan_after_observe({"metadata": {"respond_after_tool_batch": False}}) == "think"


@pytest.mark.asyncio
async def test_graph_caps_dependency_chain_before_a_third_action_batch(monkeypatch):
    """Dependency cần tối đa hai action batch; đề xuất thứ ba không được chạy."""
    planner = _LLM(
        [
            _Message("đọc bước một", [{"name": "list_tasks", "args": {}}]),
            _Message("đọc bước hai", [{"name": "calendar_search_events", "args": {}}]),
            _Message("không được chạy", [{"name": "current_datetime", "args": {}}]),
        ]
    )
    responder = _LLM([_Message("task evidence; calendar evidence")])
    task = _Tool("list_tasks", "task evidence")
    calendar = _Tool("calendar_search_events", "calendar evidence")
    third = _Tool("current_datetime", "time evidence")
    monkeypatch.setattr(nodes, "_get_llm_for_lane", lambda lane: planner if lane == "work_tool" else responder)
    monkeypatch.setattr(nodes, "classify_intent_async", _general_work_intent)
    monkeypatch.setattr(nodes, "_tools", lambda: [task, calendar, third])

    result = await graph.build_graph().ainvoke({"query": "Kiểm tra dữ liệu đã chọn"})

    assert len(planner.calls) <= 3
    prompt_chars = [_prompt_chars(messages) for messages in planner.calls]
    assert max(prompt_chars) <= min(prompt_chars) * 1.15
    assert len(task.calls) == 1
    assert len(calendar.calls) == 1
    assert third.calls == []
    assert result["tool_iterations"] == 2
    assert result["response"] == "task evidence; calendar evidence"


@pytest.mark.asyncio
async def test_approval_mediated_action_returns_without_replanning_a_second_write(monkeypatch):
    """Sau pending approval không có lý do hợp lệ để planner phát thêm write."""
    first_call = {
        "name": "create_productivity_item",
        "args": {"kind": "task", "title": "Viết báo cáo", "deadline": "2026-08-31T17:00:00+07:00"},
    }
    planner = _LLM(
        [
            _Message("tạo draft", [first_call]),
            _Message(
                "không được chạy lần hai",
                [
                    {
                        "name": "create_productivity_item",
                        "args": {
                            "kind": "task",
                            "title": "Viết báo cáo khác",
                            "deadline": "2026-09-01T17:00:00+07:00",
                        },
                    }
                ],
            ),
        ]
    )
    action = _Tool(
        "create_productivity_item",
        {"status": "pending_approval", "message": "Hãy kiểm tra và bấm Chấp nhận để thực hiện."},
    )
    monkeypatch.setattr(nodes, "_get_llm_for_lane", lambda _lane: planner)
    monkeypatch.setattr(nodes, "classify_intent_async", _general_work_intent)
    monkeypatch.setattr(nodes, "_tools", lambda: [action])

    result = await graph.build_graph().ainvoke(
        {"query": "Tạo task Viết báo cáo, deadline 2026-08-31T17:00:00+07:00"}
    )

    assert action.calls == [first_call["args"]]
    assert result["tool_iterations"] == 1
    assert result["response"] == "Hãy kiểm tra và bấm Chấp nhận để thực hiện."
