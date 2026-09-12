"""Kênh giao thông báo Web Push — kênh thứ ba sau extension và Telegram.

Kênh này KHÔNG sinh thông báo riêng: nó dùng lại đúng pipe của
``src/services/reminders.py`` (gộp bundle, giờ yên lặng, trần mỗi giờ) và chỉ
khác ở chỗ giao, y như ``telegram_channel.deliver_due_notifications()``.

Hai ràng buộc quan trọng nhất ở đây:

- Receipt chỉ được ghi SAU khi push service nhận thành công. Ghi trước là mất
  hẳn thông báo khi mạng rớt giữa chừng, vì bundle đó sẽ không bao giờ tới hạn
  lần thứ hai.
- Không ghi nội dung thông báo hay endpoint đầy đủ vào log (PRD §13). Endpoint
  là bí mật giao vận: ai có nó thì đẩy được thông báo vào máy người dùng.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.push_subscription import PushSubscription
from src.services import reminders as reminders_service

logger = logging.getLogger(__name__)

# Tên kênh dùng chung cho get_due_notifications() và bảng receipt. Đổi chuỗi
# này là mọi thông báo đã giao trước đó bị coi như chưa giao, nên giữ cố định.
WEB_PUSH_CHANNEL = "webpush"
# Trần độ dài phần thân thông báo. Push service giới hạn payload (~4KB sau khi
# mã hoá) và OS cũng cắt bớt khi hiển thị, nên cắt sớm ở đây cho có kiểm soát.
WEB_PUSH_BODY_LIMIT = 1200


class WebPushError(RuntimeError):
    """Lỗi gửi Web Push đã loại nội dung thông báo và endpoint khỏi thông điệp."""


class WebPushGoneError(WebPushError):
    """Push service trả 404/410 — endpoint đã chết vĩnh viễn, phải xoá."""


@dataclass(frozen=True)
class WebPushPayload:
    """Phần dữ liệu service worker của trình duyệt nhận được.

    Giữ đúng ba trường mà một OS notification cần (tiêu đề, thân, khoá gộp) và
    một liên kết bằng chứng tuỳ chọn, để phía client không phải đoán cấu trúc.
    """

    title: str
    body: str
    tag: str
    url: str | None = None


def _endpoint_fingerprint(endpoint: str) -> str:
    """Rút endpoint thành 12 ký tự băm để log truy vết được mà không rò bí mật.

    Cùng một endpoint luôn cho cùng một dấu vân tay nên vẫn nối được các dòng
    log của cùng một thiết bị, còn từ dấu vân tay thì không dựng lại được URL
    để gửi thông báo giả.
    """
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:12]


def _webpush_available() -> bool:
    """Có import được thư viện pywebpush hay không.

    Tách thành hàm riêng vì thư viện là phụ thuộc tuỳ chọn: môi trường chưa cài
    vẫn phải chạy được app (chỉ là không gửi được gì), và test cần thay hàm này
    thay vì phải cài thư viện thật.
    """
    try:
        import pywebpush  # noqa: F401
    except ImportError:
        return False
    return True


def render_bundle(bundle: reminders_service.NotificationBundle) -> WebPushPayload:
    """Đổi một bundle của pipe thông báo thành nội dung hiển thị được.

    Cùng khuôn với ``telegram_channel.render_bundle()``: daily_brief có dạng
    riêng vì nó là bản tổng hợp cả ngày, còn lại gộp các mục thành một danh
    sách gạch đầu dòng. Lấy liên kết bằng chứng đầu tiên có được làm ``url`` để
    người dùng bấm vào thông báo là mở đúng nguồn (FR-097), không tự bịa link.
    """
    if len(bundle.tasks) == 1 and bundle.tasks[0].kind == "daily_brief":
        payload = bundle.tasks[0].payload
        lines: list[str] = []
        for task in payload.get("dueSoonTasks", [])[:5]:
            lines.append(f"• {task.get('title', 'Việc chưa có tên')} — {task.get('dueAt', 'chưa rõ giờ')}")
        if not lines:
            lines.append("• Không có việc đã xác nhận sắp hạn trong 24 giờ.")
        if payload.get("proposedCount"):
            lines.append(f"• {payload['proposedCount']} việc đang chờ xác nhận")
        return WebPushPayload(
            title="Tóm tắt hôm nay",
            body="\n".join(lines)[:WEB_PUSH_BODY_LIMIT],
            tag=bundle.bundle_key,
        )

    lines = []
    url: str | None = None
    for item in bundle.tasks:
        line = f"• {item.title}"
        if item.due_at is not None:
            line += f" — hạn {item.due_at.isoformat()}"
        lines.append(line)
        if url is None and item.evidence_deep_link:
            url = item.evidence_deep_link
    return WebPushPayload(
        title="Nhắc việc",
        body="\n".join(lines)[:WEB_PUSH_BODY_LIMIT],
        tag=bundle.bundle_key,
        url=url,
    )


def _send_to_subscription(subscription: PushSubscription, payload_json: str) -> None:
    """Gửi một payload tới đúng một endpoint và quy lỗi về hai loại.

    Chỉ hai loại lỗi là đủ cho nơi gọi quyết định: ``WebPushGoneError`` nghĩa là
    endpoint chết hẳn (xoá đi, đừng thử lại kiếp nào nữa), còn ``WebPushError``
    là hỏng tạm thời (bỏ qua lượt này, không ghi receipt để lượt sau gửi lại).

    Import pywebpush ngay trong hàm để môi trường chưa cài thư viện vẫn import
    được module này — vòng nền sẽ tự dừng ở bước kiểm tra thay vì làm chết cả
    tiến trình lúc khởi động.
    """
    try:
        from pywebpush import WebPushException, webpush
    except ImportError as exc:  # pragma: no cover - chỉ xảy ra khi thiếu thư viện
        raise WebPushError("Thiếu thư viện pywebpush.") from exc

    settings = get_settings()
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=payload_json,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
        )
    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code in (404, 410):
            raise WebPushGoneError(f"Endpoint đã bị push service thu hồi (HTTP {status_code}).") from None
        # Không nhét exc gốc vào chuỗi: message của pywebpush có kèm body phản
        # hồi và cả endpoint.
        raise WebPushError(f"Push service trả HTTP {status_code}.") from None
    except Exception as exc:  # noqa: BLE001 - mạng/DNS/TLS đều là hỏng tạm thời
        raise WebPushError("Không gọi được push service.") from exc


def _users_with_subscriptions(db: Session) -> list[str]:
    """Danh sách user còn ít nhất một thiết bị đã đăng ký nhận Web Push.

    Quét theo user chứ không theo từng subscription vì trần thông báo mỗi giờ
    và luật gộp bundle đều tính theo user — hỏi pipe một lần cho mỗi user rồi
    mới toả ra các thiết bị mới đúng ngữ nghĩa.
    """
    rows = db.execute(select(PushSubscription.user_id).distinct()).scalars().all()
    return [str(row) for row in rows]


def _list_subscriptions(db: Session, user_id: str) -> list[PushSubscription]:
    return list(
        db.execute(select(PushSubscription).where(PushSubscription.user_id == user_id)).scalars().all()
    )


def deliver_due_web_push(db: Session, *, now: datetime | None = None) -> int:
    """Giao mọi bundle tới hạn qua Web Push, trả về số reminder đã giao.

    Cơ chế: với mỗi user có thiết bị đăng ký, hỏi pipe chung xem còn bundle nào
    chưa giao TRÊN KÊNH NÀY (kênh khác đã giao không tính) -> gửi payload tới
    mọi thiết bị của user -> chỉ khi có ít nhất một thiết bị nhận được mới ghi
    receipt. Một thiết bị chết không được phép làm mất thông báo của thiết bị
    còn sống, và cũng không được làm thông báo bị coi là đã giao.

    Trả 0 sớm khi cờ tắt, khi thiếu cặp khoá VAPID, hoặc khi chưa cài
    pywebpush — ba trường hợp "chưa dựng xong hạ tầng", không phải lỗi.
    """
    settings = get_settings()
    if not settings.web_push_enabled:
        return 0
    if not settings.vapid_private_key or not settings.vapid_public_key:
        logger.warning("Web Push đã bật nhưng thiếu cặp khoá VAPID - không gửi gì")
        return 0
    if not _webpush_available():
        logger.error("Web Push đã bật nhưng chưa cài pywebpush - không gửi gì")
        return 0

    delivered = 0
    for user_id in _users_with_subscriptions(db):
        subscriptions = _list_subscriptions(db, user_id)
        if not subscriptions:
            continue
        bundles = reminders_service.get_due_notifications(
            db,
            user_id,
            now=now,
            delivery_channel=WEB_PUSH_CHANNEL,
        )
        for bundle in bundles:
            payload_json = json.dumps(asdict(render_bundle(bundle)), ensure_ascii=False)
            any_success = False
            for subscription in list(subscriptions):
                try:
                    _send_to_subscription(subscription, payload_json)
                except WebPushGoneError:
                    # Endpoint chết vĩnh viễn: xoá luôn thay vì retry mỗi nhịp.
                    logger.info(
                        "Web Push: xoá subscription đã thu hồi user_id=%s endpoint=%s",
                        user_id,
                        _endpoint_fingerprint(subscription.endpoint),
                    )
                    subscriptions.remove(subscription)
                    db.delete(subscription)
                    db.commit()
                    continue
                except WebPushError:
                    subscription.last_error_class = "send_failed"
                    db.commit()
                    logger.warning(
                        "Web Push: gửi thất bại user_id=%s endpoint=%s",
                        user_id,
                        _endpoint_fingerprint(subscription.endpoint),
                    )
                    continue
                any_success = True
                subscription.last_used_at = now or datetime.now(UTC)
                subscription.last_error_class = None
                db.commit()
            if not any_success:
                continue
            reminders_service.record_channel_deliveries(
                db,
                user_id,
                bundle.reminder_ids,
                channel=WEB_PUSH_CHANNEL,
            )
            delivered += len(bundle.reminder_ids)
    return delivered
