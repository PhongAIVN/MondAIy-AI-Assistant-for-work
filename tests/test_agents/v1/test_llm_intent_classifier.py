"""Phân loại ý định bằng LLM: thứ tự backend, ràng buộc enum, và đường hạ cấp.

Bối cảnh (ADR-020 QĐ-1): đường embedding gọi OpenRouter và trả 402 ở mọi lượt,
nên tầng intent chưa từng chạy trên production. Lượt chat đã dùng OpenAI sẵn nên
phân loại bằng chính nhà cung cấp đó gỡ nút thắt mà không cần nạp credit.

Không test nào ở đây gọi mạng thật.
"""

from __future__ import annotations

import logging

import pytest

from src.agents.briefing import intent as intent_module
from src.agents.briefing import llm_intent
from src.agents.briefing.intent import BriefIntent, classify_intent_async


@pytest.fixture
def llm_tra_ve(monkeypatch: pytest.MonkeyPatch):
    def _cai(label: str, confidence: float = 0.9):
        async def _fake(_query):
            return label, confidence

        # `intent.py` import hàm này BÊN TRONG hàm, nên vá thuộc tính của chính
        # module llm_intent là đủ và đúng chỗ.
        monkeypatch.setattr(llm_intent, "classify_with_llm", _fake)
        return _fake

    return _cai


@pytest.fixture
def llm_khong_dung_duoc(monkeypatch: pytest.MonkeyPatch):
    async def _fake(_query):
        return None

    monkeypatch.setattr(llm_intent, "classify_with_llm", _fake)


@pytest.mark.asyncio
async def test_small_talk_khong_ton_mot_luot_goi_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guardrail chạy trước mọi backend — chào hỏi không đáng một lời gọi model."""
    async def _no(_query):
        raise AssertionError("small talk không được gọi tới LLM")

    monkeypatch.setattr(llm_intent, "classify_with_llm", _no)

    decision = await classify_intent_async("hello")
    assert decision.intent == BriefIntent.SMALL_TALK
    assert decision.backend == "exact_guardrail"


@pytest.mark.asyncio
async def test_dung_ket_qua_llm_va_ghi_ro_backend(llm_tra_ve) -> None:
    llm_tra_ve("daily_brief", 0.88)

    decision = await classify_intent_async("hôm nay tôi cần làm gì")

    assert decision.intent == BriefIntent.DAILY_BRIEF
    assert decision.backend == "llm_structured_output", (
        "trace phải nói rõ nhánh nào quyết định; bản cũ không ghi nên một sự cố "
        "toàn phần sống sót nhiều tuần mà không ai thấy"
    )
    assert decision.score == pytest.approx(0.88)


@pytest.mark.asyncio
async def test_nhan_la_roi_ve_general_work_va_keu_len(
    llm_tra_ve, caplog: pytest.LogCaptureFixture
) -> None:
    """Schema đóng lẽ ra chặn được, nhưng không được tin điều đó một cách mù quáng."""
    llm_tra_ve("lane_tu_bia_ra", 0.99)

    with caplog.at_level(logging.DEBUG, logger=intent_module.logger.name):
        decision = await classify_intent_async("câu hỏi bất kỳ về công việc")

    assert decision.intent == BriefIntent.GENERAL_WORK
    assert [r for r in caplog.records if r.levelno >= logging.ERROR], (
        "nhãn lạ phải kêu lên, không được lặng lẽ thành một lane nào đó"
    )


@pytest.mark.asyncio
async def test_yeu_cau_ghi_ro_rang_van_qua_guardrail(llm_tra_ve) -> None:
    """explicit_action là guardrail, phải áp cho MỌI backend, không riêng embedding."""
    llm_tra_ve("schedule", 0.9)

    decision = await classify_intent_async("tạo event họp mentor ngày mai trên lịch")

    assert decision.intent == BriefIntent.EXPLICIT_ACTION
    assert decision.matched_by == "explicit_action_guardrail"


@pytest.mark.asyncio
async def test_llm_khong_dung_duoc_thi_ha_cap_chu_khong_no(llm_khong_dung_duoc) -> None:
    """Tắt cờ, thiếu key hoặc lỗi mạng đều không được làm hỏng lượt chat."""
    decision = await classify_intent_async("hôm nay tôi cần làm gì")

    assert decision.intent in set(BriefIntent)
    assert decision.backend != "llm_structured_output"


@pytest.mark.asyncio
async def test_cau_qua_dai_khong_di_qua_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Câu dài gần như luôn là nội dung dán vào — bề mặt cho prompt injection."""
    from src.config import get_settings

    goi = []

    class _ClientGia:
        def with_structured_output(self, _schema):
            goi.append(1)
            raise AssertionError("câu quá dài không được gửi tới model")

    monkeypatch.setattr(llm_intent, "_client", lambda *_args: _ClientGia())
    get_settings.cache_clear()

    ket_qua = await llm_intent.classify_with_llm("x" * 5000)

    assert ket_qua is None
    assert not goi


@pytest.mark.asyncio
async def test_tat_co_thi_khong_goi_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.config import get_settings

    monkeypatch.setenv("LLM_INTENT_ENABLED", "false")
    get_settings.cache_clear()
    try:

        class _ClientGia:
            def with_structured_output(self, _schema):
                raise AssertionError("tắt cờ mà vẫn gọi model")

        monkeypatch.setattr(llm_intent, "_client", lambda *_args: _ClientGia())
        assert await llm_intent.classify_with_llm("hôm nay làm gì") is None
    finally:
        get_settings.cache_clear()
