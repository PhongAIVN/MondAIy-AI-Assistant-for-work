from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db import get_db
from src.services import telegram_channel, telegram_chat
from src.services.connections import telegram as telegram_connection

router = APIRouter(prefix="/channels/telegram", tags=["telegram-channel"])


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    update_id: int
    message: dict | None = None
    callback_query: dict | None = None


def _verify_secret(received: str | None) -> None:
    expected = get_settings().telegram_webhook_secret
    if not expected:
        raise HTTPException(
            status_code=503, detail="Telegram webhook chưa được cấu hình."
        )
    if received is None or not hmac.compare_digest(received, expected):
        raise HTTPException(
            status_code=401, detail="Telegram webhook secret không hợp lệ."
        )


@router.post("/webhook", status_code=200)
async def telegram_webhook(
    update: TelegramUpdate,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _verify_secret(secret)
    if not telegram_channel.claim_update(db, update.update_id):
        return {"ok": True}

    callback = update.callback_query or {}
    message = update.message or (
        callback.get("message") if isinstance(callback.get("message"), dict) else {}
    )
    sender_source = callback.get("from") if callback else message.get("from")
    sender = sender_source if isinstance(sender_source, dict) else {}
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    text = message.get("text") if isinstance(message.get("text"), str) else ""
    callback_data = (
        callback.get("data") if isinstance(callback.get("data"), str) else ""
    )
    callback_id = str(callback.get("id", ""))
    message_id = str(message.get("message_id", ""))
    sender_id = str(sender.get("id", ""))
    chat_id = str(chat.get("id", ""))

    # P0 chỉ hỗ trợ private chat với chính identity đã login. Group chat có thể
    # làm lộ nội dung cho thành viên khác nên không phản hồi dữ liệu nội bộ.
    if not sender_id or chat.get("type") != "private" or chat_id != sender_id:
        return {"ok": True}

    linked = telegram_channel.find_linked_user(db, sender_id)
    callback_claim: tuple[str, str, str] | None = None
    try:
        start_payload = (
            text.split(maxsplit=1)[1].strip() if text.startswith("/start ") else ""
        )
        if linked is None and start_payload.startswith("link_"):
            label = str(
                sender.get("username")
                or sender.get("first_name")
                or f"telegram:{sender_id}"
            )
            linked_user_id = telegram_connection.consume_bot_link(
                db,
                start_payload.removeprefix("link_"),
                telegram_user_id=sender_id,
                account_label=label,
            )
            if linked_user_id is not None:
                linked = telegram_channel.LinkedTelegramUser(
                    user_id=linked_user_id, chat_id=sender_id
                )
        if linked is None:
            await telegram_channel.send_message(
                chat_id,
                "Telegram này chưa liên kết với Mondaiy. Kết nối để nhận tóm tắt và nhắc việc riêng của bạn.",
                reply_markup=telegram_channel.connect_keyboard(
                    telegram_channel.get_web_app_public_url()
                ),
            )
        else:
            command = text.split(maxsplit=1)[0].split("@", 1)[0].lower() if text else ""
            # Hai họ callback tách bạch: "nav:" chỉ mở một màn hình, "rm:" đổi
            # trạng thái một lời nhắc. Giữ nguyên tiền tố trong khoá claim để
            # bấm "Xem hôm nay" và bấm "Nhắc lại" trên cùng một tin nhắn không
            # bị coi là cùng một thao tác.
            nav_action = (
                callback_data.removeprefix("nav:")
                if callback_data.startswith("nav:")
                else ""
            )
            reminder_action = (
                callback_data.removeprefix(telegram_channel.REMINDER_ACTION_PREFIX)
                if callback_data.startswith(telegram_channel.REMINDER_ACTION_PREFIX)
                else ""
            )
            task_action = (
                callback_data.removeprefix(telegram_channel.TASK_ACTION_PREFIX)
                if callback_data.startswith(telegram_channel.TASK_ACTION_PREFIX)
                else ""
            )
            # Ba họ callback tách bạch: "nav:" chỉ mở một màn hình, "rm:" đổi
            # trạng thái lời nhắc, "tk:" xoá một công việc. Giữ nguyên tiền tố
            # trong khoá claim để các nút khác nhau trên cùng một tin nhắn
            # không bị coi là cùng một thao tác.
            action = (
                nav_action
                or (f"rm-{reminder_action}" if reminder_action else "")
                or (f"tk-{task_action}" if task_action else "")
            )
            if callback_id:
                if not action or not message_id:
                    await telegram_channel.answer_callback_query(
                        callback_id, "Thao tác không hợp lệ."
                    )
                    return {"ok": True}
                if not telegram_channel.claim_callback_action(
                    db, chat_id, message_id, action
                ):
                    await telegram_channel.answer_callback_query(
                        callback_id, "Yêu cầu đã được nhận. Vui lòng đợi kết quả."
                    )
                    return {"ok": True}
                callback_claim = (chat_id, message_id, action)
                await telegram_channel.answer_callback_query(callback_id, "Đang tải…")
                if not task_action:
                    try:
                        await telegram_channel.clear_inline_keyboard(chat_id, message_id)
                    except telegram_channel.TelegramAPIError:
                        # Keyboard cũ có thể đã bị Telegram xoá; kết quả vẫn phải trả.
                        pass

            async with telegram_channel.typing_indicator(chat_id):
                if task_action:
                    response_text = telegram_channel.apply_task_cancel(
                        db, linked.user_id, task_action
                    )
                    # Dựng lại keyboard từ trạng thái DB thay vì xoá sạch:
                    # các nút Xoá của việc còn lại phải bấm được tiếp.
                    style, remaining = telegram_channel._open_tasks_for_message(
                        db, linked.user_id, message_id
                    )
                    base = (
                        telegram_channel.reminder_keyboard(
                            telegram_channel.get_web_app_public_url()
                        )
                        if style == "bundle"
                        else telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        )
                    )
                    rows = list(base["inline_keyboard"]) + (
                        telegram_channel.task_delete_keyboard_rows(remaining)
                    )
                    try:
                        await telegram_channel.edit_message_text(
                            int(chat_id),
                            int(message_id),
                            response_text,
                            {"inline_keyboard": rows},
                        )
                    except telegram_channel.TelegramAPIError:
                        # Message quá cũ hoặc đã bị xoá; gửi tin nhắn mới.
                        await telegram_channel.send_message(
                            chat_id,
                            response_text,
                            reply_markup={"inline_keyboard": rows},
                        )
                elif reminder_action:
                    response_text = telegram_channel.apply_reminder_action(
                        db, linked.user_id, message_id, reminder_action
                    )
                    # Sửa message cũ thay vì gửi tin nhắn mới; nếu sửa fail thì fallback gửi tin mới.
                    try:
                        await telegram_channel.edit_message_text(
                            int(chat_id), int(message_id), response_text
                        )
                    except telegram_channel.TelegramAPIError:
                        # Message quá cũ hoặc đã bị xoá; gửi tin nhắn mới.
                        await telegram_channel.send_message(
                            chat_id,
                            response_text,
                            reply_markup=telegram_channel.command_keyboard(
                                telegram_channel.get_web_app_public_url()
                            ),
                        )
                elif command == "/today" or nav_action == "today":
                    text, deletable = telegram_channel.today_view(db, linked.user_id)
                    rows = list(
                        telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        )["inline_keyboard"]
                    ) + telegram_channel.task_delete_keyboard_rows(deletable)
                    await telegram_channel.send_message(
                        chat_id,
                        text,
                        reply_markup={"inline_keyboard": rows},
                    )
                elif command == "/tasks" or nav_action == "tasks":
                    response_text = telegram_channel.render_tasks(db, linked.user_id)
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                elif command == "/inbox" or nav_action == "inbox":
                    response_text = telegram_channel.render_inbox(db, linked.user_id)
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                elif command == "/settings" or nav_action == "settings":
                    response_text = "Mở cài đặt Mondaiy để chọn giờ nhận tin và khoảng thời gian yên lặng."
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                elif command == "/start":
                    response_text = (
                        "Mondaiy đã được liên kết. Bạn có thể xem nhanh hôm nay, việc cần làm "
                        "và các cập nhật cần chú ý ngay tại đây."
                    )
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                elif command.startswith("/"):
                    # Lệnh lạ: hướng dẫn ngắn thay vì nạp rác vào agent chat.
                    response_text = (
                        "Mình chưa có lệnh này. Gõ thẳng câu hỏi của bạn "
                        "hoặc dùng các nút bên dưới."
                    )
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                elif text.strip():
                    # Chat tự do: chạy cùng agent pipeline với web chat để user
                    # hỏi việc ngay trong Telegram, có đầy đủ bộ nhớ và nguồn.
                    response_text = await telegram_chat.handle_free_message(
                        db, linked.user_id, text.strip()
                    )
                    await telegram_channel.send_message(
                        chat_id,
                        response_text,
                        reply_markup=telegram_channel.command_keyboard(
                            telegram_channel.get_web_app_public_url()
                        ),
                    )
                # Còn lại là tin nhắn không mang chữ (ảnh, sticker…): bỏ qua
                # im lặng thay vì trả lời thừa.
    except Exception as exc:
        # Mọi lỗi chưa trả kết quả thành công đều phải nhả claim. Nếu chỉ
        # bắt TelegramAPIError, một lỗi render/DB bất ngờ sẽ giữ receipt
        # vĩnh viễn và mọi retry sau bị coi là duplicate.
        db.rollback()
        telegram_channel.release_update_claim(db, update.update_id)
        if callback_claim is not None:
            telegram_channel.release_callback_claim(db, *callback_claim)
        if isinstance(exc, telegram_channel.TelegramAPIError):
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if isinstance(exc, RuntimeError):
            # Agent chat tự do hỏng: trả 502 để Telegram retry, claim đã nhả
            # nên lượt retry được xử lý lại từ đầu thay vì bị nuốt.
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        raise
    return {"ok": True}
