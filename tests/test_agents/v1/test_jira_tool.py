import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.tools.jira_tool import jira_search_issues, reset_jira_scope, set_jira_scope
from src.db import engine
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.services.intent_router import ToolPlanContext, plan_tool_calls


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_jira_scope()
    yield
    reset_jira_scope()


@pytest.fixture
def owner():
    user_id = f"jira-window-{uuid.uuid4()}"
    yield user_id
    with Session(engine) as db:
        task_ids = db.execute(select(Task.id).where(Task.user_id == user_id)).scalars().all()
        if task_ids:
            db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
        db.execute(delete(Task).where(Task.user_id == user_id))
        db.commit()


def _add_jira_task(user_id: str, title: str, due_at: datetime | None, deep_link: str) -> None:
    with Session(engine) as db:
        task = Task(
            user_id=user_id,
            cluster_key=f"cluster-{uuid.uuid4()}",
            title=title,
            detail=f"Chi tiết {title}",
            due_at=due_at,
            status="proposed",
        )
        db.add(task)
        db.flush()
        db.add(
            TaskEvidence(
                task_id=task.id,
                provider="jira",
                evidence_quote=f"Jira evidence {title}",
                deep_link=deep_link,
            )
        )
        db.commit()


@pytest.mark.asyncio
async def test_jira_search_refuses_without_authenticated_scope():
    result = await jira_search_issues.ainvoke({})
    assert "Jira" in result
    assert "chưa đọc" in result


def test_jira_search_returns_only_jira_evidence_for_current_user(monkeypatch):
    class _Result:
        def all(self):
            return [
                (
                    SimpleNamespace(
                        id=7,
                        title="TAPB-128",
                        detail="Checkpoint 2",
                        status="proposed",
                        due_at=None,
                        assignee="account-other",
                        assignee_ambiguous=False,
                    ),
                    SimpleNamespace(evidence_quote="Jira issue TAPB-128", deep_link="https://acme.atlassian.net/browse/TAPB-128"),
                )
            ]

    class _Session:
        def __init__(self, engine):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement):
            return _Result()

    set_jira_scope("user-1")
    monkeypatch.setattr("src.agents.tools.jira_tool.Session", _Session)
    result = jira_search_issues.invoke({"query": "TAPB-128"})

    assert "TAPB-128" in result
    assert "atlassian.net/browse/TAPB-128" in result
    assert "phan cong Jira: account-other" in result
    assert "chi task cua ban moi vao danh sach can duyet/len lich" in result
    assert "Ngoài ra" not in result


def test_jira_window_loai_task_ngoai_han_nhung_bao_task_chua_co_han_va_nguon(owner):
    set_jira_scope(owner)
    _add_jira_task(owner, "Trong cửa sổ", datetime(2026, 8, 28, 9, tzinfo=UTC), "https://jira/inside")
    for index in range(5):
        _add_jira_task(
            owner,
            f"Ngoài cửa sổ {index}",
            datetime(2026, 9, 10 + index, 9, tzinfo=UTC),
            f"https://jira/outside-{index}",
        )
    _add_jira_task(owner, "Đúng biên cuối", datetime(2026, 9, 3, 9, tzinfo=UTC), "https://jira/end-boundary")
    _add_jira_task(owner, "Chưa hạn một", None, "https://jira/no-deadline")
    _add_jira_task(owner, "Chưa hạn hai", None, "https://jira/no-deadline-2")

    before = jira_search_issues.invoke({"query": ""})
    planned = plan_tool_calls(
        [],
        ToolPlanContext(
            query="trước khi họp mentor duty cần làm gì",
            now=datetime(2026, 8, 27, 9, tzinfo=UTC),
        ),
    )
    jira_args = next(call["args"] for call in planned if call["name"] == "jira_search_issues")
    after = jira_search_issues.invoke(jira_args)

    assert "Trong cửa sổ" in after
    assert "Ngoài cửa sổ" not in after
    assert "Đúng biên cuối" not in after
    assert "Chưa hạn một" not in after
    assert "Chưa hạn hai" not in after
    assert "Ngoài ra còn 2 issue Jira chưa có deadline" in after
    assert "xem tại https://jira/no-deadline" in after
    assert "Ngoài cửa sổ 4" in before
    assert "Đúng biên cuối" in before
    assert "Chưa hạn hai" in before
    assert "Ngoài ra" not in before
    assert len(after) * 2 < len(before)


def test_jira_window_noi_ro_khi_task_chua_han_khong_co_link_that(owner):
    set_jira_scope(owner)
    _add_jira_task(owner, "Chưa hạn thiếu link", None, "")

    result = jira_search_issues.invoke(
        {
            "query": "",
            "due_after": "2026-08-27T00:00:00+00:00",
            "due_before": "2026-08-30T00:00:00+00:00",
        }
    )

    assert "Ngoài ra còn 1 issue Jira chưa có deadline" in result
    assert "không có link Jira thật trong dữ liệu đã đồng bộ" in result
