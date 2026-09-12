"""Task tạo từ chat phải sinh mốc nhắc, như khi confirm thủ công.

Ca thật 28/08: Thái gõ "nhắn tôi 3h40 hồi quota AI". Ngay cả sau khi gỡ cổng
regex và thêm mốc `at_time`, người dùng vẫn KHÔNG nhận được lời nhắc nào — vì
`create_productivity_item` tạo task `confirmed` rồi dừng, không gọi
`generate_default_reminders`.

Đường confirm thủ công (`src/api/tasks.py`) và đường pipeline
(`src/agents/pipeline/nodes/persist.py`) đều có gọi. Chỉ đường chat thiếu, và
không có vòng quét nền nào bù. Task nằm im trong DB tới lúc quá hạn.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.tools.productivity_tool import (
    create_productivity_item,
    execute_productivity_action,
    reset_productivity_action_scope,
    set_productivity_action_scope,
)
from src.db import engine
from src.models.reminder import Reminder
from src.models.task import Task


@pytest.fixture
def owner(request):
    return f"reminders-{request.node.name}"


@pytest.fixture(autouse=True)
def _reset_scope():
    yield
    reset_productivity_action_scope()


@pytest.mark.asyncio
async def test_tao_task_tu_chat_thi_sinh_moc_nhac(owner) -> None:
    han = datetime.now(UTC) + timedelta(hours=3)
    set_productivity_action_scope(
        owner,
        request_id=f"req-{owner}",
        current_query="nhắn tôi lúc 3h40 hỏi quota AI",
    )

    # Tool chỉ CHUẨN BỊ action; task chỉ được tạo sau khi người dùng bấm
    # Chấp nhận. Test phải đi qua đúng luồng đó, không gọi tắt hàm bên trong.
    de_xuat = await create_productivity_item.ainvoke(
        {
            "kind": "task",
            "title": "hỏi quota AI",
            "deadline": han.isoformat(),
        }
    )
    assert de_xuat["status"] == "pending_approval", de_xuat

    ket_qua = await execute_productivity_action(owner, de_xuat)
    assert ket_qua["status"] == "created", ket_qua
    task_id = ket_qua["result"]["task_id"]

    with Session(engine) as db:
        moc = sorted(
            r.milestone
            for r in db.execute(
                select(Reminder).where(Reminder.task_id == task_id, Reminder.kind == "task_due")
            ).scalars()
        )

    assert moc, (
        "Task tạo từ chat không sinh mốc nhắc nào. Người dùng xin được nhắc "
        "và sẽ không bao giờ được nhắc — không có vòng quét nền nào bù."
    )
    assert "at_time" in moc, f"thiếu mốc bắn đúng giờ người dùng xin; có: {moc}"


@pytest.mark.asyncio
async def test_moc_at_time_bang_dung_han_nguoi_dung_xin(owner) -> None:
    """Không được trừ lùi: xin nhắc lúc X thì phải có mốc đúng X."""
    han = (datetime.now(UTC) + timedelta(hours=5)).replace(microsecond=0)
    set_productivity_action_scope(
        owner, request_id=f"req-{owner}", current_query="nhắc tôi lúc 20h nộp báo cáo"
    )

    de_xuat = await create_productivity_item.ainvoke(
        {"kind": "task", "title": "nộp báo cáo", "deadline": han.isoformat()}
    )
    assert de_xuat["status"] == "pending_approval", de_xuat
    ket_qua = await execute_productivity_action(owner, de_xuat)
    assert ket_qua["status"] == "created", ket_qua

    with Session(engine) as db:
        task = db.get(Task, ket_qua["result"]["task_id"])
        at_time = db.execute(
            select(Reminder).where(
                Reminder.task_id == task.id,
                Reminder.kind == "task_due",
                Reminder.milestone == "at_time",
            )
        ).scalar_one()

    assert at_time.scheduled_at.replace(tzinfo=UTC) == task.due_at.replace(tzinfo=UTC)
