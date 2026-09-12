from types import SimpleNamespace

import pytest

from src.services.agent_stream import stream_agent_execution


class FakeGraph:
    async def astream_events(self, state, version):
        assert state == {"query": "Lịch của tôi"}
        assert version == "v2"
        root = "root-run"
        yield {
            "event": "on_chain_start",
            "name": "LangGraph",
            "run_id": root,
            "parent_ids": [],
            "metadata": {},
            "data": {"input": state},
        }
        yield {
            "event": "on_chain_start",
            "name": "think",
            "run_id": "think-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "think"},
            "data": {"input": state},
        }
        # Work-lane planning is private and must never become an SSE token.
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "run_id": "private-model-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "think", "route_lane": "work"},
            "data": {"chunk": SimpleNamespace(content="private reasoning")},
        }
        yield {
            "event": "on_chain_start",
            "name": "action",
            "run_id": "action-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "action"},
            "data": {
                "input": {"pending_tool_calls": [{"name": "calendar_search_events", "args": {"secret": "not-public"}}]}
            },
        }
        yield {
            "event": "on_chain_start",
            "name": "observe",
            "run_id": "observe-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "observe"},
            "data": {
                "input": {
                    "latest_observations": [{"name": "calendar_search_events", "output": "private calendar data"}]
                }
            },
        }
        yield {
            "event": "on_chain_start",
            "name": "respond",
            "run_id": "respond-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "respond"},
            "data": {"input": {}},
        }
        for delta in ("Bạn có ", "một cuộc hẹn."):
            yield {
                "event": "on_chat_model_stream",
                "name": "ChatOpenAI",
                "run_id": "public-model-run",
                "parent_ids": [root],
                "metadata": {"langgraph_node": "respond", "route_lane": "work"},
                "data": {"chunk": SimpleNamespace(content=delta)},
            }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "run_id": root,
            "parent_ids": [],
            "metadata": {},
            "data": {"output": {"response": "Bạn có một cuộc hẹn.", "analysis": "private"}},
        }


@pytest.mark.asyncio
async def test_stream_agent_execution_emits_safe_progress_and_real_response_tokens():
    items = [item async for item in stream_agent_execution(FakeGraph(), {"query": "Lịch của tôi"})]

    assert [item["event"] for item in items] == [
        "progress",
        "progress",
        "progress",
        "progress",
        "token",
        "token",
        "result",
    ]
    assert [item["data"] for item in items[:4]] == [
        {"phase": "thinking"},
        {"phase": "calling", "tool": "calendar_search_events"},
        {"phase": "observing", "tool": "calendar_search_events"},
        {"phase": "responding"},
    ]
    assert "".join(item["data"]["delta"] for item in items if item["event"] == "token") == ("Bạn có một cuộc hẹn.")
    serialized = repr(items)
    assert "private reasoning" not in serialized
    assert "private calendar data" not in serialized
    assert "not-public" not in serialized
    assert "analysis" not in serialized
    assert "private" not in serialized
    assert "analysis" not in items[-1]["data"]


class _GraphCoNguon:
    """Graph giả có nguồn đã gom sẵn trong metadata lúc bước vào respond."""

    NGUON = [
        {
            "tool": "discord_search_messages",
            "title": "Chốt deadline",
            "url": "https://discord.com/x/1",
            "occurred_at": "2026-08-06T10:00:00+07:00",
        }
    ]

    async def astream_events(self, state, version):
        root = "root-run"
        yield {
            "event": "on_chain_start",
            "name": "LangGraph",
            "run_id": root,
            "parent_ids": [],
            "metadata": {},
            "data": {"input": state},
        }
        yield {
            "event": "on_chain_start",
            "name": "respond",
            "run_id": "respond-run",
            "parent_ids": [root],
            "metadata": {"langgraph_node": "respond"},
            "data": {"input": {"metadata": {"sources": self.NGUON}}},
        }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "run_id": root,
            "parent_ids": [],
            "metadata": {},
            "data": {"output": {"response": "Deadline đã chốt.", "metadata": {"sources": self.NGUON}}},
        }


@pytest.mark.asyncio
async def test_nguon_di_kem_ngay_o_progress_responding():
    """Giao diện dựng được danh sách nguồn trong lúc chữ còn đang chảy."""
    items = [item async for item in stream_agent_execution(_GraphCoNguon(), {"query": "deadline"})]

    responding = next(item for item in items if item["event"] == "progress" and item["data"]["phase"] == "responding")
    assert responding["data"]["sources"] == _GraphCoNguon.NGUON


@pytest.mark.asyncio
async def test_khong_co_nguon_thi_progress_khong_co_khoa_sources():
    """Không có link nào thì không bịa ra khoá rỗng cho client phải xử lý."""
    items = [item async for item in stream_agent_execution(FakeGraph(), {"query": "Lịch của tôi"})]

    responding = next(item for item in items if item["event"] == "progress" and item["data"]["phase"] == "responding")
    assert responding["data"] == {"phase": "responding"}
