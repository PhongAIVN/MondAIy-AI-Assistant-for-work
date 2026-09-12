"""Kênh giao Web Push — xem src/services/web_push.py.

Ràng buộc được khoá ở đây, theo thứ tự quan trọng: subscription của một người
không bao giờ nhận thông báo của người khác; receipt chỉ ghi sau khi gửi thành
công; endpoint chết bị xoá thay vì retry vô hạn; và log không chứa nội dung
thông báo hay endpoint đầy đủ.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.channel_delivery import ChannelNotificationDelivery
from src.models.notification_preference import NotificationPreference
from src.models.push_subscription import PushSubscription
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.user import User
from src.services import web_push

# Id user do file này tạo — teardown chỉ xoá đúng phần mình sinh ra, vì DB test
# dùng chung và không reset giữa các file.
_created_user_ids: set[int] = set()


@pytest.fixture(autouse=True)
def _enable_web_push(monkeypatch):
    """Bật cờ, cắm khoá VAPID giả và giả vờ đã cài pywebpush.

    Cả ba đều mặc định TẮT/thiếu ở môi trường thật, nên test phải bật tường
    minh. Khoá ở đây là chuỗi giả: mọi lời gọi mạng đều bị thay bằng monkeypatch
    trong từng test, không có gói tin nào rời khỏi máy.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "web_push_enabled", True)
    monkeypatch.setattr(settings, "vapid_public_key", "test-public-key")
    monkeypatch.setattr(settings, "vapid_private_key", "test-private-key")
    monkeypatch.setattr(web_push, "_webpush_available", lambda: True)
    _created_user_ids.clear()
    yield
    with SessionLocal() as db:
        if _created_user_ids:
            user_ids = {str(uid) for uid in _created_user_ids}
            db.query(PushSubscription).filter(PushSubscription.user_id.in_(user_ids)).delete(
                synchronize_session=False
            )
            db.query(ChannelNotificationDelivery).filter(
                ChannelNotificationDelivery.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(Reminder).filter(Reminder.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(TaskEvidence).filter(
                TaskEvidence.task_id.in_(
                    db.query(Task.id).filter(Task.user_id.in_(user_ids)).scalar_subquery()
                )
            ).delete(synchronize_session=False)
            db.query(Task).filter(Task.user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(NotificationPreference).filter(
                NotificationPreference.user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(_created_user_ids)).delete(synchronize_session=False)
            db.commit()
    _created_user_ids.clear()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _user(db) -> User:
    row = User(email=f"webpush-{uuid.uuid4().hex[:10]}@example.com", password_hash="test")
    db.add(row)
    db.commit()
    db.refresh(row)
    _created_user_ids.add(row.id)
    return row


def _subscribe(db, user: User) -> PushSubscription:
    row = PushSubscription(
        user_id=str(user.id),
        endpoint=f"https://push.example.test/{uuid.uuid4().hex}",
        p256dh="p256dh-test",
        auth="auth-test",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _due_reminder(db, user: User, *, now: datetime, title: str = "Nộp báo cáo") -> Reminder:
    task = Task(
        user_id=str(user.id),
        cluster_key=f"wp-{uuid.uuid4().hex}",
        title=title,
        detail="",
        status="confirmed",
        due_at=now + timedelta(minutes=20),
        signal_strength=1.0,
    )
    db.add(task)
    db.flush()
    db.add(
        TaskEvidence(task_id=task.id, provider="gmail", evidence_quote="q", deep_link="https://example.test/e")
    )
    reminder = Reminder(
        task_id=task.id,
        user_id=str(user.id),
        kind="task_due",
        milestone="30_min",
        scheduled_at=now - timedelta(minutes=1),
    )
    db.add(reminder)
    db.add(NotificationPreference(user_id=str(user.id), quiet_hours_start=0, quiet_hours_end=0))
    db.commit()
    db.refresh(reminder)
    return reminder


def _receipts(db, user: User) -> list[ChannelNotificationDelivery]:
    return (
        db.query(ChannelNotificationDelivery)
        .filter_by(user_id=str(user.id), channel=web_push.WEB_PUSH_CHANNEL)
        .all()
    )


def test_flag_tat_thi_khong_gui_gi(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_push_enabled", False)
    user = _user(db)
    _subscribe(db, user)
    _due_reminder(db, user, now=datetime.now(UTC))
    sent: list[str] = []
    monkeypatch.setattr(web_push, "_send_to_subscription", lambda sub, payload: sent.append(payload))

    assert web_push.deliver_due_web_push(db, now=datetime.now(UTC)) == 0
    assert sent == []
    assert _receipts(db, user) == []


def test_thieu_khoa_vapid_thi_khong_gui_gi(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "vapid_private_key", "")
    user = _user(db)
    _subscribe(db, user)
    _due_reminder(db, user, now=datetime.now(UTC))
    sent: list[str] = []
    monkeypatch.setattr(web_push, "_send_to_subscription", lambda sub, payload: sent.append(payload))

    assert web_push.deliver_due_web_push(db) == 0
    assert sent == []


def test_chua_cai_pywebpush_thi_tra_0(db, monkeypatch):
    monkeypatch.setattr(web_push, "_webpush_available", lambda: False)
    user = _user(db)
    _subscribe(db, user)
    _due_reminder(db, user, now=datetime.now(UTC))

    assert web_push.deliver_due_web_push(db) == 0


def test_gui_thanh_cong_thi_ghi_receipt_va_khong_giao_trung(db, monkeypatch):
    now = datetime.now(UTC)
    user = _user(db)
    subscription = _subscribe(db, user)
    reminder = _due_reminder(db, user, now=now)
    sent: list[str] = []
    monkeypatch.setattr(web_push, "_send_to_subscription", lambda sub, payload: sent.append(payload))

    assert web_push.deliver_due_web_push(db, now=now) == 1
    assert len(sent) == 1
    receipts = _receipts(db, user)
    assert [row.reminder_id for row in receipts] == [reminder.id]

    # Nhịp thứ hai: cùng reminder không được giao lại lần nữa.
    assert web_push.deliver_due_web_push(db, now=now) == 0
    assert len(sent) == 1
    assert len(_receipts(db, user)) == 1

    db.refresh(subscription)
    assert subscription.last_used_at is not None
    assert subscription.last_error_class is None


def test_gui_hong_thi_khong_ghi_receipt(db, monkeypatch):
    now = datetime.now(UTC)
    user = _user(db)
    subscription = _subscribe(db, user)
    _due_reminder(db, user, now=now)

    def _fail(sub, payload):
        raise web_push.WebPushError("Push service trả HTTP 500.")

    monkeypatch.setattr(web_push, "_send_to_subscription", _fail)

    assert web_push.deliver_due_web_push(db, now=now) == 0
    assert _receipts(db, user) == []
    db.refresh(subscription)
    assert subscription.last_error_class == "send_failed"

    # Lượt sau gửi được thì thông báo vẫn tới — đó là lý do không ghi receipt sớm.
    monkeypatch.setattr(web_push, "_send_to_subscription", lambda sub, payload: None)
    assert web_push.deliver_due_web_push(db, now=now) == 1


def test_410_thi_xoa_subscription(db, monkeypatch):
    now = datetime.now(UTC)
    user = _user(db)
    subscription = _subscribe(db, user)
    subscription_id = subscription.id
    _due_reminder(db, user, now=now)

    def _gone(sub, payload):
        raise web_push.WebPushGoneError("Endpoint đã bị push service thu hồi (HTTP 410).")

    monkeypatch.setattr(web_push, "_send_to_subscription", _gone)

    assert web_push.deliver_due_web_push(db, now=now) == 0
    assert db.get(PushSubscription, subscription_id) is None
    assert _receipts(db, user) == []


def test_mot_thiet_bi_chet_khong_lam_mat_thong_bao_cua_thiet_bi_con_song(db, monkeypatch):
    now = datetime.now(UTC)
    user = _user(db)
    dead = _subscribe(db, user)
    alive = _subscribe(db, user)
    dead_id, alive_id = dead.id, alive.id
    reminder = _due_reminder(db, user, now=now)

    def _send(sub, payload):
        if sub.id == dead_id:
            raise web_push.WebPushGoneError("HTTP 410")

    monkeypatch.setattr(web_push, "_send_to_subscription", _send)

    assert web_push.deliver_due_web_push(db, now=now) == 1
    assert db.get(PushSubscription, dead_id) is None
    assert db.get(PushSubscription, alive_id) is not None
    assert [row.reminder_id for row in _receipts(db, user)] == [reminder.id]


def test_subscription_khong_nhan_thong_bao_cua_user_khac(db, monkeypatch):
    now = datetime.now(UTC)
    owner = _user(db)
    other = _user(db)
    owner_subscription = _subscribe(db, owner)
    other_subscription = _subscribe(db, other)
    # Chỉ `other` có việc tới hạn; `owner` thì không có gì.
    reminder = _due_reminder(db, other, now=now, title="Việc riêng của người khác")

    received: list[tuple[str, str]] = []
    monkeypatch.setattr(
        web_push, "_send_to_subscription", lambda sub, payload: received.append((sub.endpoint, payload))
    )

    web_push.deliver_due_web_push(db, now=now)

    assert [endpoint for endpoint, _ in received] == [other_subscription.endpoint]
    assert owner_subscription.endpoint not in [endpoint for endpoint, _ in received]
    assert all("Việc riêng của người khác" not in payload for endpoint, payload in received if endpoint == owner_subscription.endpoint)
    assert [row.user_id for row in _receipts(db, other)] == [str(other.id)]
    assert _receipts(db, owner) == []
    assert reminder.user_id == str(other.id)


def test_khong_log_noi_dung_thong_bao_hay_endpoint(db, monkeypatch, caplog):
    now = datetime.now(UTC)
    user = _user(db)
    subscription = _subscribe(db, user)
    _due_reminder(db, user, now=now, title="Bí mật không được vào log")

    def _fail(sub, payload):
        raise web_push.WebPushError("Push service trả HTTP 500.")

    monkeypatch.setattr(web_push, "_send_to_subscription", _fail)

    with caplog.at_level(logging.DEBUG, logger="src.services.web_push"):
        web_push.deliver_due_web_push(db, now=now)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "Bí mật không được vào log" not in logged
    assert subscription.endpoint not in logged
    # Vẫn phải truy vết được thiết bị nào hỏng, chỉ là qua dấu vân tay.
    assert web_push._endpoint_fingerprint(subscription.endpoint) in logged


def test_render_bundle_giu_lien_ket_bang_chung(db):
    now = datetime.now(UTC)
    user = _user(db)
    _due_reminder(db, user, now=now)
    from src.services import reminders as reminders_service

    bundles = reminders_service.get_due_notifications(
        db, str(user.id), now=now, delivery_channel=web_push.WEB_PUSH_CHANNEL
    )
    payload = web_push.render_bundle(bundles[0])

    assert payload.title == "Nhắc việc"
    assert "Nộp báo cáo" in payload.body
    assert payload.url == "https://example.test/e"


def test_disabled_web_push_channel_skips_delivery_without_deleting_reminder(db, monkeypatch):
    """Tắt kênh chỉ chặn đường giao, không huỷ lời nhắc.

    Đây là ranh giới quan trọng nhất của công tắc kênh: người dùng tắt thông báo
    trên máy không có nghĩa là họ muốn quên việc, nên lời nhắc phải còn nguyên
    cho kênh khác và cho lúc bật lại.
    """
    from src.services import reminders as reminders_service

    now = datetime.now(UTC)
    user = _user(db)
    _subscribe(db, user)
    reminder = _due_reminder(db, user, now=now)
    pref = reminders_service.get_or_create_preference(db, str(user.id))
    pref.web_push_enabled = False
    db.commit()

    def fail_if_sent(sub, payload):
        raise AssertionError("Kênh đã tắt thì không được gửi gì")

    monkeypatch.setattr(web_push, "_send_to_subscription", fail_if_sent)

    assert web_push.deliver_due_web_push(db, now=now) == 0
    assert _receipts(db, user) == []
    extension = reminders_service.get_due_notifications(
        db, str(user.id), now=now, delivery_channel="extension"
    )
    assert extension[0].reminder_ids == [reminder.id]
