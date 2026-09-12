"""plan_my_day — nối planner xác định (score.py/estimate.py) vào agent.

Bốn thứ được chốt ở đây: từ chối khi chưa có scope, trả lời tử tế khi không có
việc mở, đúng thứ tự rank_tasks + hiện 3 + nói rõ còn bao nhiêu việc, và tính
xác định (gọi hai lần cùng `now` ra cùng chuỗi). Ước lượng None không được bịa
số — test riêng cho trường hợp đó.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.tools.plan_tool import plan_my_day, reset_plan_scope, set_plan_scope
from src.agents.tools.time_tool import now as tool_now
from src.db import engine
from src.models.task import Task
from src.models.task_evidence import TaskEvidence

# Cùng nguồn `now()` mà chính plan_my_day dùng nội bộ (time_tool.now), để
# due_at đặt trong test rơi đúng bucket urgency mong đợi (quá hạn/hôm
# nay/tương lai) theo múi giờ ứng dụng, không lệch múi giờ với tool.
_NOW = tool_now()


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_plan_scope()
    yield
    reset_plan_scope()


@pytest.fixture
def owner():
    user_id = f"test-plan-{uuid.uuid4()}"
    yield user_id
    with Session(engine) as db:
        task_ids = db.execute(select(Task.id).where(Task.user_id == user_id)).scalars().all()
        if task_ids:
            db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
        db.execute(delete(Task).where(Task.user_id == user_id))
        db.commit()


def _add_task(user_id: str, **kwargs) -> Task:
    defaults = dict(
        cluster_key=f"plan-test-{uuid.uuid4().hex}",
        title="Việc test",
        detail="",
        status="proposed",
        source_count=1,
        signal_strength=0.0,
        reminder_dismiss_count=0,
    )
    defaults.update(kwargs)
    row = Task(user_id=user_id, **defaults)
    with Session(engine) as db:
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def test_tu_choi_khi_chua_dat_scope():
    ket_qua = plan_my_day.invoke({})
    assert "Chưa xác định được đây là việc của ai" in ket_qua


def test_khong_co_viec_mo_thi_tra_loi_tu_te(owner):
    set_plan_scope(owner)
    ket_qua = plan_my_day.invoke({})
    assert "không có việc nào đang mở" in ket_qua.lower()
    assert "lỗi" not in ket_qua.lower()


def test_dung_thu_tu_rank_tasks_hien_3_va_noi_ro_con_lai(owner):
    set_plan_scope(owner)
    # Task quá hạn phải đứng đầu (urgency cao nhất trong score.py).
    overdue = _add_task(owner, title="Task quá hạn", due_at=_NOW - timedelta(days=2), status="confirmed")
    due_today = _add_task(owner, title="Task hôm nay", due_at=_NOW, status="proposed")
    future = _add_task(owner, title="Task tương lai xa", due_at=_NOW + timedelta(days=30), status="proposed")
    no_deadline_1 = _add_task(owner, title="Task không hạn 1", status="proposed")
    no_deadline_2 = _add_task(owner, title="Task không hạn 2", status="proposed")

    ket_qua = plan_my_day.invoke({})

    assert "5 việc đang mở" in ket_qua
    idx_overdue = ket_qua.index(overdue.title)
    idx_today = ket_qua.index(due_today.title)
    idx_future = ket_qua.index(future.title)
    assert idx_overdue < idx_today < idx_future
    # Chỉ 3 việc đầu được hiện; hai việc chưa có hạn (đứng cuối bảng xếp hạng
    # vì urgency=0) không được xuất hiện trong phần đánh số.
    assert no_deadline_1.title not in ket_qua
    assert no_deadline_2.title not in ket_qua
    assert "Còn 2 việc nữa chưa hiện" in ket_qua


def test_uoc_luong_none_khong_bi_bia_so(owner):
    set_plan_scope(owner)
    _add_task(owner, title="Task chưa ước lượng", status="proposed")

    ket_qua = plan_my_day.invoke({})

    assert "chưa ước lượng được" in ket_qua


def test_xac_dinh_goi_hai_lan_cung_du_lieu_ra_cung_chuoi(owner):
    set_plan_scope(owner)
    _add_task(owner, title="Task A", due_at=_NOW + timedelta(days=1), status="proposed")
    _add_task(owner, title="Task B", due_at=_NOW - timedelta(hours=3), status="confirmed")

    lan_1 = plan_my_day.invoke({})
    lan_2 = plan_my_day.invoke({})

    assert lan_1 == lan_2


def test_duoc_bind_read_only(owner):
    from src.agents.nodes.core_nodes import _BASE_TOOLS, _READ_ONLY_TOOLS

    assert "plan_my_day" in _READ_ONLY_TOOLS
    assert any(t.name == "plan_my_day" for t in _BASE_TOOLS)
