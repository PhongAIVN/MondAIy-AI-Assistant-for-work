from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.config import Settings
from src.services.planner.schedule import (
    DailyCadence,
    build_day_schedule,
    cadence_from_settings,
)
from src.services.planner.score import NEUTRAL_JOB_SIZE_MIN

ICT = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_CADENCE = DailyCadence(
    workday_start=time(8),
    lunch_start=time(12),
    afternoon_start=time(13, 30),
    dinner_start=time(18),
    evening_start=time(19, 30),
    day_end=time(22),
)


@dataclass(frozen=True)
class FakeTask:
    id: int
    title: str
    user_id: str = "user-1"
    due_at: datetime | None = None
    signal_strength: float = 0.0
    source_count: int = 0
    reminder_dismiss_count: int = 0
    stated_priority: str | None = None
    estimate_low_min: int | None = 30
    estimate_high_min: int | None = 30
    energy: str | None = None


def _schedule(now: datetime, *tasks: FakeTask, cadence: DailyCadence = DEFAULT_CADENCE):
    return build_day_schedule(tasks, [], now=now, cadence=cadence)


def test_14h_khong_xep_vao_buoi_sang_da_qua():
    now = datetime(2026, 8, 27, 14, 0, tzinfo=ICT)

    schedule = _schedule(now, FakeTask(1, "Việc lúc 14h"))

    assert schedule.blocks[0].start == now
    assert all(block.start >= now for block in schedule.blocks)


@pytest.mark.parametrize(
    ("now", "expected_start"),
    [
        (datetime(2026, 8, 27, 11, 45, tzinfo=ICT), time(13, 30)),
        (datetime(2026, 8, 27, 17, 45, tzinfo=ICT), time(19, 30)),
    ],
)
def test_block_khong_cat_qua_gio_nghi(now: datetime, expected_start: time):
    schedule = _schedule(now, FakeTask(1, "Việc 30 phút"))

    assert schedule.blocks[0].start.time() == expected_start
    assert schedule.blocks[0].end - schedule.blocks[0].start == timedelta(minutes=30)


def test_deep_khong_vao_evening_nhung_shallow_van_duoc_xep():
    now = datetime(2026, 8, 27, 19, 30, tzinfo=ICT)
    deep = FakeTask(1, "Việc sâu", estimate_low_min=60, estimate_high_min=60, energy="deep")
    shallow = FakeTask(2, "Việc nhẹ", energy="shallow")

    schedule = _schedule(now, deep, shallow)

    assert [block.task_id for block in schedule.blocks] == [2]
    assert [task.task_id for task in schedule.deferred_to_tomorrow] == [1]
    assert schedule.deferred_to_tomorrow[0].start.time() == time(8)


def test_qua_tai_duoc_dua_sang_mai_khong_mat_task():
    now = datetime(2026, 8, 27, 21, 30, tzinfo=ICT)
    tasks = [FakeTask(index, f"Việc {index}") for index in range(1, 4)]

    schedule = _schedule(now, *tasks)

    today_ids = {block.task_id for block in schedule.blocks}
    deferred_ids = {task.task_id for task in schedule.deferred_to_tomorrow}
    assert today_ids | deferred_ids == {1, 2, 3}
    assert today_ids.isdisjoint(deferred_ids)
    assert all(item.start.date() == now.date() + timedelta(days=1) for item in schedule.deferred_to_tomorrow)


def test_chi_nhac_nghi_khi_co_viec_buoi_toi():
    evening = _schedule(datetime(2026, 8, 27, 19, 30, tzinfo=ICT), FakeTask(1, "Việc nhẹ"))
    afternoon = _schedule(datetime(2026, 8, 27, 14, 0, tzinfo=ICT), FakeTask(1, "Việc nhẹ"))

    assert evening.rest_reminder is not None
    assert afternoon.rest_reminder is None


def test_none_estimate_dung_neutral_fallback_va_noi_ro():
    task = FakeTask(1, "Chưa biết lâu", estimate_low_min=None, estimate_high_min=None)

    schedule = _schedule(datetime(2026, 8, 27, 14, 0, tzinfo=ICT), task)

    block = schedule.blocks[0]
    assert block.minutes == int(NEUTRAL_JOB_SIZE_MIN)
    assert block.estimate_confidence == "neutral_fallback"
    assert "Chưa ước lượng được" in block.why


def test_blocks_khong_overlap_va_duration_khop_minutes():
    tasks = [FakeTask(index, f"Việc {index}", estimate_low_min=45, estimate_high_min=45) for index in range(1, 5)]

    schedule = _schedule(datetime(2026, 8, 27, 14, 0, tzinfo=ICT), *tasks)

    assert all(left.end <= right.start for left, right in zip(schedule.blocks, schedule.blocks[1:]))
    assert all(block.end - block.start == timedelta(minutes=block.minutes) for block in schedule.blocks)


def test_23h_moi_task_deferred_sang_mai():
    schedule = _schedule(datetime(2026, 8, 27, 23, 0, tzinfo=ICT), FakeTask(1, "Việc quá muộn"))

    assert schedule.blocks == ()
    assert [task.task_id for task in schedule.deferred_to_tomorrow] == [1]
    assert schedule.deferred_to_tomorrow[0].start.date().isoformat() == "2026-08-28"


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (FakeTask(1, "Explicit", estimate_high_min=90, energy="shallow"), "shallow"),
        (FakeTask(1, "Đúng ngưỡng", estimate_low_min=45, estimate_high_min=45), "shallow"),
        (FakeTask(1, "Qua ngưỡng", estimate_low_min=46, estimate_high_min=46), "deep"),
        (FakeTask(1, "Fallback", estimate_low_min=None, estimate_high_min=None), "shallow"),
    ],
)
def test_energy_explicit_hoac_suy_tu_can_tren(task: FakeTask, expected: str):
    schedule = _schedule(datetime(2026, 8, 27, 14, 0, tzinfo=ICT), task)

    assert schedule.blocks[0].energy == expected


def test_scheduler_xac_dinh_100_lan():
    now = datetime(2026, 8, 27, 14, 0, tzinfo=ICT)
    tasks = (FakeTask(1, "A"), FakeTask(2, "B", estimate_low_min=60, estimate_high_min=60))

    results = {_schedule(now, *tasks) for _ in range(100)}

    assert len(results) == 1


def test_rank_tasks_quyet_dinh_thu_tu():
    later = datetime(2026, 8, 30, 10, 0, tzinfo=ICT)
    urgent = FakeTask(2, "Quá hạn", due_at=datetime(2026, 8, 26, 10, 0, tzinfo=ICT))
    future = FakeTask(1, "Còn hạn", due_at=later)

    schedule = _schedule(datetime(2026, 8, 27, 14, 0, tzinfo=ICT), future, urgent)

    assert [block.task_id for block in schedule.blocks] == [2, 1]


def test_config_mac_dinh_va_custom_cadence_thuc_su_duoc_dung():
    settings = Settings(_env_file=None)
    cadence = cadence_from_settings(settings)
    custom = replace(cadence, workday_start=time(9))

    assert cadence == DEFAULT_CADENCE
    schedule = _schedule(datetime(2026, 8, 27, 8, 0, tzinfo=ICT), FakeTask(1, "Bắt đầu muộn"), cadence=custom)
    assert schedule.blocks[0].start.time() == time(9)


@pytest.mark.parametrize(
    "now",
    [datetime(2026, 8, 27, 14, 0), datetime(2026, 8, 27, 14, 0, tzinfo=None)],
)
def test_now_naive_bi_tu_choi(now: datetime):
    with pytest.raises(ValueError, match="timezone"):
        _schedule(now, FakeTask(1, "Không rõ timezone"))


def test_viec_han_hom_nay_khong_bi_day_sang_mai_boi_viec_nho_chua_gap():
    """WSJF một mình sẽ lỡ hạn hôm nay; tầng xếp lịch phải chặn điều đó.

    WSJF là giá trị chia khối lượng, nên một việc lớn hạn hôm nay luôn thua
    nhiều việc nhỏ hạn về sau. Đo thật trước khi sửa: một báo cáo 90 phút hạn
    hôm nay bị 14 việc nhẹ 25 phút hạn NGÀY MAI đẩy xuống hết và dời sang mai —
    tức lỡ hạn, dù công thức xếp hạng vẫn đúng như ADR-018 chốt.

    Test này khoá ràng buộc bổ sung, KHÔNG khoá công thức WSJF.
    """
    now = datetime(2026, 8, 27, 14, 0, tzinfo=ICT)
    han_hom_nay = FakeTask(
        1,
        "Việc hạn hôm nay",
        due_at=now.replace(hour=23, minute=0),
        stated_priority="high",
        estimate_low_min=90,
        estimate_high_min=90,
    )
    viec_nho = [
        FakeTask(i, f"Việc nhẹ {i}", due_at=now + timedelta(days=1), estimate_low_min=25, estimate_high_min=25)
        for i in range(2, 16)
    ]

    schedule = _schedule(now, han_hom_nay, *viec_nho)

    da_xep = {block.task_id for block in schedule.blocks}
    assert 1 in da_xep, (
        "Việc hạn hôm nay bị dời sang mai trong khi việc hạn ngày mai được xếp — "
        "đó là lỡ hạn, không phải đánh đổi hợp lý."
    )
    assert schedule.blocks[0].task_id == 1, "Việc hạn hôm nay phải được nhét trước."


def test_qua_han_cung_duoc_uu_tien_nhu_han_hom_nay():
    now = datetime(2026, 8, 27, 14, 0, tzinfo=ICT)
    qua_han = FakeTask(
        1, "Việc quá hạn", due_at=now - timedelta(days=3), estimate_low_min=60, estimate_high_min=60
    )
    tuong_lai = [
        FakeTask(i, f"Việc sau {i}", due_at=now + timedelta(days=2), estimate_low_min=20, estimate_high_min=20)
        for i in range(2, 12)
    ]

    schedule = _schedule(now, qua_han, *tuong_lai)

    assert schedule.blocks[0].task_id == 1


def test_khong_han_thi_khong_duoc_chen_len_truoc_viec_han_hom_nay():
    """Task không hạn KHÔNG phải là 'hạn hôm nay' — đừng gom nhầm vào nhóm ưu tiên."""
    now = datetime(2026, 8, 27, 14, 0, tzinfo=ICT)
    khong_han = FakeTask(1, "Không hạn", due_at=None, estimate_low_min=20, estimate_high_min=20)
    han_hom_nay = FakeTask(
        2, "Hạn hôm nay", due_at=now.replace(hour=23), estimate_low_min=20, estimate_high_min=20
    )

    schedule = _schedule(now, khong_han, han_hom_nay)

    assert schedule.blocks[0].task_id == 2
