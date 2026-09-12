from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.services.llm as llm_module
from src.services.llm import FailoverChatModel


class _Provider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0
        self.last_kwargs = {}

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return self

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        return self.result


class _SequenceProvider(_Provider):
    def __init__(self, outcomes):
        super().__init__()
        self.outcomes = list(outcomes)

    async def ainvoke(self, messages, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_failover_moves_to_next_provider_on_rate_limit():
    first = _Provider(error=RuntimeError("HTTP 429 rate limit"))
    second = _Provider(result="groq-result")

    result = await FailoverChatModel([first, second]).ainvoke("hello")

    assert result == "groq-result"
    assert first.calls == 1
    assert second.calls == 1


@pytest.mark.asyncio
async def test_failover_preserves_tool_binding():
    first = _Provider(error=RuntimeError("HTTP 503 unavailable"))
    second = _Provider(result="ok")

    result = await FailoverChatModel([first, second]).bind_tools(["tool"]).ainvoke("hello")

    assert result == "ok"


@pytest.mark.asyncio
async def test_failover_preserves_structured_output_binding():
    """Regression: get_llm() trả FailoverChatModel theo default config (LLM_PROVIDERS
    có nhiều provider) — extract_batch.py gọi .with_structured_output() thẳng lên đó,
    thiếu proxy method là AttributeError giữa chừng sync (xem extract_batch.py:118)."""
    first = _Provider(error=RuntimeError("HTTP 503 unavailable"))
    second = _Provider(result="structured-ok")

    result = await FailoverChatModel([first, second]).with_structured_output(dict).ainvoke("hello")

    assert result == "structured-ok"
    assert first.calls == 1
    assert second.calls == 1


@pytest.mark.asyncio
async def test_failover_moves_on_tool_use_failed_400():
    first = _Provider(error=RuntimeError("HTTP 400 code=tool_use_failed"))
    second = _Provider(result="fallback-result")

    result = await FailoverChatModel([first, second]).bind_tools(["tool"]).ainvoke("hello")

    assert result == "fallback-result"
    assert first.calls == 1
    assert second.calls == 1
    assert second.last_kwargs["config"]["metadata"]["fallback_reason"] == "tool_use_failed"


@pytest.mark.asyncio
async def test_failover_does_not_retry_generic_400():
    first = _Provider(error=RuntimeError("HTTP 400 invalid_request_error"))
    second = _Provider(result="must-not-run")

    with pytest.raises(RuntimeError, match="invalid_request_error"):
        await FailoverChatModel([first, second]).ainvoke("hello")

    assert second.calls == 0


@pytest.mark.asyncio
async def test_failover_retries_whole_chain_after_short_rate_limit(monkeypatch):
    """Regression: both providers can transiently 429 before Calendar is read."""
    first = _Provider(error=RuntimeError("HTTP 429 rate limit"))
    second = _SequenceProvider([RuntimeError("HTTP 429; please try again in 0.01s"), "recovered"])
    sleep = AsyncMock()
    monkeypatch.setattr(llm_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        llm_module,
        "get_settings",
        lambda: type("Settings", (), {"llm_max_retries": 1})(),
    )

    result = await FailoverChatModel([first, second]).ainvoke("calendar")

    assert result == "recovered"
    assert first.calls == 2
    assert second.calls == 2
    sleep.assert_awaited_once_with(0.01)
    assert second.last_kwargs["config"]["metadata"]["retry_index"] == 1


def test_routed_candidates_prioritize_free_and_keep_fallback(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "llm_routing_enabled": True,
            "small_talk_candidates": "groq:paid-model|paid,openrouter:free-model|free",
            "work_tool_candidates": "",
            "work_response_candidates": "",
            "paid_fallback_enabled": True,
            "llm_candidate_max_attempts": 1,
        },
    )()
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        llm_module,
        "_rotating_provider",
        lambda provider, model, lane=None: (provider, model, lane),
    )

    result = llm_module.get_llm("small_talk")

    # Lane đi kèm xuống tận provider vì nó quyết định temperature của lời gọi.
    assert result._providers == [
        ("openrouter", "free-model", "small_talk"),
        ("groq", "paid-model", "small_talk"),
    ]


def test_lane_chon_tool_chay_temperature_khong(monkeypatch):
    """Lượt chọn công cụ phải lặp lại được; lượt viết văn thì vẫn được ngẫu nhiên."""
    settings = SimpleNamespace(llm_temperature=0.7, llm_tool_temperature=0.0)
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)

    assert llm_module._lane_temperature("work_tool") == 0.0
    assert llm_module._lane_temperature("work_response") == 0.7
    assert llm_module._lane_temperature("small_talk") == 0.7
    assert llm_module._lane_temperature(None) == 0.7


def test_client_duoc_dung_lai_theo_cau_hinh():
    """Dựng ChatOpenAI mới mỗi lời gọi là bắt tay TLS lại cho từng lượt."""
    llm_module._chat_client.cache_clear()
    dau = llm_module._chat_client("m", "k", "https://x/v1", 0.0, 30.0, "work_tool")
    lap_lai = llm_module._chat_client("m", "k", "https://x/v1", 0.0, 30.0, "work_tool")
    khac_temperature = llm_module._chat_client("m", "k", "https://x/v1", 0.7, 30.0, "work_tool")
    khac_lane = llm_module._chat_client("m", "k", "https://x/v1", 0.0, 30.0, "work_response")

    assert dau is lap_lai
    # Temperature nằm trong khoá cache: dùng nhầm client là chạy sai lane mà
    # không có dấu hiệu gì.
    assert dau is not khac_temperature
    # Callback gắn lane lúc dựng client; dùng lại chéo lane sẽ ghi metric sai.
    assert dau is not khac_lane


def test_client_co_timeout_va_khong_tu_retry():
    """Thiếu timeout thì provider treo sẽ chặn luôn chuỗi failover."""
    llm_module._chat_client.cache_clear()
    client = llm_module._chat_client("m", "k", "https://x/v1", 0.0, 12.5, "work_response")

    assert client.request_timeout == 12.5
    # Việc thử lại thuộc về FailoverChatModel, không phải SDK.
    assert client.max_retries == 0


class _StructuredProvider(_Provider):
    """Provider ghi lại schema đã nhận, để kiểm tra schema không bị rơi mất."""

    def __init__(self, result=None, error=None):
        super().__init__(result=result, error=error)
        self.schema = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self


@pytest.mark.asyncio
async def test_failover_preserves_structured_output_schema():
    """extract_batch và meeting notes đều gọi with_structured_output trên client
    do get_llm() trả về — nếu chuỗi failover đánh rơi schema thì hai luồng đó
    nhận về text thô thay vì đối tượng đã parse."""
    first = _StructuredProvider(error=RuntimeError("HTTP 429 rate limit"))
    second = _StructuredProvider(result="parsed")

    result = await FailoverChatModel([first, second]).with_structured_output(dict).ainvoke("hello")

    assert result == "parsed"
    assert first.schema is dict
    assert second.schema is dict


@pytest.mark.asyncio
async def test_rotating_model_applies_structured_schema_per_key(monkeypatch):
    """Client được dựng lại theo từng key trong pool, nên schema phải áp lại sau
    khi chọn key chứ không phải một lần lúc gọi with_structured_output."""
    built: list = []

    class _Client:
        def __init__(self):
            self.schema = None

        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            built.append(self)
            return self

        async def ainvoke(self, messages, **kwargs):
            return "parsed"

    monkeypatch.setattr(llm_module, "_chat_client", lambda *args, **kwargs: _Client())
    pool = SimpleNamespace(size=1, next_key=lambda: "key-1", mark_unavailable=lambda key: None)
    model = llm_module.RotatingChatModel(pool, "https://example.test", "model-x", "openrouter", "work_response")

    result = await model.with_structured_output(dict).ainvoke("hello")

    assert result == "parsed"
    assert [client.schema for client in built] == [dict]
