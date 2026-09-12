"""Gói bằng chứng phải giữ đủ nguồn, không để một tool chiếm hết cửa sổ.

Ca thật đã xảy ra trên production: người dùng hỏi "trước khi họp mentor duty cần
làm gì". Agent gọi 13 tool, trong đó `calendar_search_events` tìm ĐÚNG sự kiện
"Mentor Duty 29/08 20:00". Nhưng sau đó nó gọi thêm sáu lượt `gmail_read_email`,
và cách cắt cũ — chỉ giữ 8 observation mới nhất — đẩy Calendar ra khỏi cửa sổ
trước khi câu trả lời được dựng. Kết quả: Mondaiy trả lời về báo cáo Jira lấy từ
email digest, hoàn toàn không nhắc cuộc họp người dùng hỏi.

Dữ liệu có, tool chạy đúng, guardrail không chặn — bằng chứng bị vứt ở bước cuối.
"""

from __future__ import annotations

import pytest

from src.agents.nodes.core_nodes import _budgeted_observations

# Đúng thứ tự 13 observation của lượt production đó; độ dài xấp xỉ output thật.
TRACE_THAT_LOST_CALENDAR = [
    ("list_tasks", 800),
    ("jira_search_issues", 6200),
    ("discord_search_program", 90),
    ("calendar_search_events", 2600),
    ("gmail_deadline_sweep", 3600),
    ("gmail_read_email", 950),
    ("gmail_read_email", 70),
    ("gmail_read_email", 1100),
    ("gmail_read_email", 1150),
    ("gmail_read_email", 1100),
    ("gmail_read_email", 1050),
    ("suggest_tasks", 95),
    ("suggest_tasks", 95),
]


def _observations(spec: list[tuple[str, int]]) -> list[dict]:
    return [{"name": name, "output": "x" * size} for name, size in spec]


def test_chum_goi_cung_tool_khong_hat_duoc_nguon_khac() -> None:
    kept = _budgeted_observations(_observations(TRACE_THAT_LOST_CALENDAR))
    names = [item["name"] for item in kept]

    assert "calendar_search_events" in names, (
        "calendar_search_events bị loại khỏi gói bằng chứng. Đây chính là lỗi "
        "production: sáu lượt gmail_read_email hất nguồn duy nhất trả lời được "
        "câu hỏi ra ngoài cửa sổ. Đừng xếp observation thuần theo độ mới."
    )
    assert names.count("gmail_read_email") < 6, (
        "Một tool vẫn đang chiếm gần hết cửa sổ; cách xếp theo vòng chưa có tác dụng."
    )

    # jira_search_issues CỐ Ý không nằm trong khẳng định trên. Một mình nó 6.200
    # ký tự trên ngân sách 12.000, nên giữ nó lại là đánh đổi bằng nhiều nguồn
    # khác. Với câu hỏi về một cuộc họp, cái dump 25 issue đó đúng là nhiễu —
    # bỏ nó là hành vi đúng, không phải hồi quy. Nếu sau này cần cả nguồn lớn,
    # việc phải làm là cắt output theo nguồn, không phải nới ngân sách.
    assert len({name for name in names}) >= 5, (
        f"Gói bằng chứng còn quá ít nguồn khác nhau: {sorted(set(names))}"
    )


def test_giu_dung_thu_tu_thoi_gian_goc() -> None:
    """Prompt phải đọc xuôi theo diễn biến, dù thứ tự chọn là theo vòng."""
    kept = _budgeted_observations(_observations(TRACE_THAT_LOST_CALENDAR))
    names = [item["name"] for item in kept]
    goc = [name for name, _ in TRACE_THAT_LOST_CALENDAR]

    vi_tri = [goc.index(name) for name in dict.fromkeys(names)]
    assert vi_tri == sorted(vi_tri), f"Thứ tự bị đảo: {names}"


def test_moi_tool_co_mat_truoc_khi_tool_nao_duoc_suat_thu_hai() -> None:
    spec = [("tool_a", 100)] * 5 + [("tool_b", 100), ("tool_c", 100)]
    kept = _budgeted_observations(_observations(spec))
    names = [item["name"] for item in kept]

    assert {"tool_a", "tool_b", "tool_c"} <= set(names), (
        f"Thiếu nguồn trong gói bằng chứng: {names}"
    )


def test_muc_qua_kho_bi_bo_qua_chu_khong_dung_ca_vong_duyet() -> None:
    """Dừng sớm ở mục quá khổ sẽ giết luôn tính đa dạng vừa dựng."""
    spec = [("nho_a", 50), ("khong_lo", 500_000), ("nho_b", 50)]
    kept = _budgeted_observations(_observations(spec))
    names = [item["name"] for item in kept]

    assert "nho_a" in names and "nho_b" in names, (
        f"Mục quá khổ đã chặn các nguồn nhỏ phía sau: {names}"
    )


def test_luon_giu_it_nhat_mot_muc_du_qua_ngan_sach() -> None:
    kept = _budgeted_observations(_observations([("khong_lo", 500_000)]))
    assert len(kept) == 1, "Một mục quá khổ vẫn phải được giữ, không mất trắng bằng chứng."


@pytest.mark.parametrize("observations", [[], None])
def test_khong_co_observation_thi_tra_ve_rong(observations) -> None:
    assert _budgeted_observations(observations or []) == []
