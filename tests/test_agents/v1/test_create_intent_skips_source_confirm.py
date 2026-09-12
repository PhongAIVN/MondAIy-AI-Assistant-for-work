"""Yêu cầu TẠO không bị chặn bởi cổng xác nhận nguồn.

Ca thật Thái gặp 27/08: "nhắc tôi 01/09 23:59 nộp dự án P004" bị hỏi lại
"Mình nhận diện entity/dự án 'P004' nhưng chưa chắc bạn muốn lấy từ nguồn nào.
Bạn xác nhận giúp mình nguồn cần kiểm tra: Tasks, Jira, Gmail, Calendar,
Discord, Google Sheets, Google Docs hay tất cả?"

Câu đó không tra gì cả. Người dùng đang ĐỌC CHO máy ghi, không phải nhờ máy đọc
hộ. Không có nguồn nào để chọn, và hỏi lại là bắt họ trả lời một câu vô nghĩa —
rồi họ phải gõ thêm "tạo task í" mới xong việc.

Đọc và tạo là hai ý định khác nhau; cổng xác nhận nguồn chỉ có nghĩa cho vế đọc.
"""

from __future__ import annotations

import pytest

from src.services.intent_router.tool_planning import is_productivity_create
from src.services.source_routing import analyze_source_mentions

CAU_THAT = "nhắc tôi 01/09 23:59 nộp dự án P004"


def test_ca_that_van_bi_source_routing_nhan_nham_la_cau_doc() -> None:
    """Khoá lại hiện trạng của source_routing, để bản sửa không giả vờ nó đã đúng.

    Bản sửa nằm ở core_nodes, không phải ở đây: source_routing nhận diện entity
    đúng nhiệm vụ của nó. Cái sai là hỏi xác nhận nguồn mà không xét ý định.
    """
    decision = analyze_source_mentions(CAU_THAT)

    assert decision.needs_confirmation is True
    assert decision.action == "confirm_source"


@pytest.mark.parametrize(
    "query",
    [
        CAU_THAT,
        "tạo task nộp dự án P004",
        "nhắc tôi mai họp mentor",
    ],
)
def test_cac_cau_tao_deu_duoc_nhan_dien(query: str) -> None:
    assert is_productivity_create(query) is True, (
        f"{query!r} là yêu cầu tạo. Nhận nhầm thành câu đọc thì người dùng sẽ bị "
        "hỏi nguồn dữ liệu cho một việc chưa tồn tại."
    )


@pytest.mark.parametrize(
    "query",
    [
        "dự án P004 có gì mới",
        "task nào của dự án P004 đang quá hạn",
    ],
)
def test_cau_doc_that_van_duoc_hoi_nguon(query: str) -> None:
    """Đừng sửa quá tay: câu đọc thật vẫn phải đi qua cổng xác nhận nguồn."""
    assert is_productivity_create(query) is False


def test_khoang_trong_da_biet_them_viec_tran_khong_duoc_nhan() -> None:
    """"thêm việc X" KHÔNG được nhận là tạo. Đã biết, cố ý chưa sửa.

    `_AGENT_PRODUCTIVITY_CREATE` đòi cả động từ lẫn danh từ, và danh từ phải là
    "cong viec" hoặc "viec can lam" — "them viec" trần không khớp.

    Nới thành `viec` trần sẽ bắt nhầm nhiều câu đọc: "cho tôi thêm thông tin về
    việc...", "có việc gì cần làm không". Thêm một regex nữa cũng đúng hướng mà
    cả phần router đang cố thoát ra.

    Nếu ca này tự đúng, đổi test và ghi vào tests/eval/routing_gold.py.
    """
    assert is_productivity_create("thêm việc gửi báo cáo cho dự án P004") is False
