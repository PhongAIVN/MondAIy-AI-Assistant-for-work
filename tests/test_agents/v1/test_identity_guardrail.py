"""Mondaiy là mondaiy, không phải sản phẩm của nhà cung cấp model nào.

Ca thật trên production 28/08. Thái hỏi "cuối cùng là bạn thật sự do ai sáng lập
ra" và nhận về:

    "Mình được phát triển bởi OpenAI, một tổ chức nghiên cứu chuyên về trí tuệ
     nhân tạo. OpenAI được sáng lập bởi Elon Musk, Sam Altman, Greg Brockman..."

Ba thứ sai trong một câu trả lời:

1. Lộ nhà cung cấp phía sau. Mondaiy tự nhận là sản phẩm của OpenAI.
2. Trả lời kiến thức chung (tiểu sử người sáng lập) như thể đã biết chắc, trong
   khi không tra được nguồn nào.
3. Trace ghi `groundingStatus: "grounded"` cho khẳng định đó — cổng grounding so
   từ vựng với nguồn, nên khi KHÔNG có nguồn nào nó chẳng có gì để so và vẫn gắn
   nhãn đã kiểm chứng.

Test này khoá phần luật trong prompt. Nó KHÔNG kiểm được model có tuân luật hay
không — điều đó cần eval chạy model thật, và nó nằm ngoài phạm vi PR này.
Nhưng luật biến mất khỏi prompt thì phải có gì đó đỏ, vì lần trước
`_SMALL_TALK_PROMPT` nằm chết trong file suốt gần hai tuần mà không ai biết.
"""

from __future__ import annotations

import pytest

from src.agents.nodes.core_nodes import _RESPOND_PROMPT

# Đúng những câu Thái đã hỏi, cộng vài biến thể. Giữ ở đây để lần sau ai đọc
# test cũng biết luật này sinh ra từ ca thật nào.
CAU_HOI_DANH_TINH = (
    "cuối cùng là bạn thật sự là do ai sáng lập ra",
    "Tác giả của bạn là ai người sáng tạo bạn người sáng lập bạn",
    "bạn chạy trên model gì",
)


def test_prompt_cam_nhan_minh_la_san_pham_cua_nha_cung_cap_model() -> None:
    prompt = _RESPOND_PROMPT.lower()

    for hang in ("openai", "gemini", "claude", "anthropic", "google"):
        assert hang in prompt, (
            f"Prompt phải nêu ĐÍCH DANH {hang!r} trong luật cấm. Nói chung chung "
            '("đừng nói mình do hãng nào tạo ra") thì model vẫn trả lời "tôi do '
            'OpenAI phát triển" — nó không tự coi đó là vi phạm.'
        )


def test_prompt_khang_dinh_danh_tinh_mondaiy() -> None:
    assert "mondaiy" in _RESPOND_PROMPT.lower()
    assert "DANH TÍNH" in _RESPOND_PROMPT, (
        "Luật danh tính phải là một khối được đánh dấu rõ, không lẫn vào văn xuôi "
        "— để lần dọn prompt sau không ai xoá nhầm."
    )


def test_prompt_chan_tra_loi_kien_thuc_chung_nhu_da_biet_chac() -> None:
    prompt = _RESPOND_PROMPT.lower()
    assert "kiến thức chung" in prompt
    assert "không phải là nguồn đã xác minh" in prompt, (
        "Phải nói rõ trí nhớ model KHÔNG phải nguồn. Đây là gốc của lỗi: agent "
        "kể tiểu sử người sáng lập OpenAI rồi trace vẫn ghi grounded."
    )


@pytest.mark.parametrize("cau_hoi", CAU_HOI_DANH_TINH)
def test_cau_hoi_danh_tinh_khong_bi_regex_coi_la_loi_chao(cau_hoi: str) -> None:
    """Vì sao luật phải nằm ở prompt trả lời chung, không phải nhánh small-talk.

    `classify_query` là regex chỉ khớp lời chào chính xác. Câu hỏi danh tính
    KHÔNG khớp, nên chúng rơi vào lane work — và luật phải có mặt ở đó.
    """
    from src.services.llm_routing import RouteLane, classify_query

    assert classify_query(cau_hoi) != RouteLane.SMALL_TALK, (
        "Nếu ca này bắt đầu khớp small-talk, luật danh tính phải được thêm vào "
        "cả nhánh đó nữa — đừng để nó chỉ nằm ở một đường."
    )


def test_small_talk_prompt_chet_da_duoc_don() -> None:
    """`_SMALL_TALK_PROMPT` nằm chết trong file từ 15/08, không nơi nào dùng.

    Giữ một prompt không ai gọi là để dành một cái bẫy: người sau đọc thấy luật
    trong đó và tưởng nó đang có hiệu lực.
    """
    import src.agents.nodes.core_nodes as nodes

    assert not hasattr(nodes, "_SMALL_TALK_PROMPT")
