import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.tools import productivity_tool as module
from src.agents.tools.productivity_tool import (
    create_productivity_item,
    execute_productivity_action,
    reset_productivity_action_scope,
    set_productivity_action_scope,
)
from src.db import engine
from src.models.connection import Connection
from src.models.task import Task


@pytest.fixture(autouse=True)
def _reset_scope():
    reset_productivity_action_scope()
    yield
    reset_productivity_action_scope()


@pytest.fixture
def owner():
    user_id = f"productivity-{uuid.uuid4()}"
    yield user_id
    with Session(engine) as db:
        db.execute(delete(Task).where(Task.user_id == user_id))
        db.execute(delete(Connection).where(Connection.user_id == user_id))
        db.commit()


def _connect_google(owner: str, scopes: str) -> None:
    with Session(engine) as db:
        db.add(
            Connection(
                user_id=owner,
                provider="google",
                status="connected",
                scopes=scopes,
            )
        )
        db.commit()


@pytest.mark.asyncio
async def test_calendar_event_asks_for_explicit_duration_instead_of_guessing(owner):
    set_productivity_action_scope(
        owner,
        request_id="turn-1",
        current_query="Tối nay tôi có workshop lúc 8h, hãy thêm vào lịch cho tôi",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
        }
    )

    assert result["status"] == "needs_clarification"
    assert result["missing_fields"] == ["end_or_duration"]
    assert "kéo dài bao lâu" in result["question"]


@pytest.mark.asyncio
async def test_bare_add_to_calendar_is_valid_intent_and_asks_for_missing_fields(owner):
    set_productivity_action_scope(
        owner,
        request_id="bare-calendar-turn",
        current_query="Thêm vào lịch cho tôi",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            # Model không được biến "tối nay" thành một giờ mặc định.
            "starts_at": "2026-08-29T20:00:00+07:00",
            "duration_minutes": 60,
        }
    )

    assert result["status"] == "needs_clarification"
    assert result["missing_fields"] == ["title", "starts_at", "end_or_duration"]
    assert "Mình hiểu bạn muốn thêm một sự kiện vào lịch" in result["question"]
    assert result["draft"]["title"] == ""


@pytest.mark.asyncio
async def test_calendar_request_prefills_user_words_and_asks_only_for_exact_time(owner):
    set_productivity_action_scope(
        owner,
        request_id="natural-calendar-turn",
        current_query="điện thoại đặt lịch cho tôi tối nay học với mentor",
    )

    result = await create_productivity_item.ainvoke({"kind": "calendar_event"})

    assert result["status"] == "needs_clarification"
    assert result["draft"]["title"] == "Học với mentor"
    assert result["missing_fields"] == ["starts_at", "end_or_duration"]
    assert result["question"] == (
        "Tối nay, “Học với mentor” bắt đầu lúc mấy giờ, "
        "và kéo dài bao lâu hoặc kết thúc lúc mấy giờ?"
    )


@pytest.mark.asyncio
async def test_reminder_request_prefills_title_and_asks_natural_deadline_follow_up(owner):
    set_productivity_action_scope(
        owner,
        request_id="natural-reminder-turn",
        current_query="nhắc tôi ngày mai nộp báo cáo P004",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "todo",
            # Tương tự, "ngày mai" không đồng nghĩa 09:00.
            "deadline": "2026-08-30T09:00:00+07:00",
        }
    )

    assert result["status"] == "needs_clarification"
    assert result["draft"]["title"] == "Nộp báo cáo P004"
    assert result["missing_fields"] == ["deadline"]
    assert result["question"] == "Ngày mai bạn muốn được nhắc “Nộp báo cáo P004” lúc mấy giờ?"


@pytest.mark.asyncio
async def test_start_written_as_eight_hours_is_not_mistaken_for_duration(owner):
    set_productivity_action_scope(
        owner,
        request_id="turn-start-hour",
        current_query="Tối nay tạo event workshop lúc 8 giờ",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "duration_minutes": 60,
        }
    )

    assert result["status"] == "needs_clarification"
    assert result["missing_fields"] == ["end_or_duration"]


@pytest.mark.asyncio
async def test_model_cannot_invent_missing_title(owner):
    set_productivity_action_scope(
        owner,
        request_id="turn-no-title",
        current_query="Hãy thêm vào lịch tối nay lúc 20h, kéo dài 1 tiếng",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Workshop bí mật",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "duration_minutes": 60,
        }
    )

    assert result["status"] == "needs_clarification"
    assert result["missing_fields"] == ["title"]
    assert "tên nội dung" in result["question"]
    assert result["draft"]["title"] == ""


@pytest.mark.asyncio
async def test_follow_up_proposes_then_approval_creates_calendar_event_once(owner, monkeypatch):
    _connect_google(
        owner,
        "https://www.googleapis.com/auth/calendar.events",
    )
    calls: list[dict] = []

    class FakeCalendarConnector:
        def __init__(self, connection, db):
            assert connection.user_id == owner

        async def create_event(self, **kwargs):
            calls.append(kwargs)
            return {"id": kwargs["event_id"], "htmlLink": "https://calendar.test/event"}

    monkeypatch.setattr(module, "CalendarConnector", FakeCalendarConnector)
    set_productivity_action_scope(
        owner,
        request_id="turn-1",
        current_query="Tối nay tôi có workshop lúc 8h, hãy thêm vào lịch cho tôi",
    )
    pending = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
        }
    )

    set_productivity_action_scope(
        owner,
        request_id="turn-2",
        current_query="Khoảng 2 tiếng",
        pending_action=pending,
    )
    proposal = await create_productivity_item.ainvoke({"kind": "calendar_event", "duration_minutes": 120})

    assert proposal["status"] == "pending_approval"
    assert calls == []
    created = await execute_productivity_action(owner, proposal)

    assert created["status"] == "created"
    assert created["result"]["calendar_event_id"]
    assert len(calls) == 1
    assert calls[0]["title"] == "Workshop"
    assert calls[0]["ends_at"].hour == 22


@pytest.mark.asyncio
async def test_end_time_given_via_the_clarification_form_colon_format_is_recognized(owner):
    set_productivity_action_scope(
        owner,
        request_id="colon-form-turn-1",
        current_query="Thêm sự kiện đi ăn với người yêu vào lịch",
    )
    pending = await create_productivity_item.ainvoke(
        {"kind": "calendar_event", "title": "Đi ăn với người yêu"}
    )
    assert pending["status"] == "needs_clarification"

    # Đúng định dạng ProductivityApprovalCard.submitClarification gửi lại khi
    # người dùng điền form nháp — "kết thúc: HH:MM:SS ..." có dấu hai chấm.
    # Trước khi sửa, provenance coi đây là CHƯA có bằng chứng giờ kết thúc và
    # hỏi lại vô hạn dù ô Kết thúc trên form đã có giá trị thật.
    set_productivity_action_scope(
        owner,
        request_id="colon-form-turn-2",
        current_query=(
            "tiêu đề: Đi ăn với người yêu; bắt đầu: 18:00:00 30/8/2026; "
            "kết thúc: 20:18:00 30/8/2026; người tham dự: lyn.nhi3010@gmail.com"
        ),
        pending_action=pending,
    )
    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Đi ăn với người yêu",
            "starts_at": "2026-08-30T18:00:00+07:00",
            "ends_at": "2026-08-30T20:18:00+07:00",
            "attendees": ["lyn.nhi3010@gmail.com"],
        }
    )

    assert result["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_calendar_event_with_attendees_passes_them_to_google_calendar(owner, monkeypatch):
    _connect_google(owner, "https://www.googleapis.com/auth/calendar.events")
    calls: list[dict] = []

    class FakeCalendarConnector:
        def __init__(self, connection, db):
            assert connection.user_id == owner

        async def create_event(self, **kwargs):
            calls.append(kwargs)
            return {"id": kwargs["event_id"], "htmlLink": "https://calendar.test/event"}

    monkeypatch.setattr(module, "CalendarConnector", FakeCalendarConnector)
    set_productivity_action_scope(
        owner,
        request_id="turn-attendees",
        current_query="Thêm cuộc họp rà soát tiến độ lúc 15h chiều mai kéo dài 1 tiếng vào lịch, mời lan@gmail.com và minh@gmail.com",
    )
    proposal = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Họp rà soát tiến độ",
            "starts_at": "2026-08-29T15:00:00+07:00",
            "duration_minutes": 60,
            "attendees": ["lan@gmail.com", "minh@gmail.com"],
        }
    )

    assert proposal["status"] == "pending_approval"
    assert proposal["draft"]["attendees"] == ["lan@gmail.com", "minh@gmail.com"]

    created = await execute_productivity_action(owner, proposal)
    assert created["status"] == "created"
    assert calls[0]["attendees"] == ["lan@gmail.com", "minh@gmail.com"]


@pytest.mark.asyncio
async def test_a_bare_name_passed_as_an_attendee_is_dropped_not_sent_to_google(owner, monkeypatch):
    # Docstring của create_productivity_item dặn model đừng đoán email từ tên
    # gọi, nhưng model vẫn có thể làm vậy ("Endy" thay vì một email thật).
    # Google Calendar trả 400 cho CẢ sự kiện chỉ vì một attendee sai định
    # dạng — attendee không hợp lệ phải bị lọc bỏ, sự kiện vẫn phải tạo được.
    _connect_google(owner, "https://www.googleapis.com/auth/calendar.events")
    calls: list[dict] = []

    class FakeCalendarConnector:
        def __init__(self, connection, db):
            assert connection.user_id == owner

        async def create_event(self, **kwargs):
            calls.append(kwargs)
            return {"id": kwargs["event_id"], "htmlLink": "https://calendar.test/event"}

    monkeypatch.setattr(module, "CalendarConnector", FakeCalendarConnector)
    set_productivity_action_scope(
        owner,
        request_id="turn-bad-attendee",
        current_query="Thêm cuộc họp rà soát tiến độ lúc 15h chiều mai kéo dài 1 tiếng vào lịch, mời Endy",
    )
    proposal = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Họp rà soát tiến độ",
            "starts_at": "2026-08-29T15:00:00+07:00",
            "duration_minutes": 60,
            "attendees": ["Endy"],
        }
    )

    assert proposal["status"] == "pending_approval"
    assert proposal["draft"]["attendees"] == []

    created = await execute_productivity_action(owner, proposal)
    assert created["status"] == "created"
    assert calls[0]["attendees"] == []


@pytest.mark.asyncio
async def test_attendees_survive_a_clarification_round_trip(owner, monkeypatch):
    _connect_google(owner, "https://www.googleapis.com/auth/calendar.events")
    calls: list[dict] = []

    class FakeCalendarConnector:
        def __init__(self, connection, db):
            assert connection.user_id == owner

        async def create_event(self, **kwargs):
            calls.append(kwargs)
            return {"id": kwargs["event_id"], "htmlLink": "https://calendar.test/event"}

    monkeypatch.setattr(module, "CalendarConnector", FakeCalendarConnector)
    set_productivity_action_scope(
        owner,
        request_id="attendees-turn-1",
        current_query="Thêm cuộc họp rà soát tiến độ lúc 15h chiều mai vào lịch, mời lan@gmail.com tham gia",
    )
    pending = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Họp rà soát tiến độ",
            "starts_at": "2026-08-29T15:00:00+07:00",
            "attendees": ["lan@gmail.com"],
        }
    )
    assert pending["status"] == "needs_clarification"
    assert pending["draft"]["attendees"] == ["lan@gmail.com"]

    # Lượt trả lời câu hỏi làm rõ không nhắc lại attendees — phải giữ nguyên
    # từ draft trước, không được coi như người dùng đã rút lại lời mời.
    set_productivity_action_scope(
        owner,
        request_id="attendees-turn-2",
        current_query="Kéo dài 1 tiếng",
        pending_action=pending,
    )
    proposal = await create_productivity_item.ainvoke({"kind": "calendar_event", "duration_minutes": 60})

    assert proposal["status"] == "pending_approval"
    assert proposal["draft"]["attendees"] == ["lan@gmail.com"]
    await execute_productivity_action(owner, proposal)
    assert calls[0]["attendees"] == ["lan@gmail.com"]


@pytest.mark.asyncio
async def test_task_requires_deadline_then_persists_confirmed_task(owner):
    set_productivity_action_scope(
        owner,
        request_id="task-turn-1",
        current_query="Hãy tạo task nộp báo cáo cho tôi",
    )
    pending = await create_productivity_item.ainvoke({"kind": "task", "title": "Nộp báo cáo"})
    assert pending["missing_fields"] == ["deadline"]

    set_productivity_action_scope(
        owner,
        request_id="task-turn-2",
        current_query="Deadline ngày mai lúc 17h",
        pending_action=pending,
    )
    proposal = await create_productivity_item.ainvoke({"kind": "task", "deadline": "2026-08-12T17:00:00+07:00"})

    assert proposal["status"] == "pending_approval"
    with Session(engine) as db:
        assert db.execute(select(Task).where(Task.user_id == owner)).scalar_one_or_none() is None

    result = await execute_productivity_action(owner, proposal)
    assert result["status"] == "created"
    with Session(engine) as db:
        task = db.execute(
            select(Task).where(Task.user_id == owner, Task.id == result["result"]["task_id"])
        ).scalar_one()
        assert task.title == "Nộp báo cáo"
        assert task.status == "confirmed"
        assert task.ambiguous is False
        assert task.cluster_key.startswith("agent-")
        assert len(task.cluster_key) <= 64


@pytest.mark.asyncio
async def test_approval_rejects_a_tampered_server_draft(owner):
    set_productivity_action_scope(
        owner,
        request_id="signed-task",
        current_query="Tạo todo nộp báo cáo, deadline ngày mai lúc 17h",
    )
    proposal = await create_productivity_item.ainvoke(
        {
            "kind": "todo",
            "title": "Nộp báo cáo",
            "deadline": "2026-08-12T17:00:00+07:00",
        }
    )
    proposal["draft"]["title"] = "Nội dung đã bị sửa"

    with pytest.raises(ValueError, match="Chữ ký action không hợp lệ"):
        await execute_productivity_action(owner, proposal)


@pytest.mark.asyncio
async def test_tool_denies_model_initiated_write_without_user_command(owner):
    set_productivity_action_scope(
        owner,
        request_id="read-turn",
        current_query="Lịch của tôi tối nay có gì?",
    )

    result = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Sự kiện do model tự nghĩ",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "duration_minutes": 60,
        }
    )

    assert result["status"] == "error"
    # Kiểm HÀNH VI (đã chặn) chứ không kiểm nguyên văn: câu cũ đổ lỗi cho người
    # dùng và đã được đổi. Điều phải giữ là câu trả lời nói được cách gỡ, vì
    # `respond_node` bê thẳng nó ra làm câu trả lời cuối cho người dùng.
    assert "chưa tạo" in result["message"]
    assert "tạo task" in result["message"], "câu từ chối phải chỉ ra cách người dùng nói lại"


@pytest.mark.asyncio
async def test_calendar_write_denied_when_google_scope_is_read_only(owner):
    _connect_google(
        owner,
        "https://www.googleapis.com/auth/calendar.readonly",
    )
    set_productivity_action_scope(
        owner,
        request_id="turn-readonly",
        current_query="Tạo event workshop lúc 20h kéo dài 1 tiếng",
    )

    proposal = await create_productivity_item.ainvoke(
        {
            "kind": "calendar_event",
            "title": "Workshop",
            "starts_at": "2026-08-11T20:00:00+07:00",
            "duration_minutes": 60,
        }
    )

    assert proposal["status"] == "pending_approval"
    result = await execute_productivity_action(owner, proposal)
    assert result["status"] == "error"
    assert "chỉ có quyền đọc" in result["message"]
