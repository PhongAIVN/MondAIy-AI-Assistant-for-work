from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.channel_delivery import (
    ChannelNotificationDelivery,
    ChannelUpdateReceipt,
)
from src.models.connection import Connection
from src.models.reminder import Reminder
from src.models.task import Task
from src.models.user import User
from src.services import reminders as reminders_service

TELEGRAM_TEXT_LIMIT = 4096
# Tên kênh dùng cho receipt; phải khớp `delivery_channel` truyền vào pipe chung.
TELEGRAM_CHANNEL = "telegram"
# Tiền tố callback_data của hai nút hành động trên tin nhắn nhắc việc. Tách
# khỏi tiền tố "nav:" để webhook phân biệt được "xem một màn hình" với "đổi
# trạng thái một lời nhắc" — chỉ loại thứ hai mới có side effect.
REMINDER_ACTION_PREFIX = "rm:"
REMINDER_SNOOZE_MINUTES = 15
# Nút bấm nhanh không có chỗ chọn 1 trong 3 lý do (FR-096) nên mặc định lý do
# trung tính nhất, giống nút trên OS notification của extension. Chọn lý do đầy
# đủ vẫn làm được từ trang chi tiết công việc trong web app.
REMINDER_QUICK_DISMISS_REASON = "khong_can_nua"
# Họ callback xoá một công việc ngay từ tin nhắn Telegram: agent tự xác nhận
# việc gom nên sai thì user xoá tại chỗ, không phải mở app. callback_data giới
# hạn 64 byte nên chỉ mang task_id; quyền sở hữu kiểm lại ở server.
TASK_ACTION_PREFIX = "tk:"
AUTO_CONFIRMED_REASON = "auto_confirmed"
_GROUPED_LOOKBACK_HOURS = 24
_MAX_DELETE_BUTTONS = 6
logger = logging.getLogger(__name__)


class TelegramAPIError(RuntimeError):
    """Lỗi Bot API đã loại token và response body khỏi thông báo/log."""


@dataclass(frozen=True)
class LinkedTelegramUser:
    user_id: str
    chat_id: str


def get_web_app_public_url() -> str:
    settings = get_settings()
    if settings.web_app_public_url.strip():
        return settings.web_app_public_url.strip().rstrip("/")
    origins = [
        origin.strip().rstrip("/")
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]
    return origins[0] if origins else settings.app_public_url.rstrip("/")


def find_linked_user(db: Session, telegram_user_id: str) -> LinkedTelegramUser | None:
    connection = db.execute(
        select(Connection).where(
            Connection.provider == "telegram",
            Connection.provider_user_id == telegram_user_id,
        )
    ).scalar_one_or_none()
    if connection is None:
        return None
    try:
        user = db.get(User, int(connection.user_id))
    except ValueError:
        return None
    if user is None or not user.is_active:
        return None
    return LinkedTelegramUser(user_id=str(connection.user_id), chat_id=telegram_user_id)


def list_linked_users(db: Session) -> list[LinkedTelegramUser]:
    connections = db.execute(
        select(Connection).where(
            Connection.provider == "telegram",
            Connection.provider_user_id.is_not(None),
        )
    ).scalars()
    linked: list[LinkedTelegramUser] = []
    for connection in connections:
        try:
            user = db.get(User, int(connection.user_id))
        except ValueError:
            continue
        if user is not None and user.is_active:
            linked.append(
                LinkedTelegramUser(
                    user_id=str(connection.user_id),
                    chat_id=str(connection.provider_user_id),
                )
            )
    return linked


def _claim_receipt(db: Session, channel: str, external_id: str) -> bool:
    db.add(ChannelUpdateReceipt(channel=channel, external_update_id=external_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def claim_update(db: Session, update_id: int) -> bool:
    return _claim_receipt(db, "telegram", str(update_id))


def claim_callback_action(
    db: Session, chat_id: str, message_id: str, action: str
) -> bool:
    """Một nút trên một message chỉ gây side effect đúng một lần.

    Kết quả mới luôn được gửi bằng message mới với keyboard mới, nên người dùng
    vẫn có thể refresh chủ động mà double-tap trên keyboard cũ không tạo spam.
    """
    return _claim_receipt(db, "telegram-callback", f"{chat_id}:{message_id}:{action}")


def release_update_claim(db: Session, update_id: int) -> None:
    row = db.execute(
        select(ChannelUpdateReceipt).where(
            ChannelUpdateReceipt.channel == "telegram",
            ChannelUpdateReceipt.external_update_id == str(update_id),
        )
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()


def release_callback_claim(
    db: Session, chat_id: str, message_id: str, action: str
) -> None:
    row = db.execute(
        select(ChannelUpdateReceipt).where(
            ChannelUpdateReceipt.channel == "telegram-callback",
            ChannelUpdateReceipt.external_update_id
            == f"{chat_id}:{message_id}:{action}",
        )
    ).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.commit()


def _trim(text: str) -> str:
    if len(text) <= TELEGRAM_TEXT_LIMIT:
        return text
    return text[: TELEGRAM_TEXT_LIMIT - 1].rstrip() + "…"


async def send_message(
    chat_id: str, text: str, *, reply_markup: dict | None = None
) -> str:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise TelegramAPIError("Telegram Bot API chưa được cấu hình.")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "chat_id": chat_id,
                "text": _trim(text),
                "disable_web_page_preview": True,
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            response = await client.post(url, json=payload)
        if response.status_code >= 400:
            raise TelegramAPIError(f"Telegram Bot API trả HTTP {response.status_code}.")
        payload = response.json()
        if not payload.get("ok") or not isinstance(payload.get("result"), dict):
            raise TelegramAPIError("Telegram Bot API trả response không hợp lệ.")
        message_id = payload["result"].get("message_id")
        if message_id is None:
            raise TelegramAPIError("Telegram Bot API không trả message_id.")
        return str(message_id)
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể giao tin qua Telegram Bot API.") from exc


async def send_chat_action(chat_id: str, action: str = "typing") -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise TelegramAPIError("Telegram Bot API chưa được cấu hình.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendChatAction",
                json={"chat_id": chat_id, "action": action},
            )
        if response.status_code >= 400 or not response.json().get("ok"):
            raise TelegramAPIError(
                f"Telegram sendChatAction thất bại với HTTP {response.status_code}."
            )
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể cập nhật trạng thái Telegram.") from exc


@asynccontextmanager
async def typing_indicator(chat_id: str):
    """Giữ typing hiện diện khi xử lý lâu; lỗi UX phụ không làm hỏng kết quả."""
    stopped = asyncio.Event()

    async def pulse() -> None:
        while not stopped.is_set():
            try:
                await send_chat_action(chat_id)
            except TelegramAPIError:
                logger.debug(
                    "Không cập nhật được Telegram typing cho chat_id=%s", chat_id
                )
            try:
                await asyncio.wait_for(stopped.wait(), timeout=4.0)
            except TimeoutError:
                continue

    task = asyncio.create_task(pulse())
    await asyncio.sleep(0)
    try:
        yield
    finally:
        stopped.set()
        await task


async def clear_inline_keyboard(chat_id: str, message_id: str) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise TelegramAPIError("Telegram Bot API chưa được cấu hình.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/editMessageReplyMarkup",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": {"inline_keyboard": []},
                },
            )
        if response.status_code >= 400 or not response.json().get("ok"):
            raise TelegramAPIError(
                f"Telegram editMessageReplyMarkup thất bại với HTTP {response.status_code}."
            )
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể khóa nút Telegram cũ.") from exc


async def edit_message_text(
    chat_id: int, message_id: int, text: str, reply_markup: dict | None = None
) -> None:
    """Sửa nội dung tin nhắn Telegram; nếu không sửa được (vd. tin nhắn quá cũ) không throw lỗi."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise TelegramAPIError("Telegram Bot API chưa được cấu hình.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
            if reply_markup:
                payload["reply_markup"] = reply_markup
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/editMessageText",
                json=payload,
            )
        if response.status_code >= 400 or not response.json().get("ok"):
            raise TelegramAPIError(
                f"Telegram editMessageText thất bại với HTTP {response.status_code}."
            )
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể sửa tin nhắn Telegram.") from exc


async def configure_webhook() -> None:
    """Đăng ký webhook production bằng secret riêng; gọi từ script deploy."""
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret:
        raise TelegramAPIError("Thiếu Telegram bot token hoặc webhook secret.")
    if not settings.app_public_url.startswith("https://"):
        raise TelegramAPIError("Telegram webhook yêu cầu APP_PUBLIC_URL dùng HTTPS.")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
    webhook_url = (
        f"{settings.app_public_url.rstrip('/')}/api/v1/channels/telegram/webhook"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "url": webhook_url,
                    "secret_token": settings.telegram_webhook_secret,
                    "allowed_updates": ["message", "callback_query"],
                    "drop_pending_updates": False,
                },
            )
            if response.status_code >= 400 or not response.json().get("ok"):
                raise TelegramAPIError(
                    f"Telegram setWebhook thất bại với HTTP {response.status_code}."
                )

            commands_response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/setMyCommands",
                json={
                    "commands": [
                        {"command": "today", "description": "Tóm tắt hôm nay"},
                        {"command": "tasks", "description": "Việc cần làm"},
                        {"command": "inbox", "description": "Cập nhật cần chú ý"},
                        {"command": "settings", "description": "Cài đặt thông báo"},
                    ]
                },
            )
            if commands_response.status_code >= 400 or not commands_response.json().get(
                "ok"
            ):
                raise TelegramAPIError(
                    f"Telegram setMyCommands thất bại với HTTP {commands_response.status_code}."
                )
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể cấu hình Telegram webhook.") from exc


def recently_grouped_tasks(
    db: Session, user_id: str, *, now: datetime | None = None
) -> list[Task]:
    """Những việc agent vừa tự gom và tự xác nhận trong 24 giờ qua.

    Nguồn sự thật là reason `auto_confirmed` trên chính task, không phải
    trạng thái proposed (không còn tồn tại cho luồng gom). Chỉ tin `created_at`
    chứ không phải `updated_at`: persist_node đụng updated_at mỗi lần resync
    cụm nên task gom từ tuần trước vẫn sẽ lọt qua cửa updated_at (Antigravity
    review 2026-08-22). Sắp theo hạn rồi mới tới mới nhất để việc sắp deadline
    nổi lên trước; trần số lượng do nơi gọi quyết định.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=_GROUPED_LOOKBACK_HOURS)
    rows = (
        db.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == "confirmed",
                Task.created_at >= cutoff,
            )
            .order_by(Task.due_at.is_(None), Task.due_at, Task.id.desc())
        )
        .scalars()
        .all()
    )
    return [row for row in rows if AUTO_CONFIRMED_REASON in (row.reasons or [])]


def render_today(db: Session, user_id: str, *, now: datetime | None = None) -> str:
    text, _deletable = today_view(db, user_id, now=now)
    return text


def today_view(
    db: Session, user_id: str, *, now: datetime | None = None
) -> tuple[str, list[tuple[int, str]]]:
    """Nội dung tóm tắt hôm nay kèm danh sách việc xoá được từ tin nhắn.

    Trước đây phần "chờ bạn xác nhận" chỉ đếm số — user không biết mình bị
    gom những gì và phải mở app mới thấy (phàn nàn trực tiếp của người dùng).
    Giờ liệt kê tên việc agent đã tự xác nhận, kể cả việc chưa có hạn, và trả
    kèm (task_id, title) để webhook gắn nút Xoá đúng từng dòng.
    """
    payload = reminders_service.build_daily_digest_payload(db, user_id, now)
    lines = ["Tóm tắt hôm nay"]
    tasks = payload.get("dueSoonTasks", [])
    if tasks:
        lines.append(f"\nSắp hạn trong 24 giờ: {payload.get('dueSoonCount', len(tasks))}")
        for task in tasks:
            due_at = task.get("dueAt") or "chưa rõ giờ"
            lines.append(f"• {task.get('title', 'Việc chưa có tên')} — {due_at}")
        truncated = payload.get("dueSoonTruncated", 0)
        if truncated > 0:
            lines.append(f"… và {truncated} việc khác")
    else:
        lines.append("\nKhông có việc đã xác nhận sắp hạn trong 24 giờ.")
    grouped = recently_grouped_tasks(db, user_id, now=now)[:_MAX_DELETE_BUTTONS]
    deletable: list[tuple[int, str]] = []
    if grouped:
        lines.append("\nĐã tự xác nhận việc agent gom được:")
        for task in grouped:
            due = task.due_at.strftime("%d/%m %H:%M") if task.due_at else "chưa có hạn"
            lines.append(f"• {task.title} — {due}")
            deletable.append((task.id, task.title))
    proposed_count = int(payload.get("proposedCount", 0))
    if proposed_count:
        lines.append(f"\nChờ bạn xác nhận: {proposed_count} việc (từ chat/tệp bạn tải lên)")
    return "\n".join(lines), deletable


def render_tasks(db: Session, user_id: str) -> str:
    tasks = (
        db.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status.in_(["confirmed", "proposed"]),
            )
            .order_by(Task.due_at.is_(None), Task.due_at)
            .limit(8)
        )
        .scalars()
        .all()
    )
    if not tasks:
        return "Việc cần làm\n\nBạn chưa có việc đang mở."
    lines = ["Việc cần làm"]
    for task in tasks:
        state = "chờ xác nhận" if task.status == "proposed" else "đã xác nhận"
        due = task.due_at.isoformat() if task.due_at else "chưa có hạn"
        lines.append(f"\n• {task.title}\n  {state} · {due}")
    return "\n".join(lines)


def render_inbox(db: Session, user_id: str) -> str:
    proposed = (
        db.scalar(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == "proposed",
            )
        )
        or 0
    )
    conflicts = (
        db.scalar(
            select(func.count(Reminder.id)).where(
                Reminder.user_id == user_id,
                Reminder.status == "scheduled",
                Reminder.kind.in_(["conflict_schedule", "conflict_evidence"]),
            )
        )
        or 0
    )
    if proposed == 0 and conflicts == 0:
        return "Hộp thư công việc\n\nKhông có cập nhật nào cần bạn xử lý."
    return (
        "Hộp thư công việc\n\n"
        f"• {proposed} việc đang chờ xác nhận\n"
        f"• {conflicts} xung đột cần kiểm tra"
    )


def command_keyboard(web_app_url: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Hôm nay", "callback_data": "nav:today"},
                {"text": "Việc cần làm", "callback_data": "nav:tasks"},
            ],
            [
                {"text": "Cập nhật", "callback_data": "nav:inbox"},
                {"text": "Cài đặt", "url": f"{web_app_url.rstrip('/')}/settings"},
            ],
        ]
    }


def connect_keyboard(web_app_url: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Kết nối Mondaiy",
                    "url": f"{web_app_url.rstrip('/')}/sources?connect=telegram",
                }
            ]
        ]
    }


async def answer_callback_query(
    callback_query_id: str, text: str | None = None
) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise TelegramAPIError("Telegram Bot API chưa được cấu hình.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
            response = await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery",
                json=payload,
            )
        if response.status_code >= 400 or not response.json().get("ok"):
            raise TelegramAPIError(
                f"Telegram answerCallbackQuery thất bại với HTTP {response.status_code}."
            )
    except TelegramAPIError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise TelegramAPIError("Không thể xác nhận thao tác Telegram.") from exc


def render_bundle(
    bundle: reminders_service.NotificationBundle,
    *,
    db: Session | None = None,
    user_id: str | None = None,
) -> str:
    if len(bundle.tasks) == 1 and bundle.tasks[0].kind == "daily_brief":
        item = bundle.tasks[0]
        payload = item.payload
        lines = ["Tóm tắt hôm nay"]
        for task in payload.get("dueSoonTasks", [])[:5]:
            lines.append(
                f"• {task.get('title', 'Việc chưa có tên')} — {task.get('dueAt', 'chưa rõ giờ')}"
            )
        truncated = payload.get("dueSoonTruncated", 0)
        if truncated > 0:
            lines.append(f"• … và {truncated} việc khác")
        if not payload.get("dueSoonTasks"):
            lines.append("• Không có việc đã xác nhận sắp hạn trong 24 giờ.")
        # Việc agent gom không có hạn thì không bao giờ lọt phần dueSoon ở
        # trên — liệt kê riêng để user thấy hết những gì vừa được tự xác nhận.
        if db is not None and user_id is not None:
            grouped = recently_grouped_tasks(db, user_id)
            if grouped:
                lines.append("Đã tự xác nhận việc agent gom được:")
                for task in grouped[:_MAX_DELETE_BUTTONS]:
                    due = (
                        task.due_at.strftime("%d/%m %H:%M") if task.due_at else "chưa có hạn"
                    )
                    lines.append(f"• {task.title} — {due}")
        if payload.get("proposedCount"):
            lines.append(f"• {payload['proposedCount']} việc đang chờ xác nhận")
        return "\n".join(lines)

    lines = ["Nhắc việc"]
    for item in bundle.tasks:
        line = f"• {item.title}"
        if item.due_at is not None:
            line += f" — hạn {item.due_at.isoformat()}"
        lines.append(line)
        if item.evidence_deep_link:
            lines.append(f"  Nguồn: {item.evidence_deep_link}")
    return "\n".join(lines)


def task_delete_keyboard_rows(items: list[tuple[int, str]]) -> list[list[dict]]:
    """Một hàng nút Xoá cho từng việc, đúng thứ tự danh sách đang hiển thị.

    callback_data 64 byte chỉ đủ mang task id; quyền sở hữu và trạng thái được
    kiểm lại ở server lúc bấm, không tin field client gửi lên.
    """
    rows: list[list[dict]] = []
    for task_id, title in items[:_MAX_DELETE_BUTTONS]:
        label = f'Xoá "{title[:26]}"'
        rows.append(
            [{"text": label, "callback_data": f"{TASK_ACTION_PREFIX}{task_id}"}]
        )
    return rows


def reminder_keyboard(
    web_app_url: str, *, deletable_tasks: list[tuple[int, str]] | None = None
) -> dict:
    """Hai nút hành động cho một tin nhắn nhắc việc, cộng một lối mở app.

    callback_data không mang reminder id: Telegram giới hạn trường này 64 byte
    còn một bundle thì gộp được nhiều lời nhắc. Thay vào đó, lúc xử lý callback
    ta tra ngược từ `message_id` của chính tin nhắn đang bị bấm — receipt đã lưu
    sẵn ánh xạ đó ở `ChannelNotificationDelivery.provider_message_id`, nên
    không cần thêm chỗ lưu trạng thái nào.

    Việc agent gom đã tự xác nhận nên mỗi dòng việc kèm một nút Xoá để user
    xoá tại chỗ nếu sai (quyết định chủ sản phẩm 2026-08-22).
    """
    rows: list[list[dict]] = [
        [
            {
                "text": f"Nhắc lại {REMINDER_SNOOZE_MINUTES}p",
                "callback_data": f"{REMINDER_ACTION_PREFIX}snooze",
            },
            {"text": "Bỏ qua", "callback_data": f"{REMINDER_ACTION_PREFIX}dismiss"},
        ],
        [{"text": "Mở Mondaiy", "url": f"{web_app_url.rstrip('/')}/tasks"}],
    ]
    rows.extend(task_delete_keyboard_rows(deletable_tasks or []))
    return {"inline_keyboard": rows}


def apply_task_cancel(db: Session, user_id: str, task_id: int) -> str:
    """Xoá (huỷ) một công việc ngay từ Telegram, đúng transition cancel của web.

    Cùng ràng buộc với POST /tasks/{id}/cancel: chỉ chủ sở hữu, chỉ từ proposed
    hoặc confirmed. Task đã hoàn thành/huỷ trước đó thì trả lời tử tế thay vì
    lỗi — nơi khác (extension, web app) có thể đã xử lý trước rồi.
    """
    row = db.get(Task, int(task_id)) if str(task_id).isdigit() else None
    if row is None or row.user_id != user_id:
        return "Không tìm thấy công việc này trong danh sách của bạn."
    if row.status == "cancelled":
        return f'Công việc “{row.title}” đã bị xoá từ trước.'
    if row.status == "completed":
        return f"Công việc “{row.title}” đã xong rồi nên không xoá được nữa."
    if row.status not in {"proposed", "confirmed"}:
        return "Công việc này đang ở trạng thái không thể xoá."
    row.status = "cancelled"
    reminders_service.cancel_pending_reminders(db, row.id)
    db.commit()
    return f'Đã xoá công việc “{row.title}”.'


def _open_tasks_for_message(
    db: Session, user_id: str, message_id: str
) -> tuple[str, list[tuple[int, str]]]:
    """Dựng lại toàn bộ keyboard của một tin nhắn sau khi xoá một việc.

    Tin nhắn nhắc việc có ánh xạ reminder -> task trong receipt nên liệt kê
    chính xác các việc VẪN MỞ trên đúng tin nhắn đó; tin tóm tắt hôm nay thì
    dựng lại theo cùng truy vấn lúc render. Nhờ vậy bấm Xoá một dòng không
    làm mất nút Xoá của các dòng còn lại (rủi ro do Antigravity bắt được).
    """
    reminder_ids = reminder_ids_for_message(db, user_id, message_id)
    if reminder_ids:
        rows = (
            db.execute(
                select(Task)
                .join(Reminder, Reminder.task_id == Task.id)
                .where(Reminder.id.in_(reminder_ids), Reminder.user_id == user_id)
                .order_by(Task.due_at.is_(None), Task.due_at)
            )
            .scalars()
            .all()
        )
        style = "bundle"
    else:
        rows = recently_grouped_tasks(db, user_id)
        style = "digest"
    items = [
        (row.id, row.title)
        for row in rows
        if row.status in {"proposed", "confirmed"}
    ][:_MAX_DELETE_BUTTONS]
    return style, items


def reminder_ids_for_message(db: Session, user_id: str, message_id: str) -> list[int]:
    """Những lời nhắc đã được giao bằng đúng tin nhắn Telegram này.

    Lọc kèm `user_id` chứ không chỉ theo message_id: id tin nhắn do Telegram
    cấp theo từng chat nên hai người dùng khác nhau hoàn toàn có thể cùng có
    message_id, và thiếu điều kiện này thì bấm nút ở chat mình lại hoãn lời
    nhắc của người khác.
    """
    rows = (
        db.execute(
            select(ChannelNotificationDelivery.reminder_id).where(
                ChannelNotificationDelivery.channel == TELEGRAM_CHANNEL,
                ChannelNotificationDelivery.user_id == user_id,
                ChannelNotificationDelivery.provider_message_id == message_id,
            )
        )
        .scalars()
        .all()
    )
    return [int(row) for row in rows]


def apply_reminder_action(
    db: Session, user_id: str, message_id: str, action: str
) -> str:
    """Thực hiện nhắc lại/bỏ qua cho cả bundle và trả câu trả lời cho người dùng.

    Cơ chế: message_id -> danh sách reminder id đã giao bằng tin nhắn đó -> lọc
    lấy những lời nhắc còn `scheduled` và đúng chủ sở hữu -> áp dụng thao tác
    cho tất cả. Người dùng thấy một tin nhắn thì họ đang trả lời cho cả tin
    nhắn đó, không phải cho một dòng trong đó.

    Không tìm thấy gì cũng trả lời tử tế thay vì im lặng: lời nhắc có thể đã
    được xử lý ở extension hay web app trước đó, và đó là chuyện bình thường
    của hệ thống nhiều kênh, không phải lỗi.
    """
    if action not in ("snooze", "dismiss"):
        return "Thao tác không hợp lệ."

    reminder_ids = reminder_ids_for_message(db, user_id, message_id)
    rows = (
        db.execute(
            select(Reminder).where(
                Reminder.id.in_(reminder_ids),
                Reminder.user_id == user_id,
                Reminder.status == "scheduled",
            )
        )
        .scalars()
        .all()
        if reminder_ids
        else []
    )
    if not rows:
        return "Lời nhắc này đã được xử lý ở nơi khác rồi."

    if action == "snooze":
        for reminder in rows:
            reminders_service.snooze_reminder(
                db, reminder, minutes=REMINDER_SNOOZE_MINUTES
            )
        return f"Đã hẹn nhắc lại sau {REMINDER_SNOOZE_MINUTES} phút."

    for reminder in rows:
        reminders_service.dismiss_reminder(
            db, reminder, reason=REMINDER_QUICK_DISMISS_REASON
        )
    return "Đã bỏ qua lời nhắc này. Công việc vẫn giữ nguyên trạng thái."


async def deliver_due_notifications(db: Session, *, now: datetime | None = None) -> int:
    """Giao mọi bundle tới Telegram và chỉ ghi receipt sau send thành công."""
    delivered = 0
    web_app_url = get_web_app_public_url()
    for linked in list_linked_users(db):
        bundles = reminders_service.get_due_notifications(
            db,
            linked.user_id,
            now=now,
            delivery_channel=TELEGRAM_CHANNEL,
        )
        for bundle in bundles:
            # Nút Xoá theo từng việc trong bundle: agent đã tự xác nhận nên
            # sai thì user xoá ngay tại tin nhắn, không phải mở app.
            deletable = [
                (item.task_id, item.title)
                for item in bundle.tasks
                if item.task_id is not None
            ]
            keyboard = reminder_keyboard(web_app_url, deletable_tasks=deletable)
            try:
                message_id = await send_message(
                    linked.chat_id,
                    render_bundle(bundle, db=db, user_id=linked.user_id),
                    reply_markup=keyboard,
                )
            except TelegramAPIError as exc:
                # Một user block bot/provider lỗi riêng không được làm những user
                # phía sau trong cùng tick mất notification. Không log nội dung.
                logger.error(
                    "Telegram send failed",
                    extra={
                        "user_id": linked.user_id,
                        "channel": "telegram",
                        "error": str(exc),
                    },
                )
                continue
            reminders_service.record_channel_deliveries(
                db,
                linked.user_id,
                bundle.reminder_ids,
                channel=TELEGRAM_CHANNEL,
                provider_message_id=message_id,
            )
            delivered += len(bundle.reminder_ids)
    return delivered
