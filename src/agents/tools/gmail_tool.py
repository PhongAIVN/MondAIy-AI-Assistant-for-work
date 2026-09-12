"""Read-only Gmail tools for the in-app agent.

The OAuth connection is selected from a ContextVar set by the authenticated API
layer, so an LLM can never supply another user's account identifier.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from langchain_core.tools import tool
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_user_id: ContextVar[str | None] = ContextVar("gmail_user_id", default=None)
_MAX_BODY_CHARS = 1_500


def set_gmail_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_gmail_scope() -> None:
    _user_id.set(None)


def _format_message(message: dict, *, include_body: bool) -> str:
    subject = message.get("subject") or "(không có tiêu đề)"
    sender = message.get("author_name") or message.get("author_id") or "không rõ người gửi"
    sent_at = message.get("sent_at") or "không rõ thời điểm"
    text = (message.get("normalized_text") or message.get("text") or message.get("snippet") or "").strip()
    if include_body:
        text = text[:_MAX_BODY_CHARS]
    else:
        text = text[:400]
    lines = [
        f"ID: {message.get('id', '')}",
        f"Tiêu đề: {subject}",
        f"Người gửi: {sender}",
        f"Thời gian: {sent_at}",
    ]
    if text:
        lines.append(f"Nội dung: {text}")
    if message.get("deep_link"):
        lines.append(f"Nguồn: {message['deep_link']}")
    return "\n".join(lines)


@tool
async def gmail_search_emails(query: str = "", time_from: str = "", time_to: str = "") -> str:
    """Tìm email trong Gmail của chính người dùng, trong khoảng thời gian hữu hạn.

    Dùng cho câu hỏi về email, hộp thư, thư từ một người, deadline hoặc nội dung
    trong mail. ``query`` dùng từ khóa thông thường hoặc Gmail search syntax như
    ``from:mentor@example.com``, ``subject:report`` hay ``is:unread``. Chỉ đọc,
    không gửi, sửa, gắn nhãn, lưu trữ hoặc xóa email.
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được hộp thư của ai nên chưa đọc. Tầng gọi phải đặt phạm vi người dùng trước."

    from src.agents.tools.time_tool import parse_timestamp

    start = parse_timestamp(time_from)
    end = parse_timestamp(time_to)
    if start is None or end is None:
        return "Cần cả time_from và time_to ở dạng ngày/tháng/năm hoặc ISO để đọc Gmail có giới hạn."
    if start.moment >= end.moment:
        return "Khoảng Gmail không hợp lệ: time_from phải sớm hơn time_to."

    from src.db import engine
    from src.services.gmail_tools import search_gmail_messages

    try:
        with Session(engine) as db:
            messages = await search_gmail_messages(db, user_id, start.moment, end.moment, query=query.strip())
    except Exception as exc:
        logger.warning("Đọc Gmail hỏng cho user %s: %s", user_id, exc)
        return f"Không đọc được Gmail: {exc}"

    if not messages:
        return f"Không có email nào khớp từ {start.moment.isoformat()} đến {end.moment.isoformat()}."
    return "\n\n".join(_format_message(message, include_body=False) for message in messages)


@tool
async def gmail_read_email(message_id: str) -> str:
    """Đọc nội dung một email chính xác trong Gmail của chính người dùng.

    Chỉ dùng ``message_id`` vừa nhận từ gmail_search_emails. Công cụ chỉ đọc,
    không thực hiện bất kỳ thay đổi nào với email.
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được hộp thư của ai nên chưa đọc. Tầng gọi phải đặt phạm vi người dùng trước."
    if not message_id.strip():
        return "Cần message_id từ kết quả gmail_search_emails trước khi đọc email."

    from src.db import engine
    from src.services.gmail_tools import read_gmail_message

    try:
        with Session(engine) as db:
            message = await read_gmail_message(db, user_id, message_id.strip())
    except Exception as exc:
        logger.warning("Đọc email Gmail hỏng cho user %s: %s", user_id, exc)
        return f"Không đọc được email Gmail: {exc}"
    return _format_message(message, include_body=True)


@tool
async def gmail_deadline_sweep(query: str = "", time_from: str = "", time_to: str = "") -> str:
    """Quét Gmail nhiều lớp để tìm clue công việc/deadline cho daily brief.

    Kết quả chưa phải sự thật đã xác minh: hãy đọc message ID cụ thể trước khi
    kết luận owner, trạng thái hoặc deadline.  Nếu một sweep lỗi, coverage là
    partial và không được diễn giải thành "không có việc".
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được hộp thư của ai nên chưa đọc Gmail."
    from src.agents.tools.time_tool import parse_timestamp
    start = parse_timestamp(time_from)
    end = parse_timestamp(time_to)
    if start is None or end is None or start.moment >= end.moment:
        return "Cần time_from và time_to hợp lệ để quét Gmail."
    from src.db import engine
    from src.services.gmail_tools import search_gmail_deadline_candidates
    try:
        with Session(engine) as db:
            messages, receipts = await search_gmail_deadline_candidates(
                db, user_id, start.moment, end.moment, query=query
            )
    except Exception as exc:
        logger.warning("Quét deadline Gmail hỏng cho user %s: %s", user_id, exc)
        return f"Gmail coverage: partial (sweep_error: {exc})\nKhông được kết luận không có việc."
    status = "complete" if all(item.status == "complete" for item in receipts) else "partial"
    lines = [
        f"Gmail coverage: {status}; candidates={len(messages)}; verified_work_items=0",
        "Các candidate dưới đây chỉ là clue; cần gmail_read_email để xác minh evidence.",
    ]
    for receipt in receipts:
        detail = f"count={receipt.message_count}"
        if receipt.error:
            detail += f" error={receipt.error}"
        lines.append(f"sweep[{receipt.family.value}]: {receipt.status} {detail}")
    if messages:
        lines.extend(_format_message(message, include_body=False) for message in messages)
    else:
        lines.append("Không phát hiện candidate trong phạm vi đã quét; đây không phải xác nhận mailbox không có việc.")
    return "\n\n".join(lines)
