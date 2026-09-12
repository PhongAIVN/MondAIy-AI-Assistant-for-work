import json
import uuid
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.tools.task_tool import draft_task, reset_task_scope, set_task_scope
from src.db import engine
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.telemetry import AuditEvent
from src.services import task_dedup


@pytest.fixture(autouse=True)
def _reset_scope():
    reset_task_scope()
    yield
    reset_task_scope()


@pytest.fixture
def owner():
    user_id = f"task-dedup-{uuid.uuid4()}"
    yield user_id
    with Session(engine) as db:
        task_ids = db.scalars(select(Task.id).where(Task.user_id == user_id)).all()
        if task_ids:
            db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
        db.execute(delete(Task).where(Task.user_id == user_id))
        db.execute(delete(AuditEvent).where(AuditEvent.actor_id == user_id))
        db.commit()


def _settings(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        task_dedup_semantic_enabled=enabled,
        task_dedup_embedding_model="text-embedding-3-small",
        task_dedup_fuzzy_threshold=0.95,
        task_dedup_semantic_threshold=0.92,
        task_dedup_embedding_timeout_seconds=2.0,
        task_dedup_due_proximity_hours=6.0,
        task_dedup_candidate_limit=50,
        openai_api_key="test-key",
    )


def _draft(title: str, due_at: datetime) -> dict:
    return json.loads(draft_task.invoke({"title": title, "due_at": due_at.isoformat()}))


def test_exact_same_title_and_due_reuses_task(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 16, 44, tzinfo=timezone(timedelta(hours=7)))
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        task_dedup,
        "_embed_task_titles",
        lambda _titles: pytest.fail("Exact match không được gọi embedding"),
    )

    first = _draft("Nộp báo cáo", due_at)
    second = _draft("  NỘP   BÁO CÁO ", due_at.astimezone(UTC))

    assert second["status"] == "draft_created"
    assert second["deduplicated"] is True
    assert second["task_id"] == first["task_id"]
    assert second["dedup_layer"] == "exact"
    assert second["similarity_score"] == 1.0
    with Session(engine) as db:
        assert len(db.scalars(select(Task).where(Task.user_id == owner)).all()) == 1


def test_same_title_days_apart_keeps_recurring_tasks_separate(owner, monkeypatch):
    set_task_scope(owner)
    first_due = datetime(2026, 8, 24, 19, 0, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    monkeypatch.setattr(task_dedup, "_embed_task_titles", lambda _titles: [[1.0, 0.0], [1.0, 0.0]])

    first = _draft("Làm toán", first_due)
    second = _draft("Làm toán", first_due + timedelta(days=1))

    assert second["status"] == "draft_created"
    assert second["deduplicated"] is False
    assert second["task_id"] != first["task_id"]
    with Session(engine) as db:
        assert len(db.scalars(select(Task).where(Task.user_id == owner)).all()) == 2


def test_nearly_identical_title_uses_guarded_fuzzy_layer(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        task_dedup,
        "_embed_task_titles",
        lambda _titles: pytest.fail("Fuzzy match chắc chắn không được gọi embedding"),
    )

    first = _draft("Viết báo cáo tuần", due_at)
    second = _draft("Viết báo cáo tuần!", due_at)

    assert second["status"] == "draft_created"
    assert second["deduplicated"] is True
    assert second["task_id"] == first["task_id"]
    assert second["dedup_layer"] == "fuzzy"
    assert second["similarity_score"] >= 0.95


def test_conflicting_detail_or_all_day_vetoes_generic_exact_match(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())

    first = json.loads(
        draft_task.invoke(
            {"title": "Nộp báo cáo", "detail": "Môn HPC", "due_at": due_at.isoformat()}
        )
    )
    second = json.loads(
        draft_task.invoke(
            {"title": "Nộp báo cáo", "detail": "Môn Big Data", "due_at": due_at.isoformat()}
        )
    )
    all_day_due = due_at + timedelta(days=2)
    scheduled = json.loads(
        draft_task.invoke({"title": "Review tuần", "due_at": all_day_due.isoformat(), "all_day": False})
    )
    all_day = json.loads(
        draft_task.invoke({"title": "Review tuần", "due_at": all_day_due.isoformat(), "all_day": True})
    )

    assert second["task_id"] != first["task_id"]
    assert all_day["task_id"] != scheduled["task_id"]


def test_semantic_paraphrase_near_due_merges(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    monkeypatch.setattr(task_dedup, "_embed_task_titles", lambda _titles: [[1.0, 0.0], [0.99, 0.1]])

    first = _draft("Nộp báo cáo tuần", due_at)
    second = _draft("Weekly report submission", due_at + timedelta(hours=1))

    assert second["status"] == "draft_created"
    assert second["deduplicated"] is True
    assert second["task_id"] == first["task_id"]
    assert second["dedup_layer"] == "semantic"
    assert second["similarity_score"] > 0.99
    with Session(engine) as db:
        assert len(db.scalars(select(Task).where(Task.user_id == owner)).all()) == 1


def test_semantic_hard_negative_same_project_stays_separate(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    # 0.91 là rất gần về nghĩa nhưng vẫn dưới ngưỡng chặt 0.92.
    monkeypatch.setattr(task_dedup, "_embed_task_titles", lambda _titles: [[1.0, 0.0], [0.91, 0.414608]])

    # Ratio chữ 0.87: cluster threshold 0.72 sẽ gộp nhầm nếu thiếu guard 0.95
    # riêng cho draft. Hai động từ mô tả hai việc khác nhau trong cùng dự án.
    first = _draft("Soạn báo cáo tiến độ dự án Phoenix", due_at)
    second = _draft("Duyệt báo cáo tiến độ dự án Phoenix", due_at)

    assert second["status"] == "draft_created"
    assert second["deduplicated"] is False
    assert second["task_id"] != first["task_id"]
    with Session(engine) as db:
        assert len(db.scalars(select(Task).where(Task.user_id == owner)).all()) == 2


def test_semantic_disabled_degrades_without_losing_task(owner, monkeypatch):
    set_task_scope(owner)
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings(enabled=False))
    monkeypatch.setattr(
        task_dedup,
        "_embed_task_titles",
        lambda _titles: pytest.fail("Cờ tắt không được gọi embedding"),
    )

    first = _draft("Chuẩn bị slide Phoenix", due_at)
    second = _draft("Kiểm tra quyền API Phoenix", due_at)

    assert second["status"] == "draft_created"
    assert second["task_id"] != first["task_id"]
    with Session(engine) as db:
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "task_dedup_degraded",
                AuditEvent.object_id == str(second["task_id"]),
            )
        )
        assert audit is not None
        assert audit.details == {"reason": "semantic_disabled"}

    error_due = due_at + timedelta(days=2)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings(enabled=True))
    monkeypatch.setattr(
        task_dedup,
        "_embed_task_titles",
        lambda _titles: (_ for _ in ()).throw(TimeoutError("mock timeout")),
    )
    _draft("Chuẩn bị biên bản Phoenix", error_due)
    after_error = _draft("Kiểm tra quyền webhook Phoenix", error_due)

    assert after_error["status"] == "draft_created"
    with Session(engine) as db:
        error_audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "task_dedup_degraded",
                AuditEvent.object_id == str(after_error["task_id"]),
            )
        )
        assert error_audit is not None
        assert error_audit.details == {"reason": "embedding_error:TimeoutError"}


def test_merge_increments_source_count_and_preserves_evidence(owner, monkeypatch):
    due_at = datetime(2026, 8, 28, 9, 44, tzinfo=UTC)
    with Session(engine) as db:
        task = Task(
            user_id=owner,
            cluster_key="existing-task",
            title="Nộp báo cáo",
            detail="Bản gốc",
            due_at=due_at,
            status="proposed",
            source_count=2,
        )
        db.add(task)
        db.flush()
        old = TaskEvidence(
            task_id=task.id,
            provider="gmail",
            evidence_quote="Bằng chứng cũ",
            deep_link="https://mail.test/original",
        )
        db.add(old)
        db.commit()
        task_id = task.id
        old_evidence_id = old.id

    set_task_scope(owner)
    monkeypatch.setattr(task_dedup, "get_settings", lambda: _settings())
    result = _draft("Nộp báo cáo", due_at)
    replay = _draft("Nộp báo cáo", due_at)

    assert result["task_id"] == task_id
    assert replay["task_id"] == task_id
    with Session(engine) as db:
        tasks = db.scalars(select(Task).where(Task.user_id == owner)).all()
        evidence = db.scalars(select(TaskEvidence).where(TaskEvidence.task_id == task_id)).all()
        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "task_deduplicated",
                AuditEvent.object_id == str(task_id),
            )
        )
        assert len(tasks) == 1
        assert tasks[0].source_count == 3
        assert len(evidence) == 2
        assert {row.id for row in evidence} >= {old_evidence_id}
        assert any(row.provider == "user_draft" for row in evidence)
        assert db.get(TaskEvidence, old_evidence_id).evidence_quote == "Bằng chứng cũ"
        assert db.get(TaskEvidence, old_evidence_id).deep_link == "https://mail.test/original"
        assert audit is not None
        assert audit.details["layer"] == "exact"
        assert audit.details["similarity_score"] == 1.0
