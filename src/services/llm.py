import asyncio
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.services.llm_observability import llm_callbacks
from src.services.openrouter_keys import (
    OpenRouterKeyPool,
    build_groq_key_pool,
    build_openrouter_key_pool,
)

logger = logging.getLogger(__name__)


def _status_code(error: Exception) -> int | None:
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None) or getattr(error, "status_code", None)


def _should_failover(error: Exception) -> bool:
    code = _status_code(error)
    if code in {401, 402, 403, 408, 409, 429, 500, 502, 503, 504}:
        return True
    # A provider can return malformed tool calls as HTTP 400.  This is a
    # candidate capability failure, not a user request/schema failure.
    if code == 400 and "tool_use_failed" in str(error):
        return True
    if "tool_use_failed" in str(error) and any(token in str(error) for token in (" 400", "HTTP 400", "code=400")):
        return True
    return any(
        token in str(error)
        for token in (
            " 401",
            " 402",
            " 403",
            " 429",
            " 500",
            " 502",
            " 503",
            " 504",
        )
    )


def _fallback_reason(error: Exception) -> str:
    message = str(error)
    if "tool_use_failed" in message:
        return "tool_use_failed"
    code = _status_code(error)
    if code == 429 or " 429" in message:
        return "rate_limit"
    if code in {401, 402, 403}:
        return "auth_or_quota"
    if code in {500, 502, 503, 504}:
        return "provider_5xx"
    return "provider_error"


def _is_transient_retry(error: Exception) -> bool:
    code = _status_code(error)
    if code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    return any(marker in str(error) for marker in (" 408", " 409", " 429", " 500", " 502", " 503", " 504"))


def _retry_delay_seconds(error: Exception, retry_index: int) -> float:
    """Read provider advice when available, with a short bounded fallback."""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw_retry_after = headers.get("retry-after") or headers.get("Retry-After")
    try:
        if raw_retry_after is not None:
            return min(5.0, max(0.0, float(raw_retry_after)))
    except (TypeError, ValueError):
        pass

    match = re.search(r"(?i)try again in\s+([0-9]+(?:\.[0-9]+)?)s", str(error))
    if match:
        return min(5.0, max(0.0, float(match.group(1))))
    return min(4.0, 0.5 * (2**retry_index))


@dataclass(frozen=True)
class ModelCandidate:
    provider: str
    model: str
    cost_tier: str = "free"


# Lane chỉ để chọn công cụ, không viết văn cho người đọc. Sinh ngẫu nhiên ở đây
# nghĩa là cùng một câu hỏi lúc thì tra nguồn lúc thì không — đúng triệu chứng
# đã phải vá bằng regex trong nodes/core_nodes.py.
_DETERMINISTIC_LANES = {"work_tool"}


# Khối content mang chữ cho người dùng đọc. Khối `reasoning` KHÔNG nằm ở đây:
# nó là suy nghĩ nội bộ của model, có `encrypted_content` chứ không có `text`.
_TEXT_KEYS = ("text", "refusal")


def response_text(message: object) -> str:
    """Nội dung dạng chuỗi của một câu trả lời LLM, bất kể API nào sinh ra nó.

    `.content` KHÔNG cùng kiểu giữa hai endpoint của OpenAI:

        chat completions -> str
        responses        -> list[dict] các content block

    Dòng gpt-5.6 chỉ nhận function tool qua Responses API, nên bật
    `LLM_USE_RESPONSES_API` là mọi chỗ đọc `.content` như chuỗi sẽ nổ. Ca thật:
    `respond_node` truyền list vào `ground_candidate` và mọi lượt chat trả về
    "Lỗi: 'list' object has no attribute 'strip'".

    Và khi có tool, Luna trả về HAI khối chứ không phải một:

        [{"type": "reasoning", "encrypted_content": "gAAAAA...", ...},
         {"type": "text", "text": "Hạn nộp báo cáo là ngày 29/08."}]

    Bản sửa đầu tiên nối mọi khối lại nên dump nguyên JSON của khối reasoning ra
    cho người dùng đọc — hết crash nhưng câu trả lời thành rác. Vì vậy chỉ lấy
    khối mang chữ.

    Không im lặng khi gặp khối lạ: có khối mà không rút được chữ nào thì log
    warning. Trả rác cho người dùng còn tệ hơn bỏ khối, nhưng bỏ mà không ai
    biết thì lần sau không ai tìm ra.

    Không dùng `.text` của LangChain: ở bản đang cài nó vừa là property vừa gọi
    được như method và bản gọi-như-method đã deprecated — dựa vào nó là dựa vào
    thứ sắp đổi. Chuẩn hoá `content` thì độc lập phiên bản.
    """
    content = getattr(message, "content", message)
    if isinstance(content, list):
        phan: list[str] = []
        for part in content:
            if isinstance(part, str):
                phan.append(part)
                continue
            if not isinstance(part, dict):
                phan.append(str(part))
                continue
            for key in _TEXT_KEYS:
                gia_tri = part.get(key)
                if isinstance(gia_tri, str) and gia_tri:
                    phan.append(gia_tri)
                    break
        if content and not phan:
            logger.warning(
                "Câu trả lời LLM có %d content block nhưng không khối nào mang chữ; các type: %s",
                len(content),
                [part.get("type") if isinstance(part, dict) else type(part).__name__ for part in content],
            )
        return "\n".join(phan)
    if content is None:
        return ""
    return str(content)


def _lane_temperature(lane: str | None) -> float:
    """Nhiệt độ của một lane: lượt chọn tool cần lặp lại được, lượt viết thì không."""
    settings = get_settings()
    if lane in _DETERMINISTIC_LANES:
        return settings.llm_tool_temperature
    return settings.llm_temperature


@lru_cache(maxsize=256)
def _chat_client(
    model: str,
    api_key: str,
    base_url: str | None,
    temperature: float,
    timeout: float,
    lane: str | None,
    use_responses_api: bool = False,
) -> ChatOpenAI:
    """Client dùng lại theo cấu hình, thay vì dựng mới mỗi lời gọi.

    `ChatOpenAI` giữ connection pool bên trong. Dựng mới mỗi lần invoke nghĩa là
    bắt tay TLS lại từ đầu cho từng lượt gọi model, mà một lượt chat có thể gọi
    tới năm lần. Khoá cache gồm cả temperature và timeout vì hai giá trị đó khác
    nhau giữa các lane, dùng nhầm client là chạy sai cấu hình một cách im lặng.

    `max_retries=0` giữ nguyên: việc thử lại thuộc về `FailoverChatModel`, để SDK
    tự retry thì chuỗi provider không bao giờ được chạy tới.

    `base_url=None` nghĩa là để SDK tự quyết (OpenAI thật, hoặc biến môi trường
    OPENAI_BASE_URL). Truyền URL cứng vào đây sẽ chặn mất đường cấu hình đó.
    """
    optional: dict[str, Any] = {"base_url": base_url} if base_url else {}
    if use_responses_api:
        # Dòng gpt-5.6 KHÔNG nhận function tool qua /v1/chat/completions; gọi
        # `bind_tools` là ăn 400 "Function tools with reasoning_effort are not
        # supported ... in /v1/chat/completions". Responses API là đường duy
        # nhất chạy được, và nó cũng chạy tốt với gpt-4o-mini nên cờ này an
        # toàn để bật chung. Đã kiểm: usage_metadata vẫn đầy đủ trên đường này,
        # tức metric token/chi phí không bị mù.
        optional["use_responses_api"] = True
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=timeout,
        max_retries=0,
        callbacks=llm_callbacks(model, lane),
        **optional,
    )


def _parse_candidates(raw: str) -> list[ModelCandidate]:
    candidates: list[ModelCandidate] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        provider, separator, model_spec = value.partition(":")
        if not separator or not provider or not model_spec:
            continue
        model, marker, cost_tier = model_spec.rpartition("|")
        if not marker:
            model, cost_tier = model_spec, "free"
        if cost_tier not in {"free", "paid"}:
            model, cost_tier = model_spec, "free"
        candidates.append(ModelCandidate(provider.lower(), model, cost_tier))
    return candidates


def _candidate_config(settings: Any, lane: str) -> str:
    if lane == "small_talk":
        return settings.small_talk_candidates
    if lane == "work_tool":
        return settings.work_tool_candidates
    return settings.work_response_candidates


class _RotatingBoundLLM:
    def __init__(self, owner: "RotatingChatModel", tools: list[Any], kwargs: dict[str, Any]) -> None:
        self._owner = owner
        self._tools = tools
        self._kwargs = kwargs

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._owner._ainvoke(messages, tools=self._tools, bind_kwargs=self._kwargs, **kwargs)


class _RotatingStructuredLLM:
    def __init__(self, owner: "RotatingChatModel", schema: Any, kwargs: dict[str, Any]) -> None:
        self._owner = owner
        self._schema = schema
        self._kwargs = kwargs

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._owner._ainvoke(
            messages,
            structured_schema=self._schema,
            structured_kwargs=self._kwargs,
            **kwargs,
        )


class RotatingChatModel:
    """OpenAI-compatible provider client with API-key rotation."""

    def __init__(
        self,
        pool: OpenRouterKeyPool,
        base_url: str,
        model: str,
        provider: str = "unknown",
        lane: str | None = None,
    ) -> None:
        self._pool = pool
        self._base_url = base_url
        self._model = model
        self._provider = provider
        # Lane quyết định temperature. Giữ ở đây thay vì đọc lúc invoke để một
        # client đã dựng không đổi hành vi giữa chừng khi config được reload.
        self._lane = lane

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> _RotatingBoundLLM:
        return _RotatingBoundLLM(self, tools, kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _RotatingStructuredLLM:
        """Giữ nguyên vòng xoay key khi gọi model có schema ràng buộc.

        Không thể trả thẳng `ChatOpenAI.with_structured_output` vì client được
        dựng lại theo từng key trong pool; schema phải được áp ở thời điểm
        invoke, sau khi đã chọn được key còn dùng được.
        """
        return _RotatingStructuredLLM(self, schema, kwargs)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._ainvoke(messages, **kwargs)

    async def _ainvoke(
        self,
        messages: Any,
        tools: list[Any] | None = None,
        bind_kwargs: dict[str, Any] | None = None,
        structured_schema: Any = None,
        structured_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        attempts = max(1, self._pool.size)
        last_error: Exception | None = None
        settings = get_settings()
        for _ in range(attempts):
            key = self._pool.next_key()
            client = _chat_client(
                self._model,
                key,
                self._base_url,
                _lane_temperature(self._lane),
                settings.llm_request_timeout_seconds,
                self._lane,
                # openrouter/groq không có Responses API — cờ chỉ dành cho OpenAI.
                False,
            )
            if tools is not None:
                client = client.bind_tools(tools, **(bind_kwargs or {}))  # type: ignore[assignment]
            if structured_schema is not None:
                client = client.with_structured_output(  # type: ignore[assignment]
                    structured_schema,
                    **(structured_kwargs or {}),
                )
            try:
                return await client.ainvoke(messages, **kwargs)
            except Exception as error:
                last_error = error
                if not _should_failover(error):
                    raise
                self._pool.mark_unavailable(key)
        assert last_error is not None
        raise last_error


class _FailoverBoundLLM:
    def __init__(self, owner: "FailoverChatModel", tools: list[Any], kwargs: dict[str, Any]) -> None:
        self._owner = owner
        self._tools = tools
        self._kwargs = kwargs

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._owner._ainvoke(messages, tools=self._tools, bind_kwargs=self._kwargs, **kwargs)


class _FailoverStructuredLLM:
    def __init__(self, owner: "FailoverChatModel", schema: Any, kwargs: dict[str, Any]) -> None:
        self._owner = owner
        self._schema = schema
        self._kwargs = kwargs

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._owner._ainvoke(
            messages,
            structured_schema=self._schema,
            structured_kwargs=self._kwargs,
            **kwargs,
        )


class FailoverChatModel:
    """Try providers in order; key rotation happens inside each provider."""

    def __init__(self, providers: list[RotatingChatModel | ChatOpenAI]) -> None:
        self._providers = providers

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> _FailoverBoundLLM:
        return _FailoverBoundLLM(self, tools, kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _FailoverStructuredLLM:
        """Cùng lý do như bind_tools: schema phải áp lên provider được chọn tại
        thời điểm invoke, nếu không thì chuỗi failover không bao giờ chạy tới."""
        return _FailoverStructuredLLM(self, schema, kwargs)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._ainvoke(messages, **kwargs)

    async def _ainvoke(
        self,
        messages: Any,
        tools: list[Any] | None = None,
        bind_kwargs: dict[str, Any] | None = None,
        structured_schema: Any = None,
        structured_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        last_error: Exception | None = None
        max_retries = get_settings().llm_max_retries
        for retry_index in range(max_retries + 1):
            fallback_reason = ""
            for candidate_index, provider in enumerate(self._providers):
                try:
                    client: Any = provider
                    if tools is not None:
                        client = provider.bind_tools(tools, **(bind_kwargs or {}))
                    if structured_schema is not None:
                        client = provider.with_structured_output(structured_schema, **(structured_kwargs or {}))
                    invoke_kwargs = dict(kwargs)
                    config = dict(invoke_kwargs.get("config") or {})
                    metadata = dict(config.get("metadata") or {})
                    metadata.update(
                        {
                            "provider": getattr(provider, "_provider", "unknown"),
                            "model": getattr(provider, "_model", "unknown"),
                            "candidate_index": candidate_index,
                            "retry_index": retry_index,
                        }
                    )
                    if fallback_reason:
                        metadata["fallback_reason"] = fallback_reason
                    config["metadata"] = metadata
                    invoke_kwargs["config"] = config
                    return await client.ainvoke(messages, **invoke_kwargs)
                except Exception as error:
                    last_error = error
                    if not _should_failover(error):
                        raise
                    fallback_reason = _fallback_reason(error)

            assert last_error is not None
            if retry_index >= max_retries or not _is_transient_retry(last_error):
                raise last_error
            await asyncio.sleep(_retry_delay_seconds(last_error, retry_index))

        raise AssertionError("unreachable")


def _rotating_provider(name: str, model: str | None = None, lane: str | None = None) -> RotatingChatModel:
    settings = get_settings()
    if name == "openrouter":
        return RotatingChatModel(
            build_openrouter_key_pool(),
            settings.openrouter_base_url,
            model or settings.model_name,
            name,
            lane,
        )
    if name == "groq":
        return RotatingChatModel(
            build_groq_key_pool(),
            settings.groq_base_url,
            model or settings.groq_model_name,
            name,
            lane,
        )
    raise ValueError(f"Unsupported rotating LLM provider: {name}")


def get_llm(lane: str | None = None) -> FailoverChatModel | ChatOpenAI:
    settings = get_settings()
    if settings.llm_routing_enabled and lane:
        candidates = _parse_candidates(_candidate_config(settings, lane))
        candidates.sort(key=lambda candidate: candidate.cost_tier != "free")
        if not settings.paid_fallback_enabled:
            candidates = [candidate for candidate in candidates if candidate.cost_tier == "free"]
        providers: list[RotatingChatModel | ChatOpenAI] = []
        # Keep every compatible candidate in the chain.  The limit is reserved
        # for bounded retries per candidate; truncating here would disable
        # provider failover when the default is one.
        for candidate in candidates:
            if candidate.provider in {"openrouter", "groq"}:
                providers.append(_rotating_provider(candidate.provider, candidate.model, lane))
        if providers:
            return FailoverChatModel(providers)

    provider_names = [item.strip().lower() for item in settings.llm_providers.split(",") if item.strip()]
    if settings.llm_provider != "openai" and settings.llm_provider not in provider_names:
        provider_names.insert(0, settings.llm_provider)

    providers: list[RotatingChatModel | ChatOpenAI] = []
    for name in provider_names:
        if name in {"openrouter", "groq"}:
            try:
                # `llm_routing_enabled` mặc định tắt nên đây mới là nhánh đang
                # chạy thật. Lane vẫn phải truyền xuống, không thì temperature=0
                # của lượt chọn tool chỉ có tác dụng khi ai đó bật routing.
                providers.append(_rotating_provider(name, lane=lane))
            except ValueError:
                continue
    if providers:
        return FailoverChatModel(providers)

    return _chat_client(
        settings.model_name,
        settings.openai_api_key,
        None,
        _lane_temperature(lane),
        settings.llm_request_timeout_seconds,
        lane,
        settings.llm_use_responses_api,
    )
