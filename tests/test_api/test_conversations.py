"""Phiên chat phải tách hẳn theo từng user.

Các test ở đây không gửi tin nhắn nên không gọi model — chúng kiểm tra quyền sở
hữu, thứ phải đúng kể cả khi nhà cung cấp model đang hỏng.
"""

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime, timedelta, timezone
from threading import Event
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db import SessionLocal
from src.models.connection import Connection
from src.models.learning import AssistantContextRef
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.user import User
from src.services.auth import decode_token


async def _dang_ky(client) -> str:
    email = f"test-conv-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    return response.json()["accessToken"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _stream_stub(result: dict, tokens: tuple[str, ...] = ()):
    async def stream(_graph, _state):
        yield {"event": "progress", "data": {"phase": "thinking"}}
        yield {
            "event": "progress",
            "data": {"phase": "calling", "tool": "discord_search_program"},
        }
        yield {
            "event": "progress",
            "data": {"phase": "observing", "tool": "discord_search_program"},
        }
        yield {"event": "progress", "data": {"phase": "responding"}}
        for delta in tokens:
            yield {"event": "token", "data": {"delta": delta}}
        yield {"event": "result", "data": result}

    return stream


@pytest.mark.asyncio
async def test_liet_ke_can_dang_nhap(client):
    response = await client.get("/api/v1/conversations")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tao_va_liet_ke_hoi_thoai_cua_minh(client):
    token = await _dang_ky(client)

    tao = await client.post("/api/v1/conversations", json={"title": "Hỏi về hạn chót"}, headers=_auth(token))
    assert tao.status_code == 201
    assert tao.json()["title"] == "Hỏi về hạn chót"
    assert tao.json()["messages"] == []

    danh_sach = await client.get("/api/v1/conversations", headers=_auth(token))
    assert danh_sach.status_code == 200
    ids = [c["id"] for c in danh_sach.json()["conversations"]]
    assert tao.json()["id"] in ids


@pytest.mark.asyncio
async def test_khong_doc_duoc_hoi_thoai_cua_nguoi_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)

    cua_a = await client.post("/api/v1/conversations", json={"title": "Riêng của A"}, headers=_auth(token_a))
    id_a = cua_a.json()["id"]

    # 404 chứ không phải 403: 403 xác nhận id đó có tồn tại.
    xem = await client.get(f"/api/v1/conversations/{id_a}", headers=_auth(token_b))
    assert xem.status_code == 404


@pytest.mark.asyncio
async def test_danh_sach_khong_lan_giua_hai_user(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)

    cua_a = await client.post("/api/v1/conversations", json={"title": "Riêng của A"}, headers=_auth(token_a))
    id_a = cua_a.json()["id"]

    danh_sach_b = await client.get("/api/v1/conversations", headers=_auth(token_b))
    assert danh_sach_b.status_code == 200
    assert id_a not in [c["id"] for c in danh_sach_b.json()["conversations"]]


@pytest.mark.asyncio
async def test_khong_xoa_duoc_hoi_thoai_cua_nguoi_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)

    cua_a = await client.post("/api/v1/conversations", json={"title": "Riêng của A"}, headers=_auth(token_a))
    id_a = cua_a.json()["id"]

    xoa = await client.delete(f"/api/v1/conversations/{id_a}", headers=_auth(token_b))
    assert xoa.status_code == 404

    # Và A vẫn còn nguyên hội thoại của mình.
    van_con = await client.get(f"/api/v1/conversations/{id_a}", headers=_auth(token_a))
    assert van_con.status_code == 200


@pytest.mark.asyncio
async def test_khong_gui_duoc_tin_nhan_vao_hoi_thoai_nguoi_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)

    cua_a = await client.post("/api/v1/conversations", json={"title": "Riêng của A"}, headers=_auth(token_a))
    id_a = cua_a.json()["id"]

    # Phải chặn ở bước kiểm chủ sở hữu, tức là trước khi kịp gọi model.
    gui = await client.post(
        f"/api/v1/conversations/{id_a}/messages",
        json={"message": "cho tôi xem tóm tắt"},
        headers=_auth(token_b),
    )
    assert gui.status_code == 404


@pytest.mark.asyncio
async def test_luu_ca_luot_hoi_lan_luot_tra_loi(client):
    """Đường thành công, agent được thay bằng bản giả nên không gọi model thật."""
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    gia_lap = AsyncMock(return_value={"response": "Có hai hạn chót.", "analysis": "đã tra nguồn"})
    with patch("src.api.conversations.agent.ainvoke", gia_lap):
        gui = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Tuần này có hạn chót nào không?"},
            headers=_auth(token),
        )

    assert gui.status_code == 200
    assert gui.json()["response"] == "Có hai hạn chót."

    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert [m["role"] for m in chi_tiet["messages"]] == ["user", "assistant"]
    assert chi_tiet["messages"][0]["content"] == "Tuần này có hạn chót nào không?"
    # Phiên chưa đặt tên thì lấy câu hỏi đầu làm tên.
    assert chi_tiet["title"].startswith("Tuần này có hạn chót")


@pytest.mark.asyncio
async def test_conversation_carries_pending_productivity_draft_to_follow_up(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    pending = {
        "status": "needs_clarification",
        "kind": "calendar_event",
        "missing_fields": ["end_or_duration"],
        "message": "Workshop kéo dài bao lâu hoặc kết thúc lúc mấy giờ?",
        "draft": {
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
        },
    }
    proposal = {
        "status": "pending_approval",
        "kind": "calendar_event",
        "message": "Hãy kiểm tra và bấm Chấp nhận.",
    }
    mocked = AsyncMock(
        side_effect=[
            {"response": pending["message"], "metadata": {"productivity_action": pending}},
            {"response": proposal["message"], "metadata": {"productivity_action": proposal}},
        ]
    )

    with patch("src.api.conversations.agent.ainvoke", mocked):
        first = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Tối nay có workshop lúc 8h, thêm vào lịch cho tôi"},
            headers=_auth(token),
        )
        second = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Kéo dài 2 tiếng"},
            headers=_auth(token),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    second_state = mocked.await_args_list[1].args[0]
    assert second_state["pending_productivity_action"] == pending
    assert second_state["history"][-1]["extras"]["productivityAction"] == pending

    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert assistant_messages[0]["extras"]["productivityAction"]["status"] == "needs_clarification"
    assert assistant_messages[1]["extras"]["productivityAction"]["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_authenticated_agent_creates_todo_only_for_current_user(client, monkeypatch):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]

    class FakeMessage:
        def __init__(self, tool_calls=None):
            self.content = "planner"
            self.tool_calls = tool_calls or []

    class TodoPlanner:
        def __init__(self):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return FakeMessage(
                    [
                        {
                            "name": "create_productivity_item",
                            "args": {
                                "kind": "todo",
                                "title": "Nộp báo cáo",
                                "deadline": "2026-08-12T17:00:00+07:00",
                            },
                            "id": "todo-create",
                        }
                    ]
                )
            return FakeMessage()

    planner = TodoPlanner()
    monkeypatch.setattr("src.agents.nodes.core_nodes.get_llm", lambda: planner)

    response = await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"message": "Tạo todo nộp báo cáo, deadline 17h ngày 12/08/2026"},
        headers=_auth(token_a),
    )

    assert response.status_code == 200
    assert "bấm Chấp nhận" in response.json()["response"]
    message_id = response.json()["messageId"]
    tasks_a = (await client.get("/api/v1/tasks", headers=_auth(token_a))).json()["tasks"]
    tasks_b = (await client.get("/api/v1/tasks", headers=_auth(token_b))).json()["tasks"]
    assert all(task["title"] != "Nộp báo cáo" for task in tasks_a)
    assert all(task["title"] != "Nộp báo cáo" for task in tasks_b)

    denied = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{message_id}/productivity-action/approve",
        headers=_auth(token_b),
    )
    assert denied.status_code == 404

    approved = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{message_id}/productivity-action/approve",
        headers=_auth(token_a),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "created"
    tasks_a = (await client.get("/api/v1/tasks", headers=_auth(token_a))).json()["tasks"]
    assert any(task["title"] == "Nộp báo cáo" for task in tasks_a)

    retried = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{message_id}/productivity-action/approve",
        headers=_auth(token_a),
    )
    assert retried.status_code == 200
    assert retried.json()["result"]["task_id"] == approved.json()["result"]["task_id"]


@pytest.mark.asyncio
async def test_reject_productivity_action_never_executes_it(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    proposal = {
        "status": "pending_approval",
        "kind": "todo",
        "approval_id": uuid.uuid4().hex,
        "message": "Chờ duyệt",
        "draft": {
            "title": "Không được tạo",
            "deadline": "2026-08-12T17:00:00+07:00",
            "description": "",
        },
        "provenance": {"title_explicit": True, "deadline_explicit": True},
    }
    turn = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={
            "role": "assistant",
            "content": "Chờ duyệt",
            "extras": {"productivityAction": proposal},
        },
        headers=_auth(token),
    )
    message_id = turn.json()["id"]

    rejected = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{message_id}/productivity-action/reject",
        headers=_auth(token),
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    approve_after_reject = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/{message_id}/productivity-action/approve",
        headers=_auth(token),
    )
    assert approve_after_reject.status_code == 409
    tasks = (await client.get("/api/v1/tasks", headers=_auth(token))).json()["tasks"]
    assert all(task["title"] != "Không được tạo" for task in tasks)


@pytest.mark.asyncio
async def test_stream_tin_nhan_gui_token_va_luu_done(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    result = {"response": "Câu trả lời đang stream.", "analysis": "đã tra nguồn"}

    with patch(
        "src.api.conversations.stream_agent_execution",
        new=_stream_stub(result, ("Câu trả lời ", "đang stream.")),
    ):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Hỏi dạng stream"},
            headers=_auth(token),
        ) as response:
            body = await response.aread()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-transform"
    text = body.decode()
    assert 'event: progress\ndata: {"phase": "thinking"}' in text
    assert '"phase": "calling", "tool": "discord_search_program"' in text
    assert '"phase": "observing", "tool": "discord_search_program"' in text
    assert '"phase": "responding"' in text
    assert '"delta": "Câu trả lời "' in text
    assert '"delta": "đang stream."' in text
    assert "event: done" in text
    assert '"response": "Câu trả lời đang stream."' in text
    assert text.index('"phase": "thinking"') < text.index('"phase": "calling"')
    assert text.index('"phase": "responding"') < text.index('"delta": "Câu trả lời "')

    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert [message["role"] for message in chi_tiet["messages"]] == ["user", "assistant"]
    assistant_id = next(message["id"] for message in chi_tiet["messages"] if message["role"] == "assistant")
    with SessionLocal() as db:
        ref = db.scalar(
            select(AssistantContextRef).where(AssistantContextRef.assistant_message_id == assistant_id)
        )
        assert ref is not None
        assert ref.memory_version_ids == []


@pytest.mark.asyncio
async def test_append_assistant_turn_persists_empty_context_ref(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "Câu trả lời dựng sẵn."},
        headers=_auth(token),
    )

    assert response.status_code == 201
    assistant_id = response.json()["id"]
    with SessionLocal() as db:
        refs = db.scalars(
            select(AssistantContextRef).where(AssistantContextRef.assistant_message_id == assistant_id)
        ).all()
        assert len(refs) == 1
        assert refs[0].memory_version_ids == []
        assert refs[0].style_version_ids == []
        assert refs[0].skill_version_ids == []


@pytest.mark.asyncio
async def test_delete_conversation_removes_context_refs(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "Sẽ bị xoá cùng hội thoại."},
        headers=_auth(token),
    )
    assistant_id = response.json()["id"]

    deleted = await client.delete(f"/api/v1/conversations/{conv_id}", headers=_auth(token))

    assert deleted.status_code == 204
    with SessionLocal() as db:
        assert db.scalar(
            select(AssistantContextRef).where(AssistantContextRef.assistant_message_id == assistant_id)
        ) is None


@pytest.mark.asyncio
async def test_stream_task_suggestion_to_ui_without_creating_task(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    suggestion_output = json.dumps(
        {
            "status": "suggested",
            "suggestions": [
                {
                    "title": "Nộp báo cáo",
                    "detail": "Gửi PDF cho mentor",
                    "due_at": "2026-08-14T09:00:00+07:00",
                    "source": "Gmail",
                }
            ],
        },
        ensure_ascii=False,
    )
    result = {
        "response": "Mình nhận ra một việc cần làm.",
        "analysis": "đã đọc nguồn",
        "observations": [{"name": "suggest_tasks", "output": suggestion_output}],
    }

    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Có việc gì từ Gmail tôi nên lưu lại không?"},
            headers=_auth(token),
        ) as response:
            text = (await response.aread()).decode()

    assert response.status_code == 200
    assert '"taskSuggestions": [{"title": "Nộp báo cáo"' in text
    assert '"source": "Gmail"' in text
    with SessionLocal() as db:
        assert db.query(Task).filter(Task.user_id == user_id, Task.title == "Nộp báo cáo").count() == 0

    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert detail["messages"][-1]["extras"]["taskSuggestions"][0]["title"] == "Nộp báo cáo"


def _google_sheet_result(*proposals: dict) -> dict:
    sheet_output = json.dumps(
        {
            "source": "Google Sheets",
            "spreadsheet_url": "https://docs.google.com/spreadsheets/d/book-123/edit",
            "sheet_name": "",
            "scanned_sheet_names": ["Backlog", "Bugs"],
            "coverage_complete": True,
            "proposals": list(proposals),
            "proposal_count": len(proposals),
            "truncated": False,
        },
        ensure_ascii=False,
    )
    suggestions = [
        {
            "title": item["title"],
            "detail": item.get("detail", ""),
            "due_at": item.get("due_at"),
            "source": item["source"],
        }
        for item in proposals
    ]
    return {
        "response": "Đã tạo các bản nháp để bạn xác nhận hoặc bỏ qua.",
        "analysis": "đã đọc Google Sheet",
        "observations": [
            {"name": "google_sheets_task_proposals", "output": sheet_output},
            {
                "name": "suggest_tasks",
                "output": json.dumps(
                    {"status": "suggested", "suggestions": suggestions},
                    ensure_ascii=False,
                ),
            },
        ],
    }


def _sheet_due_at() -> str:
    """Hạn luôn nằm trong cửa sổ tươi của card.

    `_task_drafts_from_agent_result` loại task có `due_at` cũ hơn
    `_TASK_STALE_AFTER` (7 ngày) khỏi danh sách card và dồn vào backlog count.
    Ngày cứng khiến test tự hỏng sau đúng 7 ngày, nên tính theo lúc chạy.
    """
    gmt7 = datetime.now(timezone(timedelta(hours=7))) + timedelta(days=1)
    return gmt7.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


def _sheet_proposal(*, external_key: str, title: str, source: str) -> dict:
    return {
        "row_number": 7,
        "external_key": external_key,
        "title": title,
        "detail": f"Chi tiết {title}",
        "assignee": None,
        "due_at": _sheet_due_at(),
        "all_day": False,
        "status": "Đang làm",
        "matched_user": True,
        "match_kind": "exact",
        "needs_confirmation": False,
        "clarification_question": None,
        "date_ambiguous": False,
        "source": source,
        "source_url": "https://docs.google.com/spreadsheets/d/book-123/edit#gid=1&range=A7",
    }


@pytest.mark.asyncio
async def test_stream_google_sheet_creates_confirmed_task_without_decision_card(client):
    """Chính sách tin cậy 2026-08-25: proposal chắc chắn (needs_confirmation
    = False: ngày rõ + người nhận khớp chính xác) vào thẳng danh sách với
    status confirmed; proposal mờ hồ mới ở proposed đợi duyệt."""
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    result = _google_sheet_result(
        _sheet_proposal(
            external_key="book-v1:Backlog:task-1:row-7",
            title="Khôi phục pipeline deploy tự động",
            source="Google Sheets · Backlog",
        )
    )

    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Nhận task trong Google Sheet này"},
            headers=_auth(token),
        ) as response:
            text = (await response.aread()).decode()

    assert response.status_code == 200
    assert '"taskDrafts": []' in text
    assert '"taskSuggestions": []' in text
    with SessionLocal() as db:
        task = db.scalar(
            select(Task).where(
                Task.user_id == user_id,
                Task.title == "Khôi phục pipeline deploy tự động",
            )
        )
        assert task is not None
        # Proposal chắc chắn -> confirmed ngay, chưa bao giờ đụng Google Calendar.
        assert task.status == "confirmed"
        assert task.calendar_event_id is None
        evidence = db.scalar(select(TaskEvidence).where(TaskEvidence.task_id == task.id))
        assert evidence is not None
        assert evidence.provider == "google_sheets"
        assert evidence.deep_link.endswith("#gid=1&range=A7")


@pytest.mark.asyncio
async def test_sync_google_sheet_hides_confirmed_task_from_decision_cards(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    result = _google_sheet_result(
        _sheet_proposal(
            external_key="book-v1:Backlog:task-2:row-8",
            title="Sửa banner bảo trì",
            source="Google Sheets · Backlog",
        )
    )

    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Nhận task trong Google Sheet này"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["taskDrafts"] == []
    assert payload["taskSuggestions"] == []


@pytest.mark.asyncio
async def test_google_sheet_uncertain_proposal_stays_proposed_for_review(client):
    """Proposal thiếu bằng chứng (hạn mơ hồ hoặc người nhận chỉ "gần đúng")
    phải ở proposed đợi người dùng duyệt, không tự confirmed."""
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    uncertain = _sheet_proposal(
        external_key="book-v1:Backlog:task-9:row-9",
        title="Rà soát kho hàng cuối tháng",
        source="Google Sheets · Backlog",
    )
    uncertain["needs_confirmation"] = True
    uncertain["date_ambiguous"] = True
    result = _google_sheet_result(uncertain)

    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Nhận task trong Google Sheet này"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert response.json()["taskDrafts"][0]["status"] == "proposed"
    with SessionLocal() as db:
        task = db.scalar(
            select(Task).where(
                Task.user_id == user_id,
                Task.title == "Rà soát kho hàng cuối tháng",
            )
        )
        assert task is not None
        assert task.status == "proposed"
        # Proposed không sinh mốc nhắc (FR-062/FR-090).
        reminders = db.scalars(select(Reminder).where(Reminder.task_id == task.id)).all()
        assert reminders == []


@pytest.mark.asyncio
async def test_google_sheet_retry_is_idempotent_and_same_titles_from_distinct_rows_do_not_collide(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    result = _google_sheet_result(
        _sheet_proposal(
            external_key="book-v1:Backlog:task-1:row-7",
            title="Kiểm tra deploy",
            source="Google Sheets · Backlog",
        ),
        _sheet_proposal(
            external_key="book-v1:Bugs:task-1:row-7",
            title="Kiểm tra deploy",
            source="Google Sheets · Bugs",
        ),
    )

    for _ in range(2):
        with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
            async with client.stream(
                "POST",
                f"/api/v1/conversations/{conv_id}/messages/stream",
                json={"message": "Đọc lại Sheet"},
                headers=_auth(token),
            ) as response:
                await response.aread()
        assert response.status_code == 200

    with SessionLocal() as db:
        tasks = db.scalars(
            select(Task).where(Task.user_id == user_id, Task.title == "Kiểm tra deploy")
        ).all()
        assert len(tasks) == 2
        assert len({task.cluster_key for task in tasks}) == 2
        evidence_count = db.query(TaskEvidence).filter(
            TaskEvidence.task_id.in_([task.id for task in tasks])
        ).count()
        assert evidence_count == 2


@pytest.mark.asyncio
async def test_stream_listed_proposed_tasks_as_cards_without_creating_duplicates(client):
    """Regression: câu "Tôi nên làm gì tiếp theo?" từng chỉ có danh sách chữ.

    ``list_tasks`` đã đọc các dòng proposed có thật, nên API phải gắn chính các
    dòng đó vào message để UI render thẻ xác nhận; không được gọi đường tạo mới
    rồi sinh task trùng.
    """
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    other_token = await _dang_ky(client)
    other_user_id = str(decode_token(other_token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    with SessionLocal() as db:
        owned = Task(
            user_id=user_id,
            cluster_key=f"agenda-owned-{uuid.uuid4().hex}",
            title="Nối UI chọn nguồn với danh sách nguồn thật",
            detail="Task đã được pipeline đề xuất",
            due_at=datetime.now(UTC) + timedelta(hours=1),
            status="proposed",
        )
        confirmed = Task(
            user_id=user_id,
            cluster_key=f"agenda-confirmed-{uuid.uuid4().hex}",
            title="Task đã được xác nhận nhưng vẫn cần hiện thành card",
            detail="Có thể mở lịch từ card này",
            due_at=datetime.now(UTC) + timedelta(hours=2),
            status="confirmed",
        )
        foreign = Task(
            user_id=other_user_id,
            cluster_key=f"agenda-foreign-{uuid.uuid4().hex}",
            title="Task riêng của người khác",
            detail="Không được lộ qua thẻ",
            due_at=datetime(2026, 8, 14, 9, 0, tzinfo=UTC),
            status="proposed",
        )
        db.add_all([owned, confirmed, foreign])
        db.commit()
        db.refresh(owned)
        owned_id = owned.id

    result = {
        "response": "Có một số việc cần chú ý; hãy xác nhận trên các thẻ bên dưới.",
        "analysis": "đã đọc danh sách task",
        "observations": [
            {
                "name": "list_tasks",
                "args": {"status": "all"},
                "output": "- Nối UI chọn nguồn với danh sách nguồn thật (trạng thái proposed)",
            }
        ],
    }
    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Tôi nên làm gì tiếp theo?"},
            headers=_auth(token),
        ) as response:
            text = (await response.aread()).decode()

    assert response.status_code == 200
    assert f'"taskDrafts": [{{"id": {owned_id}' in text
    assert '"title": "Nối UI chọn nguồn với danh sách nguồn thật"' in text
    assert "Task riêng của người khác" not in text

    with SessionLocal() as db:
        assert db.query(Task).filter(Task.user_id == user_id).count() == 2

    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    cards = detail["messages"][-1]["extras"]["taskDrafts"]
    assert [card["id"] for card in cards] == [owned_id]


@pytest.mark.asyncio
async def test_list_tasks_caps_proposed_cards_and_counts_hidden_tasks(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    now = datetime.now(UTC)
    with SessionLocal() as db:
        tasks = [
            Task(
                user_id=user_id,
                cluster_key=f"cap-{uuid.uuid4().hex}",
                title=f"Việc trong cửa sổ {index}",
                detail="",
                due_at=now + timedelta(hours=index),
                status="proposed",
            )
            for index in range(12)
        ]
        db.add_all(tasks)
        db.commit()
        expected_ids = [task.id for task in tasks[:8]]

    result = {
        "response": "Đây là các việc cần quyết định.",
        "observations": [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}],
    }
    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Hôm nay tôi có việc gì?"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert '"taskBacklogCount": 4' in response.text
    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    extras = detail["messages"][-1]["extras"]
    assert [card["id"] for card in extras["taskDrafts"]] == expected_ids
    assert extras["taskBacklogCount"] == 4


@pytest.mark.asyncio
async def test_list_tasks_excludes_stale_proposed_card_and_counts_it(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with SessionLocal() as db:
        db.add(
            Task(
                user_id=user_id,
                cluster_key=f"stale-{uuid.uuid4().hex}",
                title="Việc đã quá hạn lâu",
                detail="",
                due_at=datetime.now(UTC) - timedelta(days=8),
                status="proposed",
            )
        )
        db.commit()

    result = {
        "response": "Không lặp lại việc cũ.",
        "observations": [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}],
    }
    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Hôm nay tôi có việc gì?"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert response.json()["taskDrafts"] == []
    assert response.json()["taskBacklogCount"] == 1


@pytest.mark.asyncio
async def test_list_tasks_never_renders_confirmed_tasks_as_decision_cards(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with SessionLocal() as db:
        db.add(
            Task(
                user_id=user_id,
                cluster_key=f"confirmed-{uuid.uuid4().hex}",
                title="Việc đã đưa vào danh sách",
                detail="",
                due_at=datetime.now(UTC) + timedelta(hours=1),
                status="confirmed",
            )
        )
        db.commit()

    result = {
        "response": "Việc đã xác nhận không cần hỏi lại.",
        "observations": [{"name": "list_tasks", "args": {"status": "all"}, "output": "..."}],
    }
    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Liệt kê việc của tôi"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert response.json()["taskDrafts"] == []
    assert response.json()["taskBacklogCount"] == 0


@pytest.mark.asyncio
async def test_list_tasks_zero_backlog_does_not_persist_a_redundant_line(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with SessionLocal() as db:
        db.add(
            Task(
                user_id=user_id,
                cluster_key=f"zero-{uuid.uuid4().hex}",
                title="Việc cần duyệt",
                detail="",
                due_at=datetime.now(UTC) + timedelta(hours=1),
                status="proposed",
            )
        )
        db.commit()

    result = {
        "response": "Có một việc cần duyệt.",
        "observations": [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}],
    }
    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Liệt kê việc của tôi"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert response.json()["taskBacklogCount"] == 0
    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert "taskBacklogCount" not in detail["messages"][-1]["extras"]


@pytest.mark.asyncio
async def test_list_tasks_backlog_count_is_exact_union_of_stale_and_overflow(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    other_token = await _dang_ky(client)
    other_user_id = str(decode_token(other_token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    now = datetime.now(UTC)
    with SessionLocal() as db:
        recent = [
            Task(
                user_id=user_id,
                cluster_key=f"exact-recent-{uuid.uuid4().hex}",
                title=f"Việc mới {index}",
                detail="",
                due_at=now + timedelta(hours=index),
                status="proposed",
            )
            for index in range(10)
        ]
        stale = [
            Task(
                user_id=user_id,
                cluster_key=f"exact-stale-{uuid.uuid4().hex}",
                title=f"Việc cũ {index}",
                detail="",
                due_at=now - timedelta(days=8 + index),
                status="proposed",
            )
            for index in range(2)
        ]
        foreign = Task(
            user_id=other_user_id,
            cluster_key=f"exact-foreign-{uuid.uuid4().hex}",
            title="Việc cũ của người khác",
            detail="",
            due_at=now - timedelta(days=30),
            status="proposed",
        )
        db.add_all([*recent, *stale, foreign])
        db.commit()

    result = {
        "response": "Danh sách đã được bó gọn.",
        "observations": [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}],
    }
    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Liệt kê việc của tôi"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert len(response.json()["taskDrafts"]) == 8
    assert response.json()["taskBacklogCount"] == 4


@pytest.mark.asyncio
async def test_draft_task_bypasses_stale_window_and_list_cap(client):
    token = await _dang_ky(client)
    user_id = str(decode_token(token, "access"))
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    now = datetime.now(UTC)
    with SessionLocal() as db:
        listed = [
            Task(
                user_id=user_id,
                cluster_key=f"draft-cap-{uuid.uuid4().hex}",
                title=f"Việc có sẵn {index}",
                detail="",
                due_at=now + timedelta(hours=index),
                status="proposed",
            )
            for index in range(10)
        ]
        just_created = Task(
            user_id=user_id,
            cluster_key=f"draft-forced-{uuid.uuid4().hex}",
            title="Việc vừa tạo",
            detail="",
            due_at=now - timedelta(days=30),
            status="proposed",
        )
        db.add_all([*listed, just_created])
        db.commit()
        created_id = just_created.id

    result = {
        "response": "Đã tạo bản nháp.",
        "observations": [
            {"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."},
            {
                "name": "draft_task",
                "output": json.dumps({"status": "draft_created", "task_id": created_id}),
            },
        ],
    }
    with patch("src.api.conversations.agent.ainvoke", AsyncMock(return_value=result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Tạo việc mới"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    cards = response.json()["taskDrafts"]
    assert len(cards) == 9
    assert cards[0]["id"] == created_id
    assert response.json()["taskBacklogCount"] == 2


@pytest.mark.asyncio
async def test_card_list_tasks_khong_hien_jira_task_cua_nguoi_khac(client):
    token = await _dang_ky(client)
    user_id = decode_token(token, "access")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    with SessionLocal() as db:
        db.add(Connection(
            user_id=user_id,
            provider="jira",
            provider_user_id="account-me",
            status="connected_ready",
        ))
        mine = Task(
            user_id=user_id,
            cluster_key=f"jira-mine-{uuid.uuid4().hex}",
            title="Jira của tôi",
            detail="",
            assignee="account-me",
            assignee_ambiguous=False,
            status="proposed",
        )
        other = Task(
            user_id=user_id,
            cluster_key=f"jira-other-{uuid.uuid4().hex}",
            title="Jira của người khác",
            detail="",
            assignee="account-other",
            assignee_ambiguous=False,
            status="proposed",
        )
        db.add_all([mine, other])
        db.flush()
        db.add_all([
            TaskEvidence(task_id=mine.id, provider="jira", evidence_quote="mine", deep_link="jira://mine"),
            TaskEvidence(task_id=other.id, provider="jira", evidence_quote="other", deep_link="jira://other"),
        ])
        db.commit()

    result = {
        "response": "Đây là danh sách việc cần xem.",
        "observations": [{"name": "list_tasks", "args": {"status": "proposed"}, "output": "..."}],
    }
    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Tôi nên làm gì tiếp theo?"},
            headers=_auth(token),
        ) as response:
            text = (await response.aread()).decode()

    assert response.status_code == 200
    assert '"title": "Jira của tôi"' in text
    assert '"title": "Jira của người khác"' not in text


@pytest.mark.asyncio
async def test_stream_draft_task_gui_action_co_cau_truc_va_luu_vao_message(client):
    token = await _dang_ky(client)
    user_id = decode_token(token, "access")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with SessionLocal() as db:
        task = Task(
            user_id=user_id,
            cluster_key=f"agent-draft-{uuid.uuid4().hex}",
            title="Mentor Duty",
            detail="Ca trực mentor",
            due_at=datetime(2026, 8, 11, 13, 0, tzinfo=UTC),
            status="proposed",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id

    result = {
        "response": "Mình đã tạo bản nháp Mentor Duty.",
        "analysis": "",
        "observations": [
            {
                "name": "draft_task",
                "output": json.dumps({"status": "draft_created", "task_id": task_id}),
            }
        ],
    }
    with patch("src.api.conversations.stream_agent_execution", new=_stream_stub(result)):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Tạo lịch Mentor Duty"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert f'"id": {task_id}' in response.text
    assert '"title": "Mentor Duty"' in response.text
    assert '"status": "proposed"' in response.text
    assert '"calendarRequested": true' in response.text
    assert '"taskDrafts"' in response.text

    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert detail["messages"][-1]["extras"]["taskDrafts"][0]["id"] == task_id
    assert detail["messages"][-1]["extras"]["taskDrafts"][0]["calendarRequested"] is True


@pytest.mark.asyncio
async def test_oke_xac_nhan_ban_nhap_cu_khong_goi_agent_hay_discord(client):
    """Regression: ảnh production có reply cũ chưa lưu taskDrafts rồi user gõ 'oke'."""
    token = await _dang_ky(client)
    user_id = decode_token(token, "access")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "user", "content": "Tạo Mentor Duty từ 20h đến 22h"},
        headers=_auth(token),
    )
    with SessionLocal() as db:
        task = Task(
            user_id=user_id,
            cluster_key=f"legacy-draft-{uuid.uuid4().hex}",
            title="Mentor Duty",
            detail="Ca trực mentor từ 20h đến 22h",
            due_at=datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
            status="proposed",
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
        user = db.get(User, int(user_id))
        user.llm_quota_day = datetime.now(ZoneInfo(get_settings().app_timezone)).date().isoformat()
        user.llm_questions_used = get_settings().llm_questions_per_day
        db.commit()
    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={
            "role": "assistant",
            "content": "Mình đã tạo một bản nháp cho sự kiện Mentor Duty. Hãy xác nhận nhé.",
        },
        headers=_auth(token),
    )

    mocked_stream = AsyncMock()
    with patch("src.api.conversations.stream_agent_execution", mocked_stream):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "oke"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert '"phase": "responding"' in response.text
    assert '"phase": "calling"' not in response.text
    assert "Đã xác nhận task" in response.text
    assert '"status": "confirmed"' in response.text
    mocked_stream.assert_not_called()
    with SessionLocal() as db:
        assert db.get(Task, task_id).status == "confirmed"


@pytest.mark.asyncio
async def test_oke_voi_productivity_action_hien_lai_nut_khong_goi_discord(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    proposal = {
        "status": "pending_approval",
        "kind": "calendar_event",
        "approval_id": "signed-action",
        "signature": "server-signature",
        "message": "Hãy kiểm tra và bấm Chấp nhận.",
        "draft": {
            "title": "Mentor Duty",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "ends_at": "2026-08-11T22:00:00+07:00",
        },
    }
    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "user", "content": "Tạo lịch Mentor Duty 20h đến 22h"},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={
            "role": "assistant",
            "content": proposal["message"],
            "extras": {"productivityAction": proposal},
        },
        headers=_auth(token),
    )

    mocked_stream = AsyncMock()
    with patch("src.api.conversations.stream_agent_execution", mocked_stream):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "oke"},
            headers=_auth(token),
        )

    assert response.status_code == 200
    assert '"productivityAction"' in response.text
    assert '"status": "pending_approval"' in response.text
    assert '"phase": "calling"' not in response.text
    mocked_stream.assert_not_called()

    detail = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert detail["messages"][-1]["extras"]["productivityAction"] == proposal


@pytest.mark.asyncio
async def test_xac_nhan_trong_chat_khong_the_dung_task_cua_user_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)
    user_b = decode_token(token_b, "access")
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]
    with SessionLocal() as db:
        foreign_task = Task(
            user_id=user_b,
            cluster_key=f"foreign-draft-{uuid.uuid4().hex}",
            title="Task riêng của B",
            detail="Không thuộc A",
            status="proposed",
        )
        db.add(foreign_task)
        db.commit()
        db.refresh(foreign_task)
        task_id = foreign_task.id

    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "user", "content": "Chuẩn bị task"},
        headers=_auth(token_a),
    )
    await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={
            "role": "assistant",
            "content": "Ready for confirmation.",
            "extras": {"taskDrafts": [{"id": task_id, "status": "proposed"}]},
        },
        headers=_auth(token_a),
    )

    mocked = AsyncMock(return_value={"response": "Bạn muốn xác nhận việc nào?", "analysis": ""})
    with patch("src.api.conversations.agent.ainvoke", mocked):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "oke"},
            headers=_auth(token_a),
        )

    assert response.status_code == 200
    mocked.assert_awaited_once()
    with SessionLocal() as db:
        assert db.get(Task, task_id).status == "proposed"


@pytest.mark.asyncio
async def test_stream_chuan_bi_cham_khong_chan_event_loop(client, monkeypatch):
    """DB/quota wait before SSE must not starve health checks and other users."""
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    quota_entered = Event()
    release_slow_quota = Event()

    def slow_quota_check(*_args, **_kwargs):
        quota_entered.set()
        assert release_slow_quota.wait(timeout=5), "quota worker không được giải phóng"

    monkeypatch.setattr("src.api.conversations.consume_llm_question", slow_quota_check)
    monkeypatch.setattr(
        "src.api.conversations.stream_agent_execution",
        _stream_stub({"response": "Xong.", "analysis": ""}, ("Xong.",)),
    )

    started_at = time.monotonic()
    stream_task = asyncio.create_task(
        client.post(
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Kiểm tra request chậm"},
            headers=_auth(token),
        )
    )
    assert await asyncio.to_thread(quota_entered.wait, 1), "quota worker không được gọi"

    # With an async route calling sync SQL directly, the 30 ms timer resumes
    # only after slow_quota_check finishes (~250 ms). A sync route is executed
    # in FastAPI's worker pool, so the event loop remains responsive.
    assert time.monotonic() - started_at < 0.15
    health = await client.get("/health")
    assert health.status_code == 200
    release_slow_quota.set()

    response = await stream_task
    assert response.status_code == 200
    assert "event: done" in response.text


@pytest.mark.asyncio
async def test_stream_tin_nhan_gui_event_error_va_khong_luu_reply(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with patch(
        "src.api.conversations.stream_agent_execution",
        new=_stream_stub({"error": "provider unavailable"}),
    ):
        async with client.stream(
            "POST",
            f"/api/v1/conversations/{conv_id}/messages/stream",
            json={"message": "Hỏi lỗi"},
            headers=_auth(token),
        ) as response:
            body = await response.aread()

    assert response.status_code == 200
    assert "event: error" in body.decode()
    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    # Không lưu lượt trả lời hỏng, nhưng câu hỏi thì phải còn: ở nhánh stream
    # người dùng có khi đã thấy chữ hiện ra rồi mới gặp lỗi.
    assert [(m["role"], m["content"]) for m in chi_tiet["messages"]] == [("user", "Hỏi lỗi")]


@pytest.mark.asyncio
async def test_gui_tin_nhan_dung_chung_han_muc_llm_hang_ngay(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    with SessionLocal() as db:
        user = db.get(User, int(decode_token(token, "access")))
        user.llm_quota_day = datetime.now(ZoneInfo(get_settings().app_timezone)).date().isoformat()
        user.llm_questions_used = get_settings().llm_questions_per_day
        db.commit()

    mocked = AsyncMock(return_value={"response": "không được gọi", "analysis": ""})
    with patch("src.api.conversations.agent.ainvoke", mocked):
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Câu vượt quota"},
            headers=_auth(token),
        )

    assert response.status_code == 429
    mocked.assert_not_awaited()


@pytest.mark.asyncio
async def test_luot_sau_nhan_duoc_lich_su_luot_truoc(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    gia_lap = AsyncMock(return_value={"response": "Câu trả lời đầu.", "analysis": ""})
    with patch("src.api.conversations.agent.ainvoke", gia_lap):
        await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Câu hỏi đầu"},
            headers=_auth(token),
        )
        await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Còn cái kia thì sao"},
            headers=_auth(token),
        )

    lich_su = gia_lap.call_args[0][0]["history"]
    assert [t["role"] for t in lich_su] == ["user", "assistant"]
    assert lich_su[0]["content"] == "Câu hỏi đầu"
    # Câu vừa hỏi không được nằm trong lịch sử, nếu không model thấy nó hai lần.
    assert all(t["content"] != "Còn cái kia thì sao" for t in lich_su)


@pytest.mark.asyncio
async def test_agent_hong_thi_bao_loi_nhung_giu_lai_cau_hoi_cua_nguoi_dung(client):
    """Không nuốt lỗi thành câu trả lời rỗng, nhưng cũng không xoá câu người dùng gõ.

    Trước đây lượt hỏi chỉ nằm trong session nên `db.rollback()` khi agent hỏng
    xoá luôn: người dùng gõ xong, nhận báo lỗi, rồi thấy câu mình vừa gõ biến
    mất khỏi khung chat. Lỗi của trợ lý không được làm mất dữ liệu người dùng.
    """
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    gia_lap = AsyncMock(return_value={"error": "hết hạn mức của nhà cung cấp"})
    with patch("src.api.conversations.agent.ainvoke", gia_lap):
        gui = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"message": "Tuần này có gì?"},
            headers=_auth(token),
        )

    assert gui.status_code == 502
    assert "hết hạn mức" in gui.json()["detail"]

    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    # Còn đúng câu hỏi, và không có lượt trả lời rỗng nào được lưu kèm.
    assert [(m["role"], m["content"]) for m in chi_tiet["messages"]] == [("user", "Tuần này có gì?")]


@pytest.mark.asyncio
async def test_ghi_luot_dung_san_giu_nguyen_extras(client):
    """Đường Gmail briefing ghi thẳng câu trả lời kèm bằng chứng, không qua agent."""
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]

    bang_chung = {
        "summary": "Hạn chót lùi sang 29/7.",
        "evidenceItems": [{"id": "ev-1", "title": "Thông báo trong Gmail"}],
    }
    ghi = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "Đây là bản tổng hợp.", "extras": bang_chung},
        headers=_auth(token),
    )
    assert ghi.status_code == 201

    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert chi_tiet["messages"][0]["extras"] == bang_chung


@pytest.mark.asyncio
async def test_khong_ghi_duoc_luot_vao_hoi_thoai_nguoi_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]

    ghi = await client.post(
        f"/api/v1/conversations/{conv_id}/turns",
        json={"role": "assistant", "content": "chen vào"},
        headers=_auth(token_b),
    )
    assert ghi.status_code == 404


@pytest.mark.asyncio
async def test_doi_ten_va_khong_doi_ten_ho_nguoi_khac(client):
    token_a = await _dang_ky(client)
    token_b = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token_a))).json()["id"]

    doi = await client.patch(f"/api/v1/conversations/{conv_id}", json={"title": "Tên mới"}, headers=_auth(token_a))
    assert doi.status_code == 200
    assert doi.json()["title"] == "Tên mới"

    cua_nguoi_khac = await client.patch(
        f"/api/v1/conversations/{conv_id}", json={"title": "Đổi trộm"}, headers=_auth(token_b)
    )
    assert cua_nguoi_khac.status_code == 404


@pytest.mark.asyncio
async def test_danh_gia_luot_tra_loi(client):
    token = await _dang_ky(client)
    conv_id = (await client.post("/api/v1/conversations", json={}, headers=_auth(token))).json()["id"]
    luot_id = (
        await client.post(
            f"/api/v1/conversations/{conv_id}/turns",
            json={"role": "assistant", "content": "Câu trả lời"},
            headers=_auth(token),
        )
    ).json()["id"]

    danh_gia = await client.patch(
        f"/api/v1/conversations/{conv_id}/messages/{luot_id}/feedback",
        json={"feedback": "helpful"},
        headers=_auth(token),
    )
    assert danh_gia.status_code == 204

    chi_tiet = (await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))).json()
    assert chi_tiet["messages"][0]["feedback"] == "helpful"


@pytest.mark.asyncio
async def test_chu_so_huu_xoa_duoc_hoi_thoai_cua_minh(client):
    token = await _dang_ky(client)

    tao = await client.post("/api/v1/conversations", json={}, headers=_auth(token))
    conv_id = tao.json()["id"]

    xoa = await client.delete(f"/api/v1/conversations/{conv_id}", headers=_auth(token))
    assert xoa.status_code == 204

    sau_khi_xoa = await client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))
    assert sau_khi_xoa.status_code == 404
