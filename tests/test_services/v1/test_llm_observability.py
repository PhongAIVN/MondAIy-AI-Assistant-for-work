from __future__ import annotations

import hashlib
import hmac
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from src.services import llm_observability


def _sample_value(name: str, **labels: str) -> float:
    payload = generate_latest().decode("utf-8")
    for family in text_string_to_metric_families(payload):
        for sample in family.samples:
            if sample.name == name and all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0


def _response(usage: dict[str, int] | None) -> LLMResult:
    message = AIMessage(content="ok", usage_metadata=usage)
    return LLMResult(generations=[[ChatGeneration(message=message)]])


def _settings(*, secret: str = "test-hmac-secret", pricing: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        app_secret_key=secret,
        llm_model_pricing_usd_per_million=pricing or {},
    )


def test_usage_metadata_records_tokens_cost_latency_and_only_hmac_user(monkeypatch: pytest.MonkeyPatch) -> None:
    model = "priced-model-observability-test"
    lane = "usage-positive-test"
    raw_user = "raw-user-9f31:thai.private@example.test"
    secret = "stable-private-test-secret"
    monkeypatch.setattr(
        llm_observability,
        "get_settings",
        lambda: _settings(secret=secret, pricing={model: {"input": 2.0, "output": 4.0}}),
    )
    monkeypatch.setattr(llm_observability, "current_agent_user_id", lambda: raw_user)
    clock = iter((100.0, 100.25))
    monkeypatch.setattr(llm_observability.time, "perf_counter", lambda: next(clock))

    before_input = _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input")
    before_output = _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="output")
    before_cost = _sample_value("p004_llm_estimated_cost_usd_total", model=model, lane=lane)
    before_duration_count = _sample_value("p004_llm_call_duration_seconds_count", model=model, lane=lane)
    before_duration_sum = _sample_value("p004_llm_call_duration_seconds_sum", model=model, lane=lane)

    callback = llm_observability.LLMObservabilityCallback(model, lane)
    run_id = uuid4()
    callback.on_chat_model_start({}, [[]], run_id=run_id)
    callback.on_llm_end(
        _response({"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}),
        run_id=run_id,
    )

    expected_hash = hmac.new(
        secret.encode("utf-8"),
        f"p004-llm-usage-v1:{raw_user}".encode(),
        hashlib.sha256,
    ).hexdigest()[:24]
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input") == before_input + 100
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="output") == before_output + 50
    assert _sample_value("p004_llm_estimated_cost_usd_total", model=model, lane=lane) == pytest.approx(
        before_cost + 0.0004
    )
    assert _sample_value("p004_llm_call_duration_seconds_count", model=model, lane=lane) == before_duration_count + 1
    assert _sample_value("p004_llm_call_duration_seconds_sum", model=model, lane=lane) == pytest.approx(
        before_duration_sum + 0.25
    )
    assert _sample_value("p004_llm_calls_total", model=model, lane=lane, status="success") >= 1
    assert _sample_value("p004_llm_user_tokens_total", user_hash=expected_hash, direction="input") == 100
    assert _sample_value("p004_llm_user_tokens_total", user_hash=expected_hash, direction="output") == 50
    assert _sample_value("p004_llm_user_estimated_cost_usd_total", user_hash=expected_hash) == pytest.approx(0.0004)

    scrape = generate_latest().decode("utf-8")
    assert raw_user not in scrape
    assert "thai.private@example.test" not in scrape
    assert expected_hash in scrape


def test_missing_usage_does_not_invent_tokens_and_increments_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    model = "missing-usage-model-test"
    lane = "missing-usage-lane-test"
    monkeypatch.setattr(llm_observability, "get_settings", lambda: _settings())
    monkeypatch.setattr(llm_observability, "current_agent_user_id", lambda: "private-user-missing-usage")
    clock = iter((200.0, 200.1))
    monkeypatch.setattr(llm_observability.time, "perf_counter", lambda: next(clock))
    before_missing = _sample_value("p004_llm_usage_metadata_missing_total", model=model, lane=lane)
    before_input = _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input")
    before_output = _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="output")

    callback = llm_observability.LLMObservabilityCallback(model, lane)
    run_id = uuid4()
    callback.on_chat_model_start({}, [[]], run_id=run_id)
    callback.on_llm_end(_response(None), run_id=run_id)

    assert _sample_value("p004_llm_usage_metadata_missing_total", model=model, lane=lane) == before_missing + 1
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input") == before_input
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="output") == before_output


def test_unknown_model_counts_tokens_but_never_invents_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    model = "unknown-price-model-test"
    lane = "unknown-price-lane-test"
    monkeypatch.setattr(llm_observability, "get_settings", lambda: _settings(pricing={}))
    monkeypatch.setattr(llm_observability, "current_agent_user_id", lambda: "private-user-unknown-price")
    clock = iter((300.0, 300.2))
    monkeypatch.setattr(llm_observability.time, "perf_counter", lambda: next(clock))
    before_unknown = _sample_value("p004_llm_pricing_unknown_total", model=model, lane=lane)
    before_cost = _sample_value("p004_llm_estimated_cost_usd_total", model=model, lane=lane)

    callback = llm_observability.LLMObservabilityCallback(model, lane)
    run_id = uuid4()
    callback.on_chat_model_start({}, [[]], run_id=run_id)
    callback.on_llm_end(
        _response({"input_tokens": 7, "output_tokens": 11, "total_tokens": 18}),
        run_id=run_id,
    )

    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input") == 7
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="output") == 11
    assert _sample_value("p004_llm_pricing_unknown_total", model=model, lane=lane) == before_unknown + 1
    assert _sample_value("p004_llm_estimated_cost_usd_total", model=model, lane=lane) == before_cost


@pytest.mark.parametrize(
    ("error", "status"),
    [(RuntimeError("provider failed"), "error"), (TimeoutError("provider timed out"), "timeout")],
)
def test_error_and_timeout_have_bounded_status_without_token_usage(
    monkeypatch: pytest.MonkeyPatch,
    error: BaseException,
    status: str,
) -> None:
    model = f"terminal-{status}-model-test"
    lane = f"terminal-{status}-lane-test"
    private_error = type(error)(f"{error} for thai.error@example.test")
    monkeypatch.setattr(llm_observability, "current_agent_user_id", lambda: "raw-user-error-test")
    clock = iter((400.0, 400.3))
    monkeypatch.setattr(llm_observability.time, "perf_counter", lambda: next(clock))
    before_calls = _sample_value("p004_llm_calls_total", model=model, lane=lane, status=status)
    before_duration = _sample_value("p004_llm_call_duration_seconds_count", model=model, lane=lane)

    callback = llm_observability.LLMObservabilityCallback(model, lane)
    run_id = uuid4()
    callback.on_chat_model_start({}, [[]], run_id=run_id)
    callback.on_llm_error(private_error, run_id=run_id)

    assert _sample_value("p004_llm_calls_total", model=model, lane=lane, status=status) == before_calls + 1
    assert _sample_value("p004_llm_call_duration_seconds_count", model=model, lane=lane) == before_duration + 1
    assert _sample_value("p004_llm_tokens_total", model=model, lane=lane, direction="input") == 0
    assert _sample_value("p004_llm_usage_metadata_missing_total", model=model, lane=lane) == 0
    assert "thai.error@example.test" not in generate_latest().decode("utf-8")
