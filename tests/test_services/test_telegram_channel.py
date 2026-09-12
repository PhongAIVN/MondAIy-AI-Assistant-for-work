import hashlib
import hmac
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from src.config import get_settings
from src.models.channel_delivery import (
    ChannelNotificationDelivery,
    ChannelUpdateReceipt,
)
from src.models.connection import Connection
from src.models.notification_preference import NotificationPreference
from src.models.reminder import NotificationDelivery, Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.user import User
from src.services import reminders, telegram_channel
from src.services.connections import telegram


@pytest.fixture(autouse=True)
def _isolate_telegram_channel_state():
    """Provider identities and receipts must not leak between repeated suites."""
    from src.db import SessionLocal

    session = SessionLocal()
    try:
        session.query(ChannelNotificationDelivery).filter_by(
            channel="telegram"
        ).delete()
        session.query(ChannelUpdateReceipt).filter_by(channel="telegram").delete()
        session.query(ChannelUpdateReceipt).filter_by(
            channel="telegram-callback"
        ).delete()
        session.query(Connection).filter_by(provider="telegram").delete()
        session.commit()
    finally:
        session.close()


@pytest.fixture
def db():
    from src.db import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _user(db, suffix: str) -> User:
    row = User(
        email=f"telegram-{suffix}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _link(db, user: User, telegram_id: str) -> None:
    db.add(
        Connection(
            user_id=str(user.id),
            provider="telegram",
            provider_user_id=telegram_id,
            account_label=f"tg-{telegram_id}",
        )
    )
    db.commit()


def _due_reminder(db, user: User, *, now: datetime) -> Reminder:
    task = Task(
        user_id=str(user.id),
        cluster_key=f"tg-{uuid.uuid4().hex}",
        title="Nộp báo cáo",
        detail="",
        status="confirmed",
        due_at=now + timedelta(minutes=20),
        signal_strength=1.0,
    )
    db.add(task)
    db.flush()
    db.add(
        TaskEvidence(
            task_id=task.id,
            provider="gmail",
            evidence_quote="q",
            deep_link="https://example.test/e",
        )
    )
    reminder = Reminder(
        task_id=task.id,
        user_id=str(user.id),
        kind="task_due",
        milestone="30_min",
        scheduled_at=now - timedelta(minutes=1),
    )
    db.add(reminder)
    db.add(
        NotificationPreference(
            user_id=str(user.id), quiet_hours_start=0, quiet_hours_end=0
        )
    )
    db.commit()
    db.refresh(reminder)
    return reminder


def test_login_widget_verification_returns_numeric_identity(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    payload = {
        "id": "991122",
        "first_name": "An",
        "username": "an_test",
        "auth_date": str(int(time.time())),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    payload["hash"] = hmac.new(
        secret_key, check_string.encode(), hashlib.sha256
    ).hexdigest()

    identity = telegram.verify_identity(payload)

    assert identity is not None
    assert identity.user_id == "991122"
    assert identity.account_label == "an_test"


def test_bot_link_consumes_sqlite_naive_expiry(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_username", "mondaiy_bot")
    user = _user(db, "link-naive-expiry")
    link = telegram.create_bot_link(db, str(user.id))
    token = parse_qs(urlsplit(link).query)["start"][0].removeprefix("link_")

    linked_user_id = telegram.consume_bot_link(
        db,
        token,
        telegram_user_id="991123",
        account_label="an_test_2",
    )

    assert linked_user_id == str(user.id)


def test_login_widget_uses_botfather_web_domain_for_origin_and_callback(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    monkeypatch.setattr(settings, "app_public_url", "https://api.example.test")
    monkeypatch.setattr(settings, "web_app_public_url", "https://app.example.test/")

    query = parse_qs(urlsplit(telegram.build_authorize_url("signed-state")).query)

    assert query["origin"] == ["https://app.example.test"]
    assert query["return_to"] == [
        "https://app.example.test/api/v1/connections/telegram/callback?state=signed-state"
    ]


def test_login_widget_rejects_non_https_web_origin(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    monkeypatch.setattr(settings, "web_app_public_url", "http://localhost:5173")

    with pytest.raises(ValueError, match="HTTPS origin"):
        telegram.build_authorize_url("signed-state")


def test_find_linked_user_rejects_unknown_and_inactive_users(db):
    active = _user(db, "active")
    inactive = _user(db, "inactive")
    inactive.is_active = False
    db.commit()
    _link(db, active, "10001")
    _link(db, inactive, "10002")

    assert telegram_channel.find_linked_user(db, "99999") is None
    assert telegram_channel.find_linked_user(db, "10002") is None
    assert telegram_channel.find_linked_user(db, "10001").user_id == str(active.id)


def test_database_rejects_linking_same_telegram_identity_to_two_users(db):
    from sqlalchemy.exc import IntegrityError

    first = _user(db, "first-owner")
    second = _user(db, "second-owner")
    _link(db, first, "10003")

    db.add(
        Connection(
            user_id=str(second.id),
            provider="telegram",
            provider_user_id="10003",
            account_label="duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.asyncio
async def test_delivery_receipt_is_channel_scoped_and_prevents_telegram_duplicate(
    db, monkeypatch
):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "delivery")
    _link(db, user, "20001")
    reminder = _due_reminder(db, user, now=now)
    sent: list[tuple[str, str]] = []

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        sent.append((chat_id, text))
        return "501"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)

    assert await telegram_channel.deliver_due_notifications(db, now=now) == 1
    assert await telegram_channel.deliver_due_notifications(db, now=now) == 0
    assert len(sent) == 1
    assert sent[0][0] == "20001"
    assert "Nộp báo cáo" in sent[0][1]
    assert (
        db.query(ChannelNotificationDelivery)
        .filter_by(reminder_id=reminder.id, channel="telegram")
        .count()
        == 1
    )

    # Receipt Telegram không làm extension mất notification của nó.
    extension_bundles = reminders.get_due_notifications(
        db, str(user.id), now=now, delivery_channel="extension"
    )
    assert extension_bundles[0].reminder_ids == [reminder.id]
    reminders.record_deliveries(db, str(user.id), [reminder.id])
    assert (
        db.query(NotificationDelivery).filter_by(reminder_id=reminder.id).count() == 1
    )


@pytest.mark.asyncio
async def test_failed_send_does_not_record_delivery(db, monkeypatch):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "failure")
    _link(db, user, "20002")
    reminder = _due_reminder(db, user, now=now)

    async def fail_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        raise telegram_channel.TelegramAPIError("provider down")

    monkeypatch.setattr(telegram_channel, "send_message", fail_send)

    assert await telegram_channel.deliver_due_notifications(db, now=now) == 0
    assert (
        db.query(ChannelNotificationDelivery).filter_by(reminder_id=reminder.id).count()
        == 0
    )


@pytest.mark.asyncio
async def test_send_message_uses_bot_api_without_parse_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        telegram_channel.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    message_id = await telegram_channel.send_message("30001", "<b>raw</b>")

    assert message_id == "77"
    body = __import__("json").loads(seen[0].content)
    assert body["chat_id"] == "30001"
    assert "parse_mode" not in body


@pytest.mark.asyncio
async def test_typing_indicator_sends_immediate_chat_action(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_action(chat_id: str, action: str = "typing") -> None:
        calls.append((chat_id, action))

    monkeypatch.setattr(telegram_channel, "send_chat_action", fake_action)

    async with telegram_channel.typing_indicator("30002"):
        assert calls == [("30002", "typing")]


def test_callback_claim_deduplicates_same_button_but_allows_new_message(db):
    assert telegram_channel.claim_callback_action(db, "30003", "10", "tasks") is True
    assert telegram_channel.claim_callback_action(db, "30003", "10", "tasks") is False
    assert telegram_channel.claim_callback_action(db, "30003", "11", "tasks") is True


@pytest.mark.asyncio
async def test_configure_webhook_sends_https_url_secret_and_registers_navigation_commands(
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "webhook-secret")
    monkeypatch.setattr(settings, "app_public_url", "https://api.example.test/")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True, "result": True})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        telegram_channel.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    await telegram_channel.configure_webhook()

    body = __import__("json").loads(seen[0].content)
    assert body == {
        "url": "https://api.example.test/api/v1/channels/telegram/webhook",
        "secret_token": "webhook-secret",
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": False,
    }
    commands = __import__("json").loads(seen[1].content)["commands"]
    assert [item["command"] for item in commands] == [
        "today",
        "tasks",
        "inbox",
        "settings",
    ]


def test_connect_keyboard_opens_web_app_sources_instead_of_api_domain():
    keyboard = telegram_channel.connect_keyboard("https://app.example.test/")

    assert keyboard["inline_keyboard"][0][0] == {
        "text": "Kết nối Mondaiy",
        "url": "https://app.example.test/sources?connect=telegram",
    }


def test_web_app_url_falls_back_to_first_cors_origin(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_app_public_url", "")
    monkeypatch.setattr(
        settings,
        "cors_origins",
        "https://app.example.test,https://preview.example.test",
    )
    monkeypatch.setattr(settings, "app_public_url", "https://api.example.test")

    assert telegram_channel.get_web_app_public_url() == "https://app.example.test"


def test_render_tasks_and_inbox_are_scoped_to_user(db):
    owner = _user(db, "command-owner")
    other = _user(db, "command-other")
    db.add_all(
        [
            Task(
                user_id=str(owner.id),
                cluster_key=f"tg-{uuid.uuid4().hex}",
                title="Việc của tôi",
                detail="",
                status="proposed",
            ),
            Task(
                user_id=str(other.id),
                cluster_key=f"tg-{uuid.uuid4().hex}",
                title="Việc bí mật",
                detail="",
                status="proposed",
            ),
        ]
    )
    db.commit()

    tasks = telegram_channel.render_tasks(db, str(owner.id))
    inbox = telegram_channel.render_inbox(db, str(owner.id))

    assert "Việc của tôi" in tasks
    assert "Việc bí mật" not in tasks
    assert "1 việc đang chờ xác nhận" in inbox


@pytest.mark.asyncio
async def test_configure_webhook_rejects_non_https_public_url(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123:test-token")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "webhook-secret")
    monkeypatch.setattr(settings, "app_public_url", "http://localhost:8000")

    with pytest.raises(telegram_channel.TelegramAPIError, match="HTTPS"):
        await telegram_channel.configure_webhook()


@pytest.mark.asyncio
async def test_reminder_message_carries_snooze_and_dismiss_buttons(db, monkeypatch):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "buttons")
    _link(db, user, "20010")
    _due_reminder(db, user, now=now)
    keyboards: list[dict | None] = []

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        keyboards.append(reply_markup)
        return "601"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)

    await telegram_channel.deliver_due_notifications(db, now=now)

    rows = keyboards[0]["inline_keyboard"]
    assert [button["callback_data"] for button in rows[0]] == [
        "rm:snooze",
        "rm:dismiss",
    ]


@pytest.mark.asyncio
async def test_snooze_button_reschedules_and_lets_telegram_deliver_again(
    db, monkeypatch
):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "snooze-button")
    _link(db, user, "20011")
    reminder = _due_reminder(db, user, now=now)

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        return "602"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    await telegram_channel.deliver_due_notifications(db, now=now)

    answer = telegram_channel.apply_reminder_action(db, str(user.id), "602", "snooze")

    assert "nhắc lại" in answer.lower()
    db.refresh(reminder)
    assert reminder.snooze_count == 1
    assert reminder.status == "scheduled"
    # Nhắc lại là hẹn giao lại, nên receipt của kênh phải được dọn — không dọn
    # thì Telegram coi lời nhắc này đã giao xong và mốc mới không bao giờ tới.
    assert (
        db.query(ChannelNotificationDelivery).filter_by(reminder_id=reminder.id).count()
        == 0
    )
    # Mốc mới tính từ thời điểm bấm nút thật, không từ `now` giả của lần giao.
    later = reminders.get_due_notifications(
        db,
        str(user.id),
        now=datetime.now(UTC)
        + timedelta(minutes=telegram_channel.REMINDER_SNOOZE_MINUTES + 1),
        delivery_channel="telegram",
    )
    assert later[0].reminder_ids == [reminder.id]


@pytest.mark.asyncio
async def test_dismiss_button_cancels_reminder_without_touching_the_task(
    db, monkeypatch
):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "dismiss-button")
    _link(db, user, "20012")
    reminder = _due_reminder(db, user, now=now)
    task_id = reminder.task_id

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        return "603"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    await telegram_channel.deliver_due_notifications(db, now=now)

    telegram_channel.apply_reminder_action(db, str(user.id), "603", "dismiss")

    db.refresh(reminder)
    assert reminder.status == "cancelled"
    assert db.get(Task, task_id).status == "confirmed"

    # Bấm lại trên tin nhắn cũ không được ném lỗi, chỉ nói thật là đã xử lý rồi.
    again = telegram_channel.apply_reminder_action(db, str(user.id), "603", "dismiss")
    assert "đã được xử lý" in again


@pytest.mark.asyncio
async def test_reminder_action_ignores_a_message_belonging_to_another_user(
    db, monkeypatch
):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    owner = _user(db, "action-owner")
    stranger = _user(db, "action-stranger")
    _link(db, owner, "20013")
    reminder = _due_reminder(db, owner, now=now)

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        return "604"

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)
    await telegram_channel.deliver_due_notifications(db, now=now)

    # Cùng message_id nhưng khác chủ sở hữu: Telegram đánh số tin nhắn theo từng
    # chat nên trùng số là chuyện thường, không được biến thành quyền thao tác.
    answer = telegram_channel.apply_reminder_action(
        db, str(stranger.id), "604", "snooze"
    )

    assert "đã được xử lý" in answer
    db.refresh(reminder)
    assert reminder.snooze_count == 0


def test_reminder_action_rejects_an_unknown_verb(db):
    user = _user(db, "action-unknown")

    assert (
        telegram_channel.apply_reminder_action(db, str(user.id), "605", "xoa_het")
        == "Thao tác không hợp lệ."
    )


@pytest.mark.asyncio
async def test_disabling_the_telegram_channel_stops_delivery(db, monkeypatch):
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "channel-off")
    _link(db, user, "20014")
    _due_reminder(db, user, now=now)
    pref = reminders.get_or_create_preference(db, str(user.id))
    pref.telegram_enabled = False
    db.commit()

    async def fake_send(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        raise AssertionError("Kênh đã tắt thì không được gửi gì")

    monkeypatch.setattr(telegram_channel, "send_message", fake_send)

    assert await telegram_channel.deliver_due_notifications(db, now=now) == 0
    # Tắt Telegram không được làm extension mất lời nhắc của nó.
    assert reminders.get_due_notifications(
        db, str(user.id), now=now, delivery_channel="extension"
    )


@pytest.mark.asyncio
async def test_telegram_delivery_logs_structured_error_on_send_failure(
    db, monkeypatch, caplog
):
    """When send_message fails, log ERROR with user_id and channel info."""
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "send-failure-log")
    _link(db, user, "20015")
    _due_reminder(db, user, now=now)

    async def fake_send_fail(
        chat_id: str, text: str, *, reply_markup: dict | None = None
    ) -> str:
        raise telegram_channel.TelegramAPIError("Bot blocked by user")

    monkeypatch.setattr(telegram_channel, "send_message", fake_send_fail)

    result = await telegram_channel.deliver_due_notifications(db, now=now)

    # No messages delivered due to send failure
    assert result == 0
    # Log with ERROR level should be present containing structured fields
    error_records = [
        r
        for r in caplog.records
        if r.levelname == "ERROR" and "Telegram send failed" in r.message
    ]
    assert len(error_records) > 0
    # Check that extra fields are present in the log record
    error_log = error_records[0]
    assert getattr(error_log, "user_id", None) == str(user.id)
    assert getattr(error_log, "channel", None) == "telegram"
    assert "Bot blocked by user" in getattr(error_log, "error", "")


def test_apply_reminder_action_already_handled_elsewhere(db):
    """apply_reminder_action returns friendly message when reminder already processed."""
    now = datetime(2026, 8, 13, 12, tzinfo=UTC)
    user = _user(db, "already-handled")
    _link(db, user, "20020")
    _due_reminder(db, user, now=now)

    # Snooze/dismiss action on a non-existent message_id (no delivery recorded)
    response = telegram_channel.apply_reminder_action(db, str(user.id), "999", "snooze")

    # Should return friendly message indicating reminder already processed
    assert "đã được xử lý" in response


def test_render_today_with_six_due_tasks_shows_truncation_message(db):
    """Khi có 6 tasks sắp hạn, chỉ hiển thị 5 task + dòng '… và 1 việc khác'."""
    now = datetime(2026, 8, 14, 10, tzinfo=UTC)
    user = _user(db, "truncation-6")

    # Tạo 6 tasks sắp hạn trong 24 giờ
    for i in range(6):
        task = Task(
            user_id=str(user.id),
            cluster_key=f"task-{i}",
            title=f"Task {i+1}",
            detail="",
            status="confirmed",
            due_at=now + timedelta(hours=i + 1),
            signal_strength=1.0,
        )
        db.add(task)
    db.commit()

    text = telegram_channel.render_today(db, str(user.id), now=now)

    # Phải hiển thị số đếm toàn bộ (6) nhưng chỉ list 5 task
    assert "Sắp hạn trong 24 giờ: 6" in text
    assert "Task 1" in text
    assert "Task 5" in text
    assert "Task 6" not in text
    # Phải có dòng "… và 1 việc khác"
    assert "… và 1 việc khác" in text


def test_render_today_with_five_due_tasks_no_truncation_message(db):
    """Khi có 5 tasks sắp hạn, hiển thị tất cả không cần dòng '… và N'."""
    now = datetime(2026, 8, 14, 10, tzinfo=UTC)
    user = _user(db, "truncation-5")

    # Tạo 5 tasks sắp hạn trong 24 giờ
    for i in range(5):
        task = Task(
            user_id=str(user.id),
            cluster_key=f"task-no-trunc-{i}",
            title=f"Task {i+1}",
            detail="",
            status="confirmed",
            due_at=now + timedelta(hours=i + 1),
            signal_strength=1.0,
        )
        db.add(task)
    db.commit()

    text = telegram_channel.render_today(db, str(user.id), now=now)

    # Hiển thị 5 task
    assert "Sắp hạn trong 24 giờ: 5" in text
    assert "Task 1" in text
    assert "Task 5" in text
    # Không có dòng truncation
    assert "… và" not in text
