"""Embedding hỏng thì phải để lại dấu vết đọc được, không hạ cấp trong im lặng.

Chuyện đã xảy ra: nhà cung cấp embedding trả HTTP 402 "insufficient credits" —
tài khoản chưa từng mua credit — nên `classify_intent` ném lỗi ở MỌI lượt và rơi
về GENERAL_WORK. Tức phân loại ý định chưa từng chạy trên production.

Không ai phát hiện, vì nhánh except chỉ ghi `type(exc).__name__` ở mức warning:
log chỉ hiện "HTTPStatusError" — không mã lỗi, không thông điệp, không nguyên
nhân. Hệ thống vẫn trả lời như thường và vẫn tự nhận là grounded.

Test này khoá lại yêu cầu: hạ cấp thì được, im lặng thì không.
"""

from __future__ import annotations

import logging

import pytest

from src.agents.briefing import intent as intent_module
from src.agents.briefing.intent import BriefIntent, classify_intent


@pytest.fixture
def embedding_hong(monkeypatch: pytest.MonkeyPatch):
    def _no(*_args, **_kwargs):
        raise RuntimeError("402 Insufficient credits: tài khoản chưa mua credit")

    monkeypatch.setattr(intent_module, "_embedding_backend", lambda: _no)


def test_van_tra_ve_ket_qua_an_toan_khi_embedding_hong(embedding_hong) -> None:
    """Hạ cấp vẫn phải hạ cấp — không được ném lỗi ra ngoài làm hỏng cả lượt chat."""
    decision = classify_intent("hôm nay tôi cần làm gì")

    assert decision.intent == BriefIntent.GENERAL_WORK
    assert decision.backend == "shared_rag_embedding_unavailable"
    assert decision.matched_by == "embedding_error"


def test_ghi_log_muc_error_kem_nguyen_van_loi(
    embedding_hong, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=intent_module.logger.name):
        classify_intent("hôm nay tôi cần làm gì")

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, (
        "Embedding hỏng mà không có log mức ERROR nào. Đây đúng là lý do sự cố "
        "402 sống sót lâu như vậy mà không ai thấy — đừng hạ mức log xuống warning."
    )

    ghep = " ".join(r.getMessage() for r in errors)
    assert "402" in ghep and "credit" in ghep.casefold(), (
        f"Log không mang nguyên văn lỗi nên không chẩn đoán được: {ghep!r}. "
        "Ghi cả exception, đừng chỉ ghi type(exc).__name__."
    )
    assert any(r.exc_info for r in errors), "Thiếu traceback (exc_info=True)."


def test_small_talk_khong_can_toi_embedding(embedding_hong) -> None:
    """Nhánh guardrail phải đi trước, không kéo theo lỗi hạ tầng."""
    decision = classify_intent("hello")

    assert decision.intent == BriefIntent.SMALL_TALK
    assert decision.backend == "exact_guardrail"
