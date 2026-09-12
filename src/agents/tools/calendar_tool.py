"""Công cụ Calendar chỉ đọc cho agent hội thoại.

User scope do API đặt qua ContextVar, không nằm trong schema mà model có thể
điền. Mọi truy vấn bắt buộc có hai mốc thời gian để không crawl lịch vô hạn.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from langchain_core.tools import tool
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_user_id: ContextVar[str | None] = ContextVar("calendar_user_id", default=None)
_MAX_EVENTS_IN_CONTEXT = 30


def set_calendar_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_calendar_scope() -> None:
    _user_id.set(None)


@tool
async def calendar_search_events(query: str = "", time_from: str = "", time_to: str = "") -> str:
    """Đọc sự kiện Google Calendar trong một khoảng thời gian hữu hạn.

    Dùng cho câu hỏi về lịch, cuộc hẹn, sự kiện hoặc thời gian rảnh. Đây là
    công cụ chỉ đọc; không tạo, sửa, xóa sự kiện và không phản hồi lời mời.

    Args:
        query: Từ khóa trong tiêu đề/mô tả sự kiện; để trống để liệt kê cả khoảng
        time_from: Mốc bắt đầu ISO hoặc ngày/tháng/năm, bắt buộc
        time_to: Mốc kết thúc ISO hoặc ngày/tháng/năm, bắt buộc

    Returns:
        Danh sách sự kiện kèm thời gian và link nguồn Google Calendar
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được đây là lịch của ai nên chưa đọc. Tầng gọi phải đặt phạm vi người dùng trước."

    from src.agents.tools.time_tool import parse_timestamp

    start = parse_timestamp(time_from)
    end = parse_timestamp(time_to)
    if start is None or end is None:
        return (
            "Cần cả time_from và time_to ở dạng ngày/tháng/năm hoặc ISO để đọc lịch; "
            "không được tìm Calendar không giới hạn."
        )
    if start.moment >= end.moment:
        return "Khoảng thời gian lịch không hợp lệ: time_from phải sớm hơn time_to."

    from src.db import engine
    from src.services.calendar_tools import search_calendar_events

    try:
        with Session(engine) as db:
            result = await search_calendar_events(
                db,
                user_id,
                start.moment,
                end.moment,
                query=query.strip(),
            )
    except Exception as exc:  # Connector lỗi phải thành câu trả lời có kiểm soát.
        logger.warning("Đọc Calendar hỏng cho user %s: %s", user_id, exc)
        return f"Không đọc được Google Calendar: {exc}"

    events = result["events"]
    if not events:
        return f"Không có sự kiện Calendar nào khớp từ {start.moment.isoformat()} đến {end.moment.isoformat()}."

    visible = events[:_MAX_EVENTS_IN_CONTEXT]
    lines = [f"Google Calendar từ {start.moment.isoformat()} đến {end.moment.isoformat()}:"]
    for event in visible:
        start_at = event.get("start_at") or "không rõ giờ bắt đầu"
        end_at = event.get("end_at") or "không rõ giờ kết thúc"
        calendar_name = event.get("calendar_name")
        calendar_suffix = f" [{calendar_name}]" if calendar_name else ""
        line = f"- {event['title']}{calendar_suffix} — {start_at} → {end_at}"
        if event.get("deep_link"):
            line += f"\n  nguồn: {event['deep_link']}"
        lines.append(line)

    if len(events) > _MAX_EVENTS_IN_CONTEXT:
        lines.append(f"Còn {len(events) - _MAX_EVENTS_IN_CONTEXT} sự kiện khác trong khoảng này.")
    return "\n".join(lines)
