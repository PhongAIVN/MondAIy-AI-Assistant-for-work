"""Test score.py — ADR-018 QĐ-2/OD-01/OD-02. Xem docstring src/services/planner/score.py."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.services.planner.score import NEUTRAL_JOB_SIZE_MIN, rank_tasks, score_task

NOW = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)


@dataclass
class FakeTask:
    id: int | None = None
    due_at: datetime | None = None
    signal_strength: float = 0.0
    source_count: int = 1
    reminder_dismiss_count: int = 0
    stated_priority: str | None = None
    project_id: int | None = None


def test_components_sum_equals_total():
    task = FakeTask(id=1, due_at=NOW - timedelta(days=1), signal_strength=0.8, source_count=3,
                     reminder_dismiss_count=2, stated_priority="urgent", project_id=42)
    score = score_task(task, NOW, estimate=(20, 40))
    assert sum(score.components.values()) == score.total


def test_components_sum_equals_total_all_none_signals():
    # Đúng thực trạng production: due_at có, còn lại phần lớn chưa có tín hiệu.
    task = FakeTask(id=2)
    score = score_task(task, NOW, estimate=None)
    assert sum(score.components.values()) == score.total


def test_estimate_none_does_not_crash_and_uses_neutral_job_size():
    task = FakeTask(id=3, due_at=NOW + timedelta(days=1))
    score = score_task(task, NOW, estimate=None)
    assert score.job_size_min == NEUTRAL_JOB_SIZE_MIN
    assert score.wsjf == score.total / NEUTRAL_JOB_SIZE_MIN


def test_stated_priority_none_does_not_crash():
    task = FakeTask(id=4, stated_priority=None)
    score = score_task(task, NOW, estimate=(10, 20))
    assert score.components["stated_priority_bonus"] == 0.0


def test_overdue_ranks_above_due_today_ranks_above_due_soon():
    overdue = FakeTask(id=1, due_at=NOW - timedelta(days=2))
    due_today = FakeTask(id=2, due_at=NOW)
    due_soon = FakeTask(id=3, due_at=NOW + timedelta(days=2))
    future = FakeTask(id=4, due_at=NOW + timedelta(days=30))
    no_deadline = FakeTask(id=5, due_at=None)

    ranked = rank_tasks(
        [due_soon, no_deadline, future, overdue, due_today],
        NOW,
        estimates=[(30, 30)] * 5,
    )
    order = [task.id for task, _ in ranked]
    assert order == [1, 2, 3, 4, 5]


def test_high_reminder_dismiss_count_ranks_lower():
    dismissed_often = FakeTask(id=1, due_at=NOW, reminder_dismiss_count=10)
    never_dismissed = FakeTask(id=2, due_at=NOW, reminder_dismiss_count=0)

    ranked = rank_tasks([dismissed_often, never_dismissed], NOW, estimates=[(30, 30), (30, 30)])
    order = [task.id for task, _ in ranked]
    assert order == [2, 1]

    # Bằng chứng bằng số, không chỉ bằng thứ tự.
    scores = {s.task_id: s for _, s in ranked}
    assert scores[1].components["dismiss_penalty"] < scores[2].components["dismiss_penalty"]


def test_rank_tasks_does_not_truncate():
    tasks = [FakeTask(id=i) for i in range(10)]
    ranked = rank_tasks(tasks, NOW)
    assert len(ranked) == 10


def test_rank_tasks_deterministic_same_input_same_order_100_runs():
    tasks = [
        FakeTask(id=1, due_at=NOW - timedelta(days=1), signal_strength=0.5, source_count=2),
        FakeTask(id=2, due_at=NOW + timedelta(days=1), signal_strength=0.9, source_count=1),
        FakeTask(id=3, due_at=None, reminder_dismiss_count=3),
    ]
    estimates = [(10, 20), None, (30, 60)]
    orders = set()
    for _ in range(100):
        ranked = rank_tasks(tasks, NOW, estimates=estimates)
        orders.add(tuple(task.id for task, _ in ranked))
    assert len(orders) == 1


def test_rank_tasks_estimates_length_mismatch_raises():
    tasks = [FakeTask(id=1), FakeTask(id=2)]
    try:
        rank_tasks(tasks, NOW, estimates=[(10, 20)])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for mismatched estimates length")
