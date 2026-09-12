from unittest.mock import AsyncMock, patch

import pytest

from src.services.conversation_title import ConversationTitle, fallback_conversation_title, suggest_conversation_title


@pytest.mark.asyncio
async def test_suggest_conversation_title_uses_gpt4o_mini_output(monkeypatch):
    monkeypatch.setattr("src.services.conversation_title.get_settings", lambda: type("S", (), {"openai_api_key": "test"})())
    structured = AsyncMock(return_value=ConversationTitle(title="Theo dõi deadline tuần này"))
    client = type("Client", (), {"with_structured_output": lambda self, _: type("Structured", (), {"ainvoke": structured})()})()
    with patch("src.services.conversation_title.ChatOpenAI", return_value=client) as factory:
        title = await suggest_conversation_title("Tuần này tôi còn deadline nào cần theo dõi?")

    assert title == "Theo dõi deadline tuần này"
    assert factory.call_args.kwargs["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_suggest_conversation_title_falls_back_when_provider_fails(monkeypatch):
    monkeypatch.setattr("src.services.conversation_title.get_settings", lambda: type("S", (), {"openai_api_key": "test"})())
    client = type("Client", (), {"with_structured_output": lambda self, _: type("Structured", (), {"ainvoke": AsyncMock(side_effect=RuntimeError("down"))})()})()
    with patch("src.services.conversation_title.ChatOpenAI", return_value=client):
        title = await suggest_conversation_title("  Hãy giúp tôi lập kế hoạch ôn thi  ")

    assert title == "Hãy giúp tôi lập kế hoạch ôn thi"


def test_fallback_conversation_title_is_bounded():
    assert len(fallback_conversation_title("x" * 100)) == 60
