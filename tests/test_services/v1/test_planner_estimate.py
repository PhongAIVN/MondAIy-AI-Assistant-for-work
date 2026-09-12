"""Test estimate.py — ADR-018 QĐ-2. Xem docstring src/services/planner/estimate.py."""

from __future__ import annotations

from dataclasses import dataclass

from src.services.planner.estimate import MIN_SIMILAR_SAMPLES, estimate_minutes


@dataclass
class FakeTask:
    user_id: str = "u1"
    title: str = "Trả lời email khách hàng A"
    estimate_low_min: int | None = None
    estimate_high_min: int | None = None


@dataclass
class FakeHistoricalTask:
    user_id: str
    title: str
    actual_minutes: int | None


def _similar_history(count: int, actuals: list[int]) -> list[FakeHistoricalTask]:
    assert len(actuals) == count
    return [
        FakeHistoricalTask(user_id="u1", title="Trả lời email khách hàng A", actual_minutes=m)
        for m in actuals
    ]


def test_no_history_no_saved_estimate_returns_none():
    task = FakeTask()
    assert estimate_minutes(task, []) is None


def test_saved_estimate_used_when_no_reference_class():
    task = FakeTask(estimate_low_min=20, estimate_high_min=40)
    assert estimate_minutes(task, []) == (20, 40)


def test_partial_saved_estimate_is_not_a_valid_interval():
    # Chỉ có low, thiếu high -> không phải khoảng hợp lệ -> None, không đoán high.
    task = FakeTask(estimate_low_min=20, estimate_high_min=None)
    assert estimate_minutes(task, []) is None


def test_reference_class_below_min_samples_falls_back_to_saved_estimate():
    task = FakeTask(estimate_low_min=10, estimate_high_min=15)
    history = _similar_history(MIN_SIMILAR_SAMPLES - 1, [30] * (MIN_SIMILAR_SAMPLES - 1))
    assert estimate_minutes(task, history) == (10, 15)


def test_reference_class_used_when_enough_similar_samples():
    task = FakeTask(estimate_low_min=999, estimate_high_min=999)  # phải bị bỏ qua
    actuals = [10, 20, 30, 40, 50]
    history = _similar_history(MIN_SIMILAR_SAMPLES, actuals)
    result = estimate_minutes(task, history)
    assert result is not None
    low, high = result
    assert low <= high
    # p25/p75 của [10,20,30,40,50] phải nằm trong khoảng dữ liệu quan sát được
    assert 10 <= low <= 30
    assert 30 <= high <= 50


def test_reference_class_ignores_other_users():
    task = FakeTask(user_id="u1")
    history = [
        FakeHistoricalTask(user_id="u2", title=task.title, actual_minutes=m)
        for m in range(MIN_SIMILAR_SAMPLES + 5)
    ]
    assert estimate_minutes(task, history) is None


def test_reference_class_ignores_dissimilar_titles():
    task = FakeTask(title="Chuẩn bị báo cáo tài chính quý 3")
    history = [
        FakeHistoricalTask(user_id="u1", title="Đặt vé máy bay đi công tác", actual_minutes=m)
        for m in range(MIN_SIMILAR_SAMPLES + 5)
    ]
    assert estimate_minutes(task, history) is None


def test_reference_class_ignores_tasks_without_actual_minutes():
    task = FakeTask()
    history = [
        FakeHistoricalTask(user_id="u1", title=task.title, actual_minutes=None)
        for _ in range(MIN_SIMILAR_SAMPLES + 5)
    ]
    assert estimate_minutes(task, history) is None


def test_deterministic_same_input_same_output():
    task = FakeTask(estimate_low_min=20, estimate_high_min=40)
    history = _similar_history(MIN_SIMILAR_SAMPLES, [10, 20, 30, 40, 50])
    results = {estimate_minutes(task, history) for _ in range(100)}
    assert len(results) == 1
