from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

_GRAPH_NODES = {"think", "action", "observe", "respond"}
_PRIVATE_RESULT_FIELDS = frozenset({"analysis"})


def _message_text(chunk: Any) -> str:
    """Extract user-visible text from a LangChain message chunk."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def _tool_names(state: Any, key: str) -> list[str]:
    if not isinstance(state, Mapping):
        return []
    values = state.get(key)
    if not isinstance(values, list):
        return []
    return [str(item.get("name")) for item in values if isinstance(item, Mapping) and item.get("name")]


def _sources(state: Any) -> list[dict]:
    """Nguồn có cấu trúc mà `observe` đã gom vào metadata, nếu có.

    Chỉ đọc, không dựng lại: node mới là chỗ biết observation nào có link.
    """
    if not isinstance(state, Mapping):
        return []
    values = (state.get("metadata") or {}).get("sources")
    return [item for item in values if isinstance(item, Mapping)] if isinstance(values, list) else []


def _is_public_response_chunk(metadata: Mapping[str, Any]) -> bool:
    """Only stream final-answer tokens, never work-lane planning tokens."""
    node = metadata.get("langgraph_node")
    route_lane = metadata.get("route_lane")
    return node == "respond" or (node == "think" and route_lane == "small_talk")


async def stream_agent_execution(graph: Any, state: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
    """Turn LangGraph runtime events into the public SSE protocol.

    The API layer serializes these records. ``progress`` is intentionally
    semantic and contains no prompts, tool arguments, observations, or hidden
    reasoning. ``token`` is emitted only for a user-visible model response.
    """
    root_run_id: str | None = None
    final_state: dict[str, Any] | None = None
    streamed_text = False

    async for event in graph.astream_events(state, version="v2"):
        event_type = event.get("event")
        name = event.get("name")
        run_id = event.get("run_id")
        metadata = event.get("metadata") or {}
        data = event.get("data") or {}

        if root_run_id is None and event_type == "on_chain_start" and not event.get("parent_ids"):
            root_run_id = run_id

        node = metadata.get("langgraph_node")
        if event_type == "on_chain_start" and name == node and node in _GRAPH_NODES:
            input_state = data.get("input")
            if node == "think":
                yield {"event": "progress", "data": {"phase": "thinking"}}
            elif node == "action":
                tools = _tool_names(input_state, "pending_tool_calls")
                if tools:
                    for tool in tools:
                        yield {"event": "progress", "data": {"phase": "calling", "tool": tool}}
                else:
                    yield {"event": "progress", "data": {"phase": "calling"}}
            elif node == "observe":
                tools = _tool_names(input_state, "latest_observations")
                if tools:
                    for tool in tools:
                        yield {"event": "progress", "data": {"phase": "observing", "tool": tool}}
                else:
                    yield {"event": "progress", "data": {"phase": "observing"}}
            elif node == "respond":
                # Bắn kèm nguồn ngay khi bắt đầu viết câu trả lời, thay vì chờ
                # tới `done`: giao diện dựng được danh sách nguồn trong lúc chữ
                # còn đang chảy, người dùng không phải đợi hết câu mới thấy.
                sources = _sources(input_state)
                yield {
                    "event": "progress",
                    "data": {"phase": "responding", **({"sources": sources} if sources else {})},
                }

        if event_type == "on_chat_model_stream" and _is_public_response_chunk(metadata):
            delta = _message_text(data.get("chunk"))
            if delta:
                streamed_text = True
                yield {"event": "token", "data": {"delta": delta}}

        if event_type == "on_chain_end" and run_id == root_run_id:
            output = data.get("output")
            if isinstance(output, Mapping):
                final_state = dict(output)

    if final_state is None:
        raise RuntimeError("Agent stream ended without a final state.")

    # Small-talk models or test doubles may not expose model chunk callbacks.
    # Keep the endpoint usable while preserving true token streaming whenever
    # LangChain emits it.
    response = str(final_state.get("response") or "")
    if response and not streamed_text:
        yield {"event": "token", "data": {"delta": response}}

    # `analysis` là điều phối nội bộ của think, không phải một phần của SSE
    # contract. API consumers nhận result này để dựng event `done`, nên redact
    # ngay ở shared stream boundary thay vì tin từng consumer nhớ tự bỏ field.
    public_result = {key: value for key, value in final_state.items() if key not in _PRIVATE_RESULT_FIELDS}
    yield {"event": "result", "data": public_result}
