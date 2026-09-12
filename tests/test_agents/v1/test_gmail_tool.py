from datetime import UTC, datetime

import pytest

from src.agents.nodes import core_nodes
from src.agents.tools.gmail_bridge_tool import (
    GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS,
    gmail_bridge_read_thread,
    gmail_bridge_search,
    reset_gmail_bridge_scope,
    set_gmail_bridge_scope,
)
from src.agents.tools.gmail_tool import (
    gmail_read_email,
    gmail_search_emails,
    reset_gmail_scope,
    set_gmail_scope,
)
from src.services.intent_router import ToolPlanContext, plan_tool_calls


@pytest.mark.asyncio
async def test_gmail_bridge_requires_explicit_authenticated_scope():
    result = await gmail_bridge_search.ainvoke(
        {"query": "deadline tháng 8", "time_from": "2026-08-01", "time_to": "2026-09-01"}
    )
    assert "mailbox của ai" in result


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_gmail_scope()
    reset_gmail_bridge_scope()
    yield
    reset_gmail_scope()
    reset_gmail_bridge_scope()


@pytest.mark.asyncio
async def test_gmail_bridge_unavailable_outputs_follow_canonical_contract(monkeypatch):
    set_gmail_bridge_scope("user-1")
    monkeypatch.setattr("src.agents.tools.gmail_bridge_tool.bridge_available", lambda _user_id: False)

    search_result = await gmail_bridge_search.ainvoke(
        {"query": "deadline", "time_from": "2026-08-01", "time_to": "2026-09-01"}
    )
    read_result = await gmail_bridge_read_thread.ainvoke({"thread_id": "thread-1"})

    assert search_result == GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS["gmail_bridge_search"]
    assert read_result == GMAIL_BRIDGE_NOT_CONNECTED_OUTPUTS["gmail_bridge_read_thread"]


@pytest.mark.asyncio
async def test_gmail_search_refuses_without_authenticated_user_scope():
    result = await gmail_search_emails.ainvoke({"time_from": "2026-08-01", "time_to": "2026-08-02"})
    assert "hộp thư của ai" in result


@pytest.mark.asyncio
async def test_gmail_search_is_bounded_and_scoped_to_current_user(monkeypatch):
    set_gmail_scope("user-1")
    captured = {}

    async def fake_search(db, user_id, time_from, time_to, query=""):
        captured.update(user_id=user_id, time_from=time_from, time_to=time_to, query=query)
        return [
            {
                "id": "m-1",
                "subject": "Deadline report",
                "author_name": "Mentor",
                "sent_at": "2026-08-10T09:00:00+00:00",
                "snippet": "Nộp trước thứ Sáu.",
                "deep_link": "https://mail.google.com/mail/u/0/#all/m-1",
            }
        ]

    monkeypatch.setattr("src.services.gmail_tools.search_gmail_messages", fake_search)
    result = await gmail_search_emails.ainvoke(
        {"query": "from:mentor@example.com", "time_from": "2026-08-10", "time_to": "2026-08-17"}
    )

    assert captured["user_id"] == "user-1"
    assert captured["query"] == "from:mentor@example.com"
    assert captured["time_from"] < captured["time_to"]
    assert "Deadline report" in result
    assert "mail.google.com" in result


@pytest.mark.asyncio
async def test_gmail_read_returns_only_one_selected_message(monkeypatch):
    set_gmail_scope("user-1")
    captured = {}

    async def fake_read(db, user_id, message_id):
        captured.update(user_id=user_id, message_id=message_id)
        return {"id": "m-1", "subject": "Chi tiết", "author_id": "mentor@example.com", "text": "Nội dung đầy đủ"}

    monkeypatch.setattr("src.services.gmail_tools.read_gmail_message", fake_read)
    result = await gmail_read_email.ainvoke({"message_id": "m-1"})

    assert captured == {"user_id": "user-1", "message_id": "m-1"}
    assert "Nội dung đầy đủ" in result


def _plan(query: str, tool_calls: list[dict] | None = None) -> list[dict]:
    """Chạy luật điều hướng với mốc thời gian cố định."""
    return plan_tool_calls(
        tool_calls or [],
        ToolPlanContext(query=query, now=datetime(2026, 8, 12, 9, 0, tzinfo=UTC)),
    )


def test_gmail_question_is_forced_to_a_bounded_read_tool():
    calls = _plan("Email nào tuần này cần trả lời?")

    assert calls[0]["name"] == "gmail_deadline_sweep"
    assert calls[0]["args"]["time_from"].startswith("2026-08-10T00:00:00")
    assert calls[0]["args"]["time_to"].startswith("2026-08-17T00:00:00")


def test_gmail_question_without_diacritics_is_routed_the_same_way():
    """Regression: luật cũ khớp có dấu nên người gõ không dấu bị bỏ rơi."""
    calls = _plan("Email nao tuan nay can tra loi?")

    assert calls[0]["name"] == "gmail_deadline_sweep"
    assert calls[0]["args"]["time_from"].startswith("2026-08-10T00:00:00")
    assert calls[0]["args"]["time_to"].startswith("2026-08-17T00:00:00")


def test_gmail_write_request_is_not_routed_to_read_tool():
    # Gửi mail là hành động ghi ra ngoài, không được lặng lẽ đổi thành đọc.
    # Cũng không được lạc sang kho Discord: không có tool Gmail ghi thì
    # model phải nói rõ giới hạn thay vì bịa một kết quả không liên quan.
    assert _plan("Gửi email cho mentor") == []
    assert _plan("Gui email cho mentor") == []


def test_gmail_tools_are_bound_to_agent():
    names = {tool.name for tool in core_nodes._tools()}
    assert {"gmail_search_emails", "gmail_read_email"}.issubset(names)


def test_jira_read_tool_is_bound_to_agent():
    names = {tool.name for tool in core_nodes._tools()}
    assert "jira_search_issues" in names


def test_agenda_and_direct_mail_questions_use_the_same_gmail_sweep():
    calls = _plan("Tóm tắt công việc hôm nay cho tôi")

    gmail_calls = [call for call in calls if "gmail" in call["name"]]
    assert [call["name"] for call in gmail_calls] == ["gmail_deadline_sweep"]
    assert "query" not in gmail_calls[0]["args"]

    direct = _plan("email từ mentor@example.com")
    assert direct[0]["name"] == "gmail_deadline_sweep"
