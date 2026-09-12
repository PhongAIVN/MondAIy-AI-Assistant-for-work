from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.models.planner_preference import PlannerPreference
from src.services.planner.schedule import build_day_schedule
from src.services.planner.workspace import (
    _refresh_insights,
    cadence_from_preference,
    protected_windows,
    validate_preferences,
)

ICT = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass
class Task:
    id: int = 1
    user_id: str = "u"
    title: str = "Việc cần làm"
    due_at: datetime | None = None
    signal_strength: float = 0
    source_count: int = 0
    reminder_dismiss_count: int = 0
    stated_priority: str | None = None
    estimate_low_min: int | None = 30
    estimate_high_min: int | None = 30
    energy: str | None = "deep"


def test_happy_time_la_rang_buoc_cung_khong_bi_xep_task_de():
    pref = PlannerPreference(
        user_id="u", workday_start_minute=8 * 60, lunch_start_minute=12 * 60,
        lunch_end_minute=14 * 60, workday_end_minute=18 * 60,
        happy_time_enabled=True, happy_time_start_minute=16 * 60, happy_time_end_minute=17 * 60,
    )
    schedule = build_day_schedule(
        [Task()], [], now=datetime(2026, 8, 28, 15, 45, tzinfo=ICT),
        cadence=cadence_from_preference(pref), protected_windows=protected_windows(pref),
    )
    assert schedule.blocks[0].start.hour == 17
    assert schedule.blocks[0].end.hour == 17


def test_lich_chung_la_rang_buoc_cung_khong_bi_xep_task_de():
    pref = PlannerPreference(
        user_id="u", workday_start_minute=8 * 60, lunch_start_minute=12 * 60,
        lunch_end_minute=14 * 60, workday_end_minute=18 * 60,
    )
    schedule = build_day_schedule(
        [Task()], [], now=datetime(2026, 8, 28, 9, 0, tzinfo=ICT),
        cadence=cadence_from_preference(pref),
        protected_windows=protected_windows(pref),
        busy_windows=((datetime(2026, 8, 28, 9, 0, tzinfo=ICT), datetime(2026, 8, 28, 11, 0, tzinfo=ICT), "Họp chung"),),
    )
    assert schedule.blocks[0].start.hour == 11


def test_contract_tu_choi_gio_nghi_khong_nam_trong_ngay_lam_viec():
    pref = PlannerPreference(
        user_id="u", workday_start_minute=9 * 60, lunch_start_minute=8 * 60,
        lunch_end_minute=14 * 60, workday_end_minute=18 * 60,
    )
    try:
        validate_preferences(pref)
    except ValueError:
        return
    raise AssertionError("Planner phải từ chối nhịp giờ không tăng dần")


def test_lam_moi_nhan_ra_task_moi_urgent_va_de_xuat_doi_block():
    now = datetime(2026, 8, 28, 8, 0, tzinfo=ICT)
    urgent = SimpleNamespace(id=1, title="Nộp báo cáo", due_at=now)
    existing = SimpleNamespace(id=2, title="Đọc tài liệu", due_at=None)
    old = SimpleNamespace(task_id=2, start=now, end=now.replace(hour=9))
    new = SimpleNamespace(task_id=2, title="Đọc tài liệu", start=now.replace(hour=14), end=now.replace(hour=15))

    summary, suggestions = _refresh_insights(
        tasks=[urgent, existing],
        blocks=[new],
        at_risk=[],
        known_task_ids=[2],
        previous_blocks=[old],
        local_today=now.date(),
    )

    assert summary == {
        "new_task_count": 1,
        "new_urgent_today_count": 1,
        "reschedule_count": 1,
        "at_risk_count": 0,
    }
    assert suggestions[0]["task_id"] == 2
    assert suggestions[0]["to_start"] == now.replace(hour=14)
    assert "Nhường chỗ" in suggestions[0]["reason"]
