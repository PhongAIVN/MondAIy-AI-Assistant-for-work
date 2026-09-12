from unittest.mock import AsyncMock, patch

import pytest


class _FakeReply:
    def __init__(self, content: str) -> None:
        self.content = content


@pytest.mark.asyncio
async def test_public_ask_answers_without_authentication(client):
    with patch(
        "src.api.public_ask.get_llm",
        return_value=AsyncMock(ainvoke=AsyncMock(return_value=_FakeReply("mondaiy là trợ lý tổng hợp lịch và việc cần làm."))),
    ):
        response = await client.post(
            "/api/v1/public-ask/messages",
            json={"message": "mondaiy là gì?", "history": []},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "mondaiy là trợ lý tổng hợp lịch và việc cần làm."
    assert body["turnsUsed"] == 1
    assert body["limitReached"] is False


@pytest.mark.asyncio
async def test_public_ask_marks_limit_reached_on_the_final_allowed_turn(client):
    # Giới hạn mới là 4 (ba câu gợi ý + một câu tự nhập) nên lịch sử phải có
    # ba lượt user trước đó; lượt này là lượt cuối cùng được phép.
    history = [
        {"role": "user", "content": "mondaiy là gì?"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "Dùng thế nào?"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "Có hỗ trợ tiếng Việt không?"},
        {"role": "assistant", "content": "..."},
    ]
    with patch(
        "src.api.public_ask.get_llm",
        return_value=AsyncMock(ainvoke=AsyncMock(return_value=_FakeReply("Đăng ký để dùng đầy đủ nhé."))),
    ):
        response = await client.post(
            "/api/v1/public-ask/messages",
            json={"message": "Có mất phí không?", "history": history},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["turnsUsed"] == 4
    assert body["limitReached"] is True


@pytest.mark.asyncio
async def test_public_ask_rejects_a_fifth_turn_without_calling_the_llm(client):
    history = [
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "2"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "4"},
        {"role": "assistant", "content": "..."},
    ]
    fake_llm = AsyncMock(ainvoke=AsyncMock(return_value=_FakeReply("no")))
    with patch("src.api.public_ask.get_llm", return_value=fake_llm):
        response = await client.post(
            "/api/v1/public-ask/messages",
            json={"message": "5", "history": history},
        )

    assert response.status_code == 429
    fake_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_public_ask_rejects_an_overly_long_message(client):
    response = await client.post(
        "/api/v1/public-ask/messages",
        json={"message": "x" * 501, "history": []},
    )

    assert response.status_code == 422
