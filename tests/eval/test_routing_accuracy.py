"""Đo độ chính xác định tuyến và khoá sàn, thay vì chỉ pass/fail từng ca.

Khác test thường ở một điểm: test thường nói "hỏng chỗ nào", bộ này nói "hỏng
BAO NHIÊU". Đó là con số cần khi muốn dọn 23 regex hoặc thay hẳn tầng định
tuyến — bỏ một luật rồi chạy lại là biết đánh đổi, không phải đoán.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.services.intent_router import ToolPlanContext, plan_tool_calls
from tests.eval.routing_gold import GOLD_CASES, GoldCase, cases_by_status

# Mốc thời gian đóng băng: cửa sổ lịch/mail suy từ "bây giờ", nên thời gian trôi
# sẽ làm bộ đo dao động. Thứ Năm giữa tuần, tránh cuối tuần và biên tháng.
NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)


def route(case: GoldCase) -> list[str]:
    planned = plan_tool_calls(
        [],  # model chưa đề xuất gì — cô lập đúng tầng xác định
        ToolPlanContext(query=case.query, now=NOW, web_search_enabled=True),
    )
    return [call["name"] for call in planned]


def judge(case: GoldCase) -> tuple[bool, str]:
    tools = route(case)

    sai = sorted(set(tools) & case.expect_none_of)
    if sai:
        return False, f"route sang nguồn không liên quan: {sai} (đã route: {tools})"

    if case.expect_any_of and not (set(tools) & case.expect_any_of):
        thieu = sorted(case.expect_any_of)
        return False, f"thiếu tool cần có (một trong {thieu}); đã route: {tools}"

    if not case.expect_any_of and tools:
        return False, f"lẽ ra không tra nguồn nào, nhưng đã route: {tools}"

    return True, ""


@pytest.mark.parametrize("case", cases_by_status("locked"), ids=str)
def test_ca_da_khoa_van_dung(case: GoldCase) -> None:
    ok, ly_do = judge(case)
    assert ok, f"{case.query!r}: {ly_do}\nGhi chú: {case.note or '(không có)'}"


@pytest.mark.parametrize("case", cases_by_status("gap"), ids=str)
def test_khoang_trong_da_biet_chua_tu_khoi(case: GoldCase) -> None:
    """Ca đã biết là sai. Nếu tự nhiên ĐÚNG thì phải đổi sang "locked" ngay.

    Không để lửng: một khoảng trống im lặng tự lành rồi hỏng lại là thứ không ai
    phát hiện. Đó đúng là cách sự cố embedding sống sót lâu như vậy.
    """
    ok, _ = judge(case)
    assert not ok, (
        f"{case.query!r} nay đã route ĐÚNG. Đổi status sang 'locked' trong "
        f"tests/eval/routing_gold.py để khoá lại, kẻo nó lặng lẽ hỏng lần nữa.\n"
        f"Ghi chú: {case.note}"
    )


def test_do_chinh_xac_khong_duoc_tut_duoi_san() -> None:
    dat = [case for case in GOLD_CASES if judge(case)[0]]
    ty_le = len(dat) / len(GOLD_CASES)

    hong = [(case.query, judge(case)[1]) for case in GOLD_CASES if not judge(case)[0]]
    bao_cao = "\n".join(f"  ✗ {q}: {ly_do}" for q, ly_do in hong)

    # Sàn đặt bằng đúng mức ĐO ĐƯỢC lúc dựng bộ này, nay 15/22 = 68%. Đây là chốt
    # chặn hồi quy, không phải mục tiêu — sửa được khoảng trống nào thì NÂNG sàn
    # trong cùng PR. Cố ý KHÔNG đặt sàn theo mong muốn: một con số không đạt
    # được ngay từ đầu thì chỉ dạy người ta bỏ qua bộ đo.
    san = 0.68
    assert ty_le >= san, (
        f"Độ chính xác định tuyến {ty_le:.0%} < sàn {san:.0%} "
        f"({len(dat)}/{len(GOLD_CASES)} ca đạt).\n{bao_cao}"
    )


def test_in_bang_diem(capsys: pytest.CaptureFixture) -> None:
    """Không khẳng định gì — chỉ in số để so trước/sau khi sửa router."""
    dat = sum(1 for case in GOLD_CASES if judge(case)[0])
    khoa = cases_by_status("locked")
    trong = cases_by_status("gap")
    dat_khoa = sum(1 for case in khoa if judge(case)[0])

    with capsys.disabled():
        print(
            f"\n  ĐỊNH TUYẾN — {dat}/{len(GOLD_CASES)} ca đạt ({dat / len(GOLD_CASES):.0%})"
            f"\n    đã khoá      : {dat_khoa}/{len(khoa)}"
            f"\n    khoảng trống : {len(trong)} (đã biết, chưa sửa)"
        )
