"""Cổng "người dùng có thật sự yêu cầu tạo không" cho `create_productivity_item`.

Ca thật trên production 28/08, lúc 15:08. Thái gõ:

    nhắn tôi 3h40 hồi quota AI rồi làm tiếp công việc

và nhận về "Mình chưa tạo vì lượt hiện tại không có yêu cầu ghi rõ ràng từ
người dùng."

Đọc trace mới thấy model KHÔNG hề hiểu sai: nó tính đúng `3h40` thành
`2026-08-28T15:40:00+07:00` và gọi `create_productivity_item` với đủ title,
deadline, description. Chính `_kind_is_explicit` chặn lại, vì `_CREATE_VERB`
có `nhắc tôi` mà không có `nhắn tôi` — sai đúng MỘT chữ cái.

Vì vậy hai nhóm test dưới đây quan trọng ngang nhau:

- Nhóm CHẤP NHẬN khoá lại họ động từ "bảo trợ lý báo lại cho tôi". Thiếu một
  biến thể là người dùng lại bị từ chối khi họ đã nói rất rõ.
- Nhóm TỪ CHỐI khoá lại phần cổng vẫn phải giữ. Nới cổng này quá tay thì model
  tự đẻ ra task người dùng không yêu cầu — đúng thứ cổng sinh ra để chặn.

Ràng buộc giữ cho việc nới không thành nới ẩu: động từ BẮT BUỘC đi kèm tân ngữ
ngôi thứ nhất (`tôi`/`mình`). Không có nó thì "báo cáo", "gọi vốn" khớp nhầm.
"""

from __future__ import annotations

import pytest

from src.agents.tools.productivity_tool import _kind_is_explicit

CHAP_NHAN = [
    # Nguyên văn câu đã hỏng trên production.
    "nhắn tôi 3h40 hồi quota AI rồi làm tiếp công việc",
    "nhắc tôi 3h40 hỏi quota AI",
    "báo tôi lúc 3h40 nhé",
    "nhắn tin cho tôi lúc 3h40",
    "ping tôi lúc 3h40",
    "gọi tôi 3h40",
    "thông báo cho mình lúc 18h",
    "đánh thức tôi lúc 6h sáng mai",
    "tạo task nộp báo cáo",
    "remind me at 3:40 about the AI quota",
]

TU_CHOI = [
    # Câu hỏi thuần tuý — không ai yêu cầu tạo gì.
    "hôm nay tôi cần làm gì",
    "tuần này có việc gì gấp không",
    # Có động từ nhưng không phải yêu cầu gửi tin cho người dùng.
    "viết báo cáo tuần này",
    "gửi báo cáo cho tôi xem",
    # Bẫy chuỗi con: "báo cáo" chứa "báo", "gọi vốn" chứa "gọi".
    "báo cáo tiến độ giúp tôi",
    "tôi cần gọi vốn cho dự án",
    "chuẩn bị báo cáo rồi gọi cho khách",
]


@pytest.mark.parametrize("cau", CHAP_NHAN)
def test_yeu_cau_ro_rang_thi_duoc_phep_tao(cau: str) -> None:
    assert _kind_is_explicit(cau, "task") is True, (
        f"{cau!r} là yêu cầu tạo nhắc nhở rõ ràng nhưng cổng vẫn từ chối. "
        "Người dùng sẽ đọc được câu 'mình chưa chắc bạn muốn tạo' dù họ vừa nói rất rõ."
    )


@pytest.mark.parametrize("cau", TU_CHOI)
def test_khong_phai_yeu_cau_tao_thi_van_bi_chan(cau: str) -> None:
    assert _kind_is_explicit(cau, "task") is False, (
        f"{cau!r} KHÔNG phải yêu cầu tạo. Cho qua là mở đường cho model tự đẻ "
        "task người dùng không hề yêu cầu — đúng thứ cổng này sinh ra để chặn."
    )


def test_dong_tu_phai_di_kem_tan_ngu_ngoi_thu_nhat() -> None:
    """Đây là ràng buộc giữ cho cổng không bị nới rộng.

    Bỏ nó đi thì mọi câu có chữ "báo" hay "gọi" đều thành yêu cầu tạo task.
    """
    assert _kind_is_explicit("nhắn tôi lúc 8h", "task") is True
    assert _kind_is_explicit("nhắn khách lúc 8h", "task") is False
    assert _kind_is_explicit("báo tôi lúc 8h", "task") is True
    assert _kind_is_explicit("báo sếp lúc 8h", "task") is False
