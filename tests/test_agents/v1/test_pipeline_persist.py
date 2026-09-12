from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.agents.pipeline.nodes.persist import persist_node
from src.db import Base
from src.models.task import Task

_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture
def db():
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _message(external_id: str) -> dict:
    return {
        "id": external_id,
        "provider": "google",
        "source_id": "INBOX",
        "text": "vui lòng nộp báo cáo tuần 3",
        "sent_at": datetime.now(UTC),
        "deep_link": f"https://mail.google.com/mail/u/0/#all/{external_id}",
        "connection_id": None,
    }


def _cluster(cluster_key: str, assignee: str | None, assignee_ambiguous: bool) -> dict:
    message = _message("18f2a9c7b3e4d501")
    return {
        "cluster_key": cluster_key,
        "title": "Nộp báo cáo tuần 3",
        "due_at": datetime(2026, 8, 14, 16, 59, tzinfo=UTC),
        "ambiguous": False,
        "assignee": assignee,
        "assignee_ambiguous": assignee_ambiguous,
        "source_count": 1,
        "signal_strength": 0.333,
        "detail": "Nộp báo cáo tuần 3 trước hạn.",
        "items": [{"message": message, "evidence_quote": "vui lòng nộp báo cáo tuần 3"}],
    }


def test_persist_writes_assignee_onto_task(db):
    state = {
        "db": db,
        "user_id": "u1",
        "clusters": [_cluster("ck1", assignee="phong@student.mondaiy.vn", assignee_ambiguous=False)],
    }

    persist_node(state)

    task = db.execute(select(Task).where(Task.cluster_key == "ck1")).scalar_one()
    assert task.assignee == "phong@student.mondaiy.vn"
    assert task.assignee_ambiguous is False


def test_persist_leaves_assignee_blank_when_unresolved(db):
    state = {
        "db": db,
        "user_id": "u1",
        "clusters": [_cluster("ck2", assignee=None, assignee_ambiguous=True)],
    }

    persist_node(state)

    task = db.execute(select(Task).where(Task.cluster_key == "ck2")).scalar_one()
    assert task.assignee is None
    assert task.assignee_ambiguous is True


def test_persist_resync_updates_assignee_instead_of_duplicating_task(db):
    # FR-012/013: cluster_key trùng -> UPDATE, không tạo Task thứ 2.
    state1 = {"db": db, "user_id": "u1", "clusters": [_cluster("ck3", assignee=None, assignee_ambiguous=True)]}
    persist_node(state1)

    state2 = {
        "db": db,
        "user_id": "u1",
        "clusters": [_cluster("ck3", assignee="phong@student.mondaiy.vn", assignee_ambiguous=False)],
    }
    persist_node(state2)

    tasks = db.execute(select(Task).where(Task.cluster_key == "ck3")).scalars().all()
    assert len(tasks) == 1
    assert tasks[0].assignee == "phong@student.mondaiy.vn"
