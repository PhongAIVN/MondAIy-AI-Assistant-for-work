"""`.content` của LangChain không cùng kiểu giữa hai endpoint của OpenAI.

    chat completions -> str
    responses        -> list[dict] các content block

Dòng gpt-5.6 chỉ nhận function tool qua Responses API. Bật
`LLM_USE_RESPONSES_API=true` trên production ngày 28/08 và mọi lượt chat trả về:

    Lỗi: 'list' object has no attribute 'strip'

vì `respond_node` đưa thẳng `message.content` (lúc này là list) vào
`ground_candidate`, nơi gọi `candidate.strip()`.

Đã đo trực tiếp bằng key production, và đây KHÔNG phải chuyện riêng của Luna:

    gpt-4o-mini  + chat       -> content là str
    gpt-4o-mini  + responses  -> content là list
    gpt-5.6-luna + responses  -> content là list

Tức là cờ API quyết định kiểu, không phải model. Vì vậy test dưới đây bám vào
HÌNH DẠNG dữ liệu chứ không bám tên model.
"""

from __future__ import annotations

from src.services.llm import response_text


class _Message:
    def __init__(self, content):
        self.content = content


def test_chat_completions_tra_ve_chuoi() -> None:
    assert response_text(_Message("xin chào")) == "xin chào"


def test_responses_api_tra_ve_list_content_block() -> None:
    """Đúng hình dạng thật đã bắt được từ API production."""
    khoi = [
        {
            "type": "text",
            "text": "Hôm nay bạn có 3 việc tới hạn.",
            "annotations": [],
            "id": "msg_0efa3b74",
        }
    ]
    assert response_text(_Message(khoi)) == "Hôm nay bạn có 3 việc tới hạn."


def test_nhieu_khoi_thi_noi_bang_xuong_dong() -> None:
    khoi = [{"type": "text", "text": "dòng một"}, {"type": "text", "text": "dòng hai"}]
    assert response_text(_Message(khoi)) == "dòng một\ndòng hai"


def test_ket_qua_luon_la_chuoi_de_strip_duoc() -> None:
    """Hợp đồng thật sự mà chỗ gọi cần: gọi được `.strip()`.

    `ground_candidate` làm đúng việc đó và đã nổ trên production.
    """
    for content in ("chuỗi", [{"type": "text", "text": "khối"}], [], None, 42):
        ket_qua = response_text(_Message(content))
        assert isinstance(ket_qua, str)
        ket_qua.strip()


def test_content_rong_thi_ra_chuoi_rong_khong_phai_none() -> None:
    assert response_text(_Message(None)) == ""
    assert response_text(_Message([])) == ""


def test_khoi_refusal_van_duoc_lay_vi_no_mang_chu_cho_nguoi_dung() -> None:
    assert response_text(_Message([{"type": "refusal", "refusal": "không thể"}])) == "không thể"


def test_khoi_reasoning_bi_bo_khoi_cau_tra_loi() -> None:
    """Ca thật lần hai trên production: hết crash nhưng câu trả lời thành rác.

    Khi có tool, Luna trả về HAI khối. Bản sửa đầu tiên nối cả hai nên dump
    nguyên JSON của khối reasoning ra cho người dùng đọc. Hình dạng dưới đây lấy
    nguyên từ API production.
    """
    khoi = [
        {
            "type": "reasoning",
            "id": "rs_007f6288202a0481",
            "summary": [],
            "content": [],
            "encrypted_content": "gAAAAABqkVx86Sdl9DszAjCi7fGSXbR00XJfjBZUHrAx",
        },
        {"type": "text", "text": "Hạn nộp báo cáo là ngày 29/08.", "annotations": []},
    ]
    ket_qua = response_text(_Message(khoi))
    assert ket_qua == "Hạn nộp báo cáo là ngày 29/08."
    assert "encrypted_content" not in ket_qua
    assert "reasoning" not in ket_qua


def test_chi_co_khoi_khong_mang_chu_thi_rong_va_co_canh_bao(caplog) -> None:
    """Trả rác cho người dùng còn tệ hơn bỏ khối — nhưng bỏ mà im lặng thì
    lần sau không ai tìm ra. Vì vậy: rỗng, kèm warning."""
    import logging

    with caplog.at_level(logging.WARNING, logger="src.services.llm"):
        assert response_text(_Message([{"type": "reasoning", "encrypted_content": "x"}])) == ""
    assert any("không khối nào mang chữ" in r.getMessage() for r in caplog.records)
