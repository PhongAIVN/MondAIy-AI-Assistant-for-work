"""Cờ Responses API cho provider OpenAI.

Vì sao cần cờ này: dòng `gpt-5.6` từ chối function tool trên
`/v1/chat/completions` — gọi `bind_tools` là ăn 400 "Function tools with
reasoning_effort are not supported ... in /v1/chat/completions". Đã kiểm trực
tiếp trên production key: `gpt-5.6-luna` gọi tool được khi và chỉ khi
`use_responses_api=True`.

Rủi ro thật của cờ này không phải "bật có chạy không" mà là hai chuyện khác:

1. `_chat_client` được `lru_cache` bọc. Nếu cờ không nằm trong khoá cache thì
   hai cấu hình khác nhau dùng chung một client và hệ thống chạy sai cấu hình
   một cách im lặng — đúng lý do temperature và timeout đã là tham số.
2. openrouter và groq KHÔNG có endpoint này. Rò cờ sang đường rotating là làm
   hỏng mọi lời gọi qua hai provider đó.

Cả hai đều được khoá ở dưới.
"""

from __future__ import annotations

from typing import Any

import pytest

import src.services.llm as llm_module


@pytest.fixture(autouse=True)
def _clear_client_cache():
    llm_module._chat_client.cache_clear()
    yield
    llm_module._chat_client.cache_clear()


def _captured_kwargs(monkeypatch) -> list[dict[str, Any]]:
    ghi_lai: list[dict[str, Any]] = []

    class _FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            ghi_lai.append(kwargs)

    monkeypatch.setattr(llm_module, "ChatOpenAI", _FakeChatOpenAI)
    return ghi_lai


def test_cờ_tắt_thì_không_gửi_use_responses_api(monkeypatch) -> None:
    ghi_lai = _captured_kwargs(monkeypatch)
    llm_module._chat_client("gpt-4o-mini", "k", None, 0.0, 30.0, "work_tool", False)
    assert "use_responses_api" not in ghi_lai[0]


def test_cờ_bật_thì_gửi_use_responses_api(monkeypatch) -> None:
    ghi_lai = _captured_kwargs(monkeypatch)
    llm_module._chat_client("gpt-5.6-luna", "k", None, 0.0, 30.0, "work_tool", True)
    assert ghi_lai[0]["use_responses_api"] is True


def test_cờ_nằm_trong_khoá_cache(monkeypatch) -> None:
    """Hai giá trị cờ phải cho ra hai client, không dùng chung một cái.

    Đây là lỗi nguy hiểm nhất của thay đổi này: cache trả nhầm client thì
    `bind_tools` đi sai endpoint và chỉ lộ ra lúc chạy thật.
    """
    ghi_lai = _captured_kwargs(monkeypatch)
    llm_module._chat_client("gpt-5.6-luna", "k", None, 0.0, 30.0, "work_tool", False)
    llm_module._chat_client("gpt-5.6-luna", "k", None, 0.0, 30.0, "work_tool", True)
    assert len(ghi_lai) == 2, "cache đã trả nhầm client cho cấu hình khác"
    assert ghi_lai[0].get("use_responses_api") is None
    assert ghi_lai[1]["use_responses_api"] is True


@pytest.mark.asyncio
async def test_đường_rotating_không_bao_giờ_bật_cờ(monkeypatch) -> None:
    """openrouter/groq không có Responses API — cờ không được rò sang đó."""
    ghi_lai = _captured_kwargs(monkeypatch)

    monkeypatch.setattr(
        llm_module,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "llm_request_timeout_seconds": 30.0,
                "llm_temperature": 0.7,
                "llm_tool_temperature": 0.0,
                # Bật ở mức global: nếu code đọc nhầm biến này cho đường
                # rotating thì test dưới sẽ đỏ.
                "llm_use_responses_api": True,
                "llm_max_retries": 0,
            },
        )(),
    )

    class _Pool:
        size = 1

        def next_key(self) -> str:
            return "k"

    model = llm_module.RotatingChatModel.__new__(llm_module.RotatingChatModel)
    model._pool = _Pool()
    model._model = "openai/gpt-oss-20b"
    model._base_url = "https://openrouter.ai/api/v1"
    model._lane = "work_tool"

    with pytest.raises(Exception):
        # `_FakeChatOpenAI` không có `ainvoke`; ta chỉ quan tâm kwargs lúc dựng.
        await model._ainvoke("xin chào")

    assert ghi_lai, "chưa dựng client nào"
    assert all("use_responses_api" not in kw for kw in ghi_lai)
