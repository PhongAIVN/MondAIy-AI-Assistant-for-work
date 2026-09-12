import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.config import get_settings
from src.db import SessionLocal
from src.models.channel_delivery import (
    ChannelNotificationDelivery,
    ChannelUpdateReceipt,
)
from src.models.connection import Connection
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.user import User
from src.services import telegram_channel
from src.services.connections import telegram as telegram_connection


@pytest.fixture(autouse=True)
def _isolate_telegram_webhook_state():
    """Fixed provider IDs remain deterministic without leaking across test runs."""
    db = SessionLocal()
    try:
        db.query(ChannelUpdateReceipt).filter_by(channel="telegram").delete()
        db.query(ChannelUpdateReceipt).filter_by(channel="telegram-callback").delete()
        db.query(Connection).filter_by(provider="telegram").delete()
        db.commit()
    finally:
        db.close()


def _telegram_user(telegram_id: str) -> str:
    db = SessionLocal()
    try:
        user = User(
            email=f"tg-api-{uuid.uuid4().hex[:10]}@example.com", password_hash="test"
        )
        db.add(user)
        db.flush()
        db.add(
            Connection(
                user_id=str(user.id),
                provider="telegram",
                provider_user_id=telegram_id,
                account_label=f"tg-{telegram_id}",
            )
        )
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _task(
    user_id: str,
    title: str,
    *,
    status: str = "proposed",
    reasons: list[str] | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            Task(
                user_id=user_id,
                cluster_key=f"tg-api-{uuid.uuid4().hex}",
                title=title,
                detail="",
                status=status,
                due_at=(
                    datetime.now(UTC) + timedelta(hours=1)
                    if status == "confirmed"
                    else None
                ),
                reasons=reasons,
            )
        )
        db.commit()
    finally:
        db.close()


def _update(update_id: int, telegram_id: str, text: str = "/today") -> dict:
    return {
        "update_id": update_id,
        "message": {
            "from": {"id": int(telegram_id)},
            "chat": {"id": int(telegram_id), "type": "private"},
            "text": text,
        },
    }


@pytest.mark.asyncio
async def test_bot_start_deep_link_connects_without_login_widget_domain(
    client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected-secret")
    monkeypatch.setattr(settings, "telegram_bot_username", "mondaiy_bot")
    db = SessionLocal()
    try:
        user = User(
            email=f"tg-link-{uuid.uuid4().hex[:10]}@example.com", password_hash="test"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
        url = telegram_connection.create_bot_link(db, user_id)
    finally:
        db.close()
    token = url.split("?start=link_", 1)[1]
    sent: list[str] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "linked"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    update = _update(800001, "49999", f"/start link_{token}")
    update["message"]["from"]["username"] = "an_test"

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    assert "đã được liên kết" in sent[0]
    db = SessionLocal()
    try:
        connection = db.execute(
            select(Connection).where(
                Connection.user_id == user_id, Connection.provider == "telegram"
            )
        ).scalar_one()
        assert connection.provider_user_id == "49999"
        assert connection.account_label == "an_test"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_bot_start_deep_link_cannot_be_replayed(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected-secret")
    monkeypatch.setattr(settings, "telegram_bot_username", "mondaiy_bot")
    db = SessionLocal()
    try:
        user = User(
            email=f"tg-replay-{uuid.uuid4().hex[:10]}@example.com", password_hash="test"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        url = telegram_connection.create_bot_link(db, str(user.id))
    finally:
        db.close()
    token = url.split("?start=link_", 1)[1]
    sent: list[str] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "sent"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    update = _update(800002, "50000", f"/start link_{token}")

    first = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )
    update["update_id"] = 800003
    second = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert "đã được liên kết" in sent[0]
    # Replaying the same token must not move the link to another Telegram user.
    replay = _update(800004, "50001", f"/start link_{token}")
    third = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=replay,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )
    assert third.status_code == 200
    assert "chưa liên kết" in sent[2]


@pytest.mark.asyncio
async def test_webhook_rejects_missing_or_wrong_secret(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")

    missing = await client.post(
        "/api/v1/channels/telegram/webhook", json=_update(810001, "40001")
    )
    wrong = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=_update(810002, "40001"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_unlinked_user_gets_link_instruction_without_internal_data(
    client, monkeypatch
):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    sent: list[str] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append((text, kwargs))
        return "1"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=_update(820001, "40002"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    assert "chưa liên kết" in sent[0][0]
    assert "Tóm tắt" not in sent[0][0]
    button = sent[0][1]["reply_markup"]["inline_keyboard"][0][0]
    assert button["url"].endswith("/sources?connect=telegram")


@pytest.mark.asyncio
async def test_today_is_scoped_to_linked_user_and_duplicate_update_is_ignored(
    client, monkeypatch
):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    user_a = _telegram_user("40003")
    user_b = _telegram_user("40004")
    # Việc agent tự gom giờ mang reason auto_confirmed và hiện trong mục
    # "Đã tự xác nhận" của /today — scoping vẫn không được rò task của B.
    _task(user_a, "Việc riêng của A", status="confirmed", reasons=["auto_confirmed"])
    _task(user_b, "Bí mật của B", status="confirmed", reasons=["auto_confirmed"])
    sent: list[str] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "2"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    headers = {"X-Telegram-Bot-Api-Secret-Token": "expected-secret"}
    update = _update(830001, "40003")

    first = await client.post(
        "/api/v1/channels/telegram/webhook", json=update, headers=headers
    )
    second = await client.post(
        "/api/v1/channels/telegram/webhook", json=update, headers=headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(sent) == 1
    assert "Việc riêng của A" in sent[0]
    assert "Bí mật của B" not in sent[0]


@pytest.mark.asyncio
async def test_group_message_never_returns_internal_summary(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    _telegram_user("40005")
    calls = 0

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        nonlocal calls
        calls += 1
        return "3"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    update = _update(840001, "40005")
    update["message"]["chat"] = {"id": -100123, "type": "group"}

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    assert calls == 0


@pytest.mark.asyncio
async def test_callback_navigation_renders_tasks_and_acknowledges_button(
    client, monkeypatch
):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    user_id = _telegram_user("40006")
    _task(user_id, "Việc từ nút Todo")
    sent: list[str] = []
    acknowledged: list[tuple[str, str | None]] = []
    cleared: list[tuple[str, str]] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "4"

    async def fake_ack(callback_query_id: str, text: str | None = None) -> None:
        acknowledged.append((callback_query_id, text))

    async def fake_clear(chat_id: str, message_id: str) -> None:
        cleared.append((chat_id, message_id))

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )
    update = {
        "update_id": 850001,
        "callback_query": {
            "id": "callback-1",
            "from": {"id": 40006},
            "data": "nav:tasks",
            "message": {"message_id": 91, "chat": {"id": 40006, "type": "private"}},
        },
    }

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    assert acknowledged == [("callback-1", "Đang tải…")]
    assert cleared == [("40006", "91")]
    assert "Việc từ nút Todo" in sent[0]


@pytest.mark.asyncio
async def test_repeated_callback_is_acknowledged_without_duplicate_work(
    client, monkeypatch
):
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    _telegram_user("40007")
    sent: list[str] = []
    acknowledgements: list[str | None] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "5"

    async def fake_ack(callback_query_id: str, text: str | None = None) -> None:
        acknowledgements.append(text)

    async def fake_clear(chat_id: str, message_id: str) -> None:
        return None

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )
    headers = {"X-Telegram-Bot-Api-Secret-Token": "expected-secret"}

    def callback(update_id: int, callback_id: str) -> dict:
        return {
            "update_id": update_id,
            "callback_query": {
                "id": callback_id,
                "from": {"id": 40007},
                "data": "nav:today",
                "message": {"message_id": 92, "chat": {"id": 40007, "type": "private"}},
            },
        }

    first = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=callback(860001, "cb-1"),
        headers=headers,
    )
    second = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=callback(860002, "cb-2"),
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(sent) == 1
    assert acknowledgements == [
        "Đang tải…",
        "Yêu cầu đã được nhận. Vui lòng đợi kết quả.",
    ]


@pytest.mark.asyncio
async def test_unexpected_callback_failure_releases_claim_for_retry(
    client, monkeypatch
):
    """Lỗi render không thuộc TelegramAPIError vẫn phải cho nút được retry:
    handler nhả claim rồi trả 502 thay vì giữ receipt vĩnh viễn."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    _telegram_user("40008")
    rendered = 0
    sent: list[str] = []

    def today_view(db, user_id: str, *, now=None) -> tuple[str, list]:
        nonlocal rendered
        rendered += 1
        if rendered == 1:
            raise RuntimeError("unexpected renderer failure")
        return "Kết quả sau khi retry", []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "6"

    async def fake_ack(callback_query_id: str, text: str | None = None) -> None:
        return None

    async def fake_clear(chat_id: str, message_id: str) -> None:
        return None

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "today_view", today_view)
    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )
    headers = {"X-Telegram-Bot-Api-Secret-Token": "expected-secret"}

    def callback(update_id: int) -> dict:
        return {
            "update_id": update_id,
            "callback_query": {
                "id": f"callback-{update_id}",
                "from": {"id": 40008},
                "data": "nav:today",
                "message": {"message_id": 93, "chat": {"id": 40008, "type": "private"}},
            },
        }

    first = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=callback(870001),
        headers=headers,
    )
    # Lượt fail phải trả 502 (claim đã nhả trước đó) thay vì nuốt im lặng.
    assert first.status_code == 502, first.text

    db = SessionLocal()
    try:
        failed_update_claim = db.execute(
            select(ChannelUpdateReceipt).where(
                ChannelUpdateReceipt.channel == "telegram",
                ChannelUpdateReceipt.external_update_id == "870001",
            )
        ).scalar_one_or_none()
        failed_callback_claim = db.execute(
            select(ChannelUpdateReceipt).where(
                ChannelUpdateReceipt.channel == "telegram-callback",
                ChannelUpdateReceipt.external_update_id == "40008:93:today",
            )
        ).scalar_one_or_none()
        assert failed_update_claim is None
        assert failed_callback_claim is None
    finally:
        db.close()

    retried = await client.post(
        "/api/v1/channels/telegram/webhook",
        json=callback(870002),
        headers=headers,
    )

    assert retried.status_code == 200, retried.text
    assert rendered == 2
    assert sent == ["Kết quả sau khi retry"]


@pytest.mark.asyncio
async def test_snooze_button_on_a_reminder_message_reschedules_it(client, monkeypatch):
    """Nút trên tin nhắn nhắc việc phải đi hết đường: callback rm:snooze ->
    tra ngược message_id -> dời lịch lời nhắc -> trả lời cho người dùng."""
    monkeypatch.setattr(get_settings(), "telegram_webhook_secret", "expected-secret")
    user_id = _telegram_user("40021")
    sent: list[str] = []

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        sent.append(text)
        return "9"

    async def fake_ack(callback_query_id: str, text: str | None = None) -> None:
        return None

    async def fake_clear(chat_id: str, message_id: str) -> None:
        return None

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )

    db = SessionLocal()
    try:
        reminder = Reminder(
            task_id=None,
            user_id=user_id,
            kind="daily_brief",
            milestone="digest",
            scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
            payload={"dueSoonCount": 0},
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id
        db.add(
            ChannelNotificationDelivery(
                channel="telegram",
                reminder_id=reminder_id,
                user_id=user_id,
                provider_message_id="777",
            )
        )
        db.commit()
    finally:
        db.close()

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json={
            "update_id": 860001,
            "callback_query": {
                "id": "callback-snooze",
                "from": {"id": 40021},
                "data": "rm:snooze",
                "message": {
                    "message_id": 777,
                    "chat": {"id": 40021, "type": "private"},
                },
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    assert "nhắc lại" in sent[0].lower()
    db = SessionLocal()
    try:
        row = db.get(Reminder, reminder_id)
        assert row.snooze_count == 1
        assert row.status == "scheduled"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_snooze_via_edit_message_text_success(client, monkeypatch):
    """Snooze action successfully edits the original message instead of sending a new one."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected-secret")
    monkeypatch.setattr(settings, "telegram_bot_token", "123:token")

    user_id = _telegram_user("40022")
    _task(user_id, "Task to snooze", status="confirmed")

    db = SessionLocal()
    try:
        reminder = Reminder(
            user_id=user_id,
            task_id=db.execute(select(Task).where(Task.user_id == user_id))
            .scalars()
            .first()
            .id,
            kind="task_due",
            milestone="30_min",
            scheduled_at=datetime.now(UTC),
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id

        db.add(
            ChannelNotificationDelivery(
                channel="telegram",
                reminder_id=reminder_id,
                user_id=user_id,
                provider_message_id="788",
            )
        )
        db.commit()
    finally:
        db.close()

    edit_calls = []
    send_calls = []

    async def fake_edit(chat_id: int, message_id: int, text: str, reply_markup=None):
        edit_calls.append((chat_id, message_id, text))

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        send_calls.append(text)
        return "new_msg"

    async def fake_clear(chat_id: str, message_id: str):
        pass

    async def fake_ack(callback_id: str, text: str):
        pass

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "edit_message_text", fake_edit)
    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json={
            "update_id": 860002,
            "callback_query": {
                "id": "callback-snooze-2",
                "from": {"id": 40022},
                "data": "rm:snooze",
                "message": {
                    "message_id": 788,
                    "chat": {"id": 40022, "type": "private"},
                },
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    # Should edit original message, not send a new one
    assert len(edit_calls) == 1
    assert edit_calls[0][0] == 40022  # chat_id
    assert edit_calls[0][1] == 788  # message_id
    assert "nhắc lại" in edit_calls[0][2].lower()
    assert len(send_calls) == 0  # No fallback send


@pytest.mark.asyncio
async def test_snooze_via_edit_message_text_fallback_on_failure(client, monkeypatch):
    """When edit_message_text fails, fallback to sending a new message."""
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected-secret")
    monkeypatch.setattr(settings, "telegram_bot_token", "123:token")

    user_id = _telegram_user("40023")
    _task(user_id, "Task to snooze", status="confirmed")

    db = SessionLocal()
    try:
        reminder = Reminder(
            user_id=user_id,
            task_id=db.execute(select(Task).where(Task.user_id == user_id))
            .scalars()
            .first()
            .id,
            kind="task_due",
            milestone="30_min",
            scheduled_at=datetime.now(UTC),
        )
        db.add(reminder)
        db.flush()
        reminder_id = reminder.id

        db.add(
            ChannelNotificationDelivery(
                channel="telegram",
                reminder_id=reminder_id,
                user_id=user_id,
                provider_message_id="789",
            )
        )
        db.commit()
    finally:
        db.close()

    send_calls = []

    async def fake_edit_fail(
        chat_id: int, message_id: int, text: str, reply_markup=None
    ):
        raise telegram_channel.TelegramAPIError("Message is too old to edit")

    async def fake_send(chat_id: str, text: str, **kwargs) -> str:
        send_calls.append(text)
        return "fallback_msg"

    async def fake_clear(chat_id: str, message_id: str):
        pass

    async def fake_ack(callback_id: str, text: str):
        pass

    class FakeTyping:
        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(telegram_channel, "edit_message_text", fake_edit_fail)
    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    monkeypatch.setattr(telegram_channel, "answer_callback_query", fake_ack)
    monkeypatch.setattr(telegram_channel, "clear_inline_keyboard", fake_clear)
    monkeypatch.setattr(
        telegram_channel, "typing_indicator", lambda chat_id: FakeTyping()
    )

    response = await client.post(
        "/api/v1/channels/telegram/webhook",
        json={
            "update_id": 860003,
            "callback_query": {
                "id": "callback-snooze-3",
                "from": {"id": 40023},
                "data": "rm:snooze",
                "message": {
                    "message_id": 789,
                    "chat": {"id": 40023, "type": "private"},
                },
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "expected-secret"},
    )

    assert response.status_code == 200
    # Should fallback to send_message when edit fails
    assert len(send_calls) == 1
    assert "nhắc lại" in send_calls[0].lower()
