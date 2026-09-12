"""Suite không được gọi mạng thật, dù máy phát triển có key trong .env.

Chuyện đã xảy ra: `conftest` xoá `OPENAI_API_KEY` nhưng bỏ sót
`OPENROUTER_API_KEY`. `embed_queries` — dùng chung cho phân loại ý định lẫn RAG
— gọi thẳng OpenRouter, nên trên mọi máy có `.env` thì test gọi mạng THẬT ở mỗi
lượt agent, ăn 402/429 rồi retry có backoff.

Đo trên một test hội thoại: **18,12s khi có key, 1,61s khi không**. Cả suite đi
từ 19 phút xuống còn khoảng 6.

Chậm chỉ là triệu chứng dễ thấy. Vấn đề thật là test đọc kết quả mạng, nên kết
quả của chúng phụ thuộc vào việc một tài khoản ở đâu đó còn credit hay không —
đúng loại phụ thuộc làm test xanh/đỏ vì lý do chẳng liên quan tới code.
"""

from __future__ import annotations

import os

import pytest

# Mọi biến ở đây phải rỗng trong lúc chạy test. Thêm nhà cung cấp mới thì thêm
# vào cả conftest lẫn danh sách này — đó chính là bước đã bị bỏ sót lần trước.
KEY_PHAI_RONG = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
)


@pytest.mark.parametrize("ten_bien", KEY_PHAI_RONG)
def test_key_nha_cung_cap_phai_rong_trong_test(ten_bien: str) -> None:
    assert not os.environ.get(ten_bien), (
        f"{ten_bien} có giá trị trong lúc chạy test, nên suite đang gọi mạng "
        f"thật. Xoá nó trong tests/conftest.py như các key khác; đừng chỉ mock "
        f"từng chỗ gọi, vì chỗ gọi tiếp theo sẽ lại bị bỏ sót."
    )


def test_settings_cung_thay_key_rong() -> None:
    """Xoá biến môi trường là chưa đủ nếu Settings còn đọc từ .env."""
    from src.config import get_settings

    settings = get_settings()

    assert not settings.openai_api_key, "Settings vẫn đọc được openai_api_key."
    assert not settings.openrouter_api_key, (
        "Settings vẫn đọc được openrouter_api_key — pydantic đang lấy từ .env "
        "bất chấp biến môi trường đã bị xoá."
    )
