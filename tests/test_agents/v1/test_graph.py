import os
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.agents import nodes
from src.agents.graph import agent


class _FakeMessage:
    def __init__(self, content: str = "", tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeLLM:
    """Model giả cho test đơn vị.

    Node giờ có gọi model thật, nên nếu không chặn ở đây thì test sẽ đi ra mạng:
    chậm, cần key, và gãy khi OpenRouter chặn theo hạn mức. CI cũng không có
    OPENROUTER_API_KEY nên sẽ hỏng ngay ở bước pytest.
    """

    def __init__(self, tool_calls: list | None = None, final_content: str = "trả lời giả lập"):
        self._tool_calls = tool_calls or []
        self._final_content = final_content
        self.calls = 0
        self.bind_calls = 0
        self.message_batches = []

    def bind_tools(self, tools):
        self.bind_calls += 1
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        self.message_batches.append(messages)
        if self.calls == 1:
            return _FakeMessage(content="phân tích giả lập", tool_calls=self._tool_calls)
        return _FakeMessage(content=self._final_content)


class _FakeTool:
    def __init__(self, name: str, output: str):
        self.name = name
        self.output = output
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return self.output


class _SequenceLLM:
    def __init__(self, tool_calls_by_turn: list[list[dict]]):
        self.tool_calls_by_turn = tool_calls_by_turn
        self.calls = 0
        self.message_batches = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.message_batches.append(messages)
        index = self.calls
        self.calls += 1
        calls = self.tool_calls_by_turn[index] if index < len(self.tool_calls_by_turn) else []
        return _FakeMessage(content="planner", tool_calls=calls)


class _NoToolPlanner:
    async def ainvoke(self, messages):
        return _FakeMessage(content="Có thể trả lời từ memory hội thoại")


class _MemoryAwareFakeLLM:
    """Giả lập model chỉ dùng tên cũ khi system contract cho phép rõ ràng."""

    def bind_tools(self, tools):
        return _NoToolPlanner()

    async def ainvoke(self, messages):
        system = messages[0][1]
        has_user_name = any(
            role == "human" and ("Tôi tên là An" in content or '"display_name": "An"' in content)
            for role, content in messages
        )
        if "bộ nhớ ngắn hạn" in system and has_user_name:
            return _FakeMessage(content="Bạn tên là An.")
        return _FakeMessage(content="Mình chưa biết tên bạn.")


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(tool_calls: list | None = None) -> _FakeLLM:
        llm = _FakeLLM(tool_calls)
        monkeypatch.setattr(nodes.core_nodes, "get_llm", lambda: llm)
        return llm

    return _install


@pytest.mark.asyncio
async def test_agent_basic_flow(fake_llm):
    fake_llm()
    result = await agent.ainvoke({"query": "Hello"})
    assert result["response"].startswith("Chào bạn!")


@pytest.mark.asyncio
async def test_agent_state_structure(fake_llm):
    fake_llm()
    result = await agent.ainvoke({"query": "Test query"})
    assert isinstance(result, dict)
    assert "query" in result


@pytest.mark.asyncio
async def test_agent_chay_cong_cu_khi_model_yeu_cau(fake_llm):
    fake_llm([{"name": "calculate", "args": {"expression": "2 + 3"}, "id": "c1"}])
    result = await agent.ainvoke({"query": "2 cộng 3 bằng mấy"})
    assert result["metadata"]["tool_calls"] == ["calculate"]
    assert "5" in result["context"]


@pytest.mark.asyncio
async def test_calendar_create_doc_moc_thoi_gian_tu_prompt_khong_ton_them_mot_vong(
    monkeypatch,
):
    """Mốc hiện tại nằm sẵn trong system prompt, không phải đi hỏi qua công cụ.

    Trước đây node ép `current_datetime` chạy một mình một vòng trước mọi lượt
    tạo có thời gian tương đối, tức mất trọn một lời gọi model chỉ để đọc đồng
    hồ của chính máy chủ.
    """
    action_call = {
        "name": "create_productivity_item",
        "args": {
            "kind": "calendar_event",
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "duration_minutes": 120,
        },
        "id": "create-1",
    }
    llm = _SequenceLLM([[action_call], []])
    current_time = _FakeTool("current_datetime", "Bây giờ là 11/08/2026 09:00 +07:00")
    action = _FakeTool(
        "create_productivity_item",
        {
            "status": "pending_approval",
            "kind": "calendar_event",
            "message": "Hãy kiểm tra và bấm Chấp nhận để thực hiện.",
        },
    )
    monkeypatch.setattr(nodes.core_nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [current_time, action])
    monkeypatch.setattr(
        nodes.core_nodes.time_tool,
        "now",
        lambda: datetime(2026, 8, 11, 9, 0, tzinfo=timezone(timedelta(hours=7))),
    )

    result = await agent.ainvoke({"query": "Tối nay tạo event Workshop lúc 8h kéo dài 2 tiếng"})

    assert current_time.calls == []
    assert action.calls == [action_call["args"]]
    assert result["metadata"]["tool_calls"] == ["create_productivity_item"]
    assert result["metadata"]["productivity_action"]["status"] == "pending_approval"
    assert result["response"] == "Hãy kiểm tra và bấm Chấp nhận để thực hiện."
    # Vòng think đầu tiên đã nhìn thấy mốc thật, không phải chờ tool trả về.
    assert "2026-08-11T09:00:00+07:00" in str(llm.message_batches[0])


@pytest.mark.asyncio
async def test_agent_tao_task_draft_khi_nguoi_dung_yeu_cau_dich_danh(fake_llm, monkeypatch):
    llm = fake_llm(
        [
            {
                "name": "draft_task",
                "args": {
                    "title": "Họp mentor",
                    "detail": "Chuẩn bị câu hỏi tiến độ",
                    "due_at": "2026-08-12T15:00:00+07:00",
                    "all_day": False,
                },
                "id": "draft-1",
            }
        ]
    )
    draft = _FakeTool(
        "draft_task",
        '{"status":"draft_created","task_id":42,"task_status":"proposed"}',
    )
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [draft])

    result = await agent.ainvoke({"query": "Tạo task draft họp mentor chiều mai"})

    assert len(draft.calls) == 1
    assert result["metadata"]["tool_calls"] == ["draft_task"]
    assert '"task_status":"proposed"' in result["context"]
    assert "draft_task" in str(llm.message_batches[0])


@pytest.mark.asyncio
async def test_agent_nho_ten_nguoi_dung_trong_cung_conversation(monkeypatch):
    """Regression: history có tên nhưng prompt cũ cấm dùng nên agent từ chối."""
    llm = _MemoryAwareFakeLLM()
    search = _FakeTool("discord_search_program", "không liên quan")
    monkeypatch.setattr(nodes.core_nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [search])

    result = await agent.ainvoke(
        {
            "query": "Tôi tên gì?",
            "history": [
                {"role": "user", "content": "Tôi tên là An."},
                {"role": "assistant", "content": "Chào An!"},
            ],
        }
    )

    assert result["response"] == "Bạn tên là An."
    assert search.calls == []


@pytest.mark.asyncio
async def test_agent_dung_profile_memory_khi_conversation_khong_co_history(monkeypatch):
    llm = _MemoryAwareFakeLLM()
    search = _FakeTool("discord_search_program", "không liên quan")
    monkeypatch.setattr(nodes.core_nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [search])

    result = await agent.ainvoke(
        {
            "query": "Tôi tên gì?",
            "history": [],
            "user_profile": {"display_name": "An"},
        }
    )

    assert result["response"] == "Bạn tên là An."
    assert search.calls == []


@pytest.mark.asyncio
async def test_cau_hoi_lam_gi_tiep_theo_lap_qua_observation_va_ra_du_nguon(fake_llm, monkeypatch):
    """Regression: trước đây graph dừng ngay sau current_datetime."""
    llm = fake_llm()
    tools = {
        "current_datetime": _FakeTool("current_datetime", "Bây giờ là 11/08/2026 09:07"),
        "list_tasks": _FakeTool("list_tasks", "Jira/Gmail: hoàn thiện báo cáo"),
        "discord_search_program": _FakeTool("discord_search_program", "Discord: mentor yêu cầu review"),
        "calendar_search_events": _FakeTool("calendar_search_events", "Calendar: demo 12/08"),
    }
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: list(tools.values()))
    monkeypatch.setattr(
        nodes.core_nodes.time_tool,
        "now",
        lambda: datetime(2026, 8, 11, 9, 7, tzinfo=UTC),
    )

    result = await agent.ainvoke({"query": "Tôi nên làm gì tiếp theo?"})

    # Ba lớp bằng chứng chạy chung một vòng, không còn phải đốt một vòng riêng
    # chỉ để hỏi hôm nay là ngày nào.
    assert sorted(result["metadata"]["tool_calls"]) == [
        "calendar_search_events",
        "discord_search_program",
        "list_tasks",
    ]
    assert result["metadata"]["tool_iterations"] == 1
    assert tools["current_datetime"].calls == []
    assert tools["list_tasks"].calls == [{"status": "proposed"}]
    assert tools["calendar_search_events"].calls[0]["time_from"].startswith("2026-08-11T09:07:00")
    # Think lần hai phải thấy đủ cả ba nguồn trước khi cho phép respond.
    assert "Jira/Gmail: hoàn thiện báo cáo" in str(llm.message_batches[1])
    assert "Discord: mentor yêu cầu review" in str(llm.message_batches[1])
    assert "Calendar: demo 12/08" in str(llm.message_batches[1])
    assert result["response"] == "Mình chưa có đủ bằng chứng liên quan để trả lời chắc chắn câu hỏi này."


@pytest.mark.asyncio
async def test_calendar_query_does_not_repeat_after_observation(fake_llm, monkeypatch):
    """Regression: moving ``now()`` made the deterministic fallback loop 4 times."""
    llm = fake_llm()
    calendar = _FakeTool("calendar_search_events", "Calendar: học AI lúc 09:00")
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [calendar])

    current = datetime(2026, 8, 11, 9, 0, tzinfo=UTC)

    def advancing_now():
        nonlocal current
        value = current
        current += timedelta(seconds=1)
        return value

    monkeypatch.setattr(nodes.core_nodes.time_tool, "now", advancing_now)

    result = await agent.ainvoke({"query": "lịch của tôi"})

    assert len(calendar.calls) == 1
    assert result["metadata"]["tool_calls"] == ["calendar_search_events"]
    assert result["metadata"]["tool_iterations"] == 1
    assert llm.calls == 3


@pytest.mark.asyncio
async def test_agent_bo_qua_cong_cu_khong_ton_tai(fake_llm):
    fake_llm([{"name": "khong_co_that", "args": {}, "id": "x1"}])
    result = await agent.ainvoke({"query": "gọi bừa"})
    assert result["metadata"].get("tool_calls", []) == []


@pytest.mark.asyncio
async def test_daily_overview_retrieves_today_information_streams(monkeypatch):
    """Regression: knowing today's date alone is not enough to summarize it."""
    frozen_now = datetime(2026, 8, 10, 9, 30, tzinfo=timezone(timedelta(hours=7)))
    monkeypatch.setattr(nodes.core_nodes.time_tool, "now", lambda: frozen_now)

    requested: list[tuple[str, dict]] = []

    class _FakeTool:
        def __init__(self, name: str, output: str):
            self.name = name
            self.output = output

        async def ainvoke(self, args):
            requested.append((self.name, args))
            return self.output

    tools = [
        _FakeTool("current_datetime", "Hôm nay là 10/08/2026."),
        _FakeTool(
            "discord_search_program",
            "[Discord #announcements · 10/08/2026 08:15] Demo sản phẩm lúc 16:00.",
        ),
    ]
    llm = _FakeLLM(
        [{"name": "current_datetime", "args": {}, "id": "model-only-asks-for-time"}],
        final_content="Hôm nay: Demo sản phẩm lúc 16:00.",
    )
    monkeypatch.setattr(nodes.core_nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: tools)

    result = await agent.ainvoke({"query": "Tóm tắt ngày hôm nay dựa trên các luồng thông tin."})

    assert result["response"] == "Hôm nay: Demo sản phẩm lúc 16:00."
    assert "Demo sản phẩm lúc 16:00" in result["context"]
    search_args = next(args for name, args in requested if name == "discord_search_program")
    assert search_args["since"] == "2026-08-10T00:00:00+07:00"
    assert search_args["until"] == "2026-08-11T00:00:00+07:00"


@pytest.mark.asyncio
async def test_first_person_discord_query_is_forced_to_author_locked_tool(fake_llm, monkeypatch):
    fake_llm([{"name": "discord_search_program", "args": {"query": "Jira"}, "id": "wrong-tool"}])
    personal = _FakeTool(
        "discord_search_my_messages",
        "[Discord của bạn · Lab] Tôi đã setup Jira cho nhóm.",
    )
    program = _FakeTool("discord_search_program", "Tin của nhiều người")
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [program, personal])

    result = await agent.ainvoke({"query": "Tôi đã nhắn gì về Jira trên Discord?"})

    assert result["metadata"]["tool_calls"] == ["discord_search_my_messages"]
    assert personal.calls == [{"query": "Tôi đã nhắn gì về Jira trên Discord?"}]
    assert program.calls == []


@pytest.mark.asyncio
async def test_google_sheet_url_executes_sheet_tool_instead_of_model_discord_guess(fake_llm, monkeypatch):
    sheet_url = "https://docs.google.com/spreadsheets/d/abc_123/edit"
    fake_llm([{"name": "discord_search_program", "args": {"query": sheet_url}, "id": "wrong-tool"}])
    sheet = _FakeTool("google_sheets_task_proposals", '{"source":"Google Sheets","proposals":[]}')
    discord = _FakeTool("discord_search_program", "Tin Discord không liên quan")
    monkeypatch.setattr(nodes.core_nodes, "_tools", lambda: [sheet, discord])

    result = await agent.ainvoke({"query": f"Tìm task của tôi trong {sheet_url}"})

    assert result["metadata"]["tool_calls"] == ["google_sheets_task_proposals"]
    assert sheet.calls == [{"spreadsheet_url": sheet_url}]
    assert discord.calls == []


@pytest.mark.asyncio
async def test_agent_bao_loi_khi_query_rong(fake_llm):
    fake_llm()
    result = await agent.ainvoke({"query": "   "})
    assert "Câu hỏi rỗng" in result["error"]


@pytest.mark.asyncio
async def test_agent_small_talk_skips_tool_binding(monkeypatch, fake_llm):
    monkeypatch.setattr(
        nodes.core_nodes,
        "get_settings",
        lambda: SimpleNamespace(llm_routing_enabled=True),
    )
    llm = fake_llm()

    result = await agent.ainvoke({"query": "  Chào!  "})

    assert result["metadata"]["route_lane"] == "small_talk"
    assert result["response"].startswith("Chào bạn!")
    assert llm.bind_calls == 0


@pytest.mark.skipif(
    os.getenv("RUN_LLM_LIVE") != "1",
    reason="Gọi model thật, tốn hạn mức. Bật bằng RUN_LLM_LIVE=1 khi cần kiểm tra tay.",
)
@pytest.mark.asyncio
async def test_agent_goi_model_that():
    result = await agent.ainvoke({"query": "Tính 128 * 7 + 45"})
    assert result.get("response")
    assert not result.get("error")
