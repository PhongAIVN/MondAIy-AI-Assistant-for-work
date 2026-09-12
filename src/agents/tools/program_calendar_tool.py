"""Công cụ đọc lịch chương trình, chỉ mở cho người dùng mức A.

Mức truy cập và cohort do backend đặt qua ContextVar, giống mọi tool khác trong
thư mục này: chúng cố tình không nằm trong chữ ký tool để model — hoặc một câu
lệnh nhét vào prompt — không tự nâng quyền mình lên mức A được.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_access_level: ContextVar[str | None] = ContextVar("program_calendar_level", default=None)
_cohort_slug: ContextVar[str | None] = ContextVar("program_calendar_cohort", default=None)
_scope_da_dat: ContextVar[bool] = ContextVar("program_calendar_da_dat", default=False)

_MAX_EVENTS_IN_CONTEXT = 20

# Nhãn tiếng Việt cho từng loại mốc, để câu trả lời không lộ tên khóa kỹ thuật.
_TYPE_LABEL = {
    "custom": "Sự kiện",
    "daily_deadline": "Hạn daily",
    "weekly_deadline": "Hạn weekly",
    "gate_deadline": "Hạn gate",
    "mentor_duty": "Mentor duty",
}


def set_program_calendar_scope(access_level: str | None, cohort_slug: str | None) -> None:
    """Đặt mức truy cập chương trình và cohort cho lượt chạy hiện tại."""
    _access_level.set((access_level or "").strip().upper() or None)
    _cohort_slug.set((cohort_slug or "").strip() or None)
    _scope_da_dat.set(True)


def reset_program_calendar_scope() -> None:
    """Xóa phạm vi, đưa tool về trạng thái từ chối đọc."""
    _access_level.set(None)
    _cohort_slug.set(None)
    _scope_da_dat.set(False)


def _display_time(moment: datetime) -> str:
    from src.config import get_settings

    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(get_settings().app_timezone)).strftime("%d/%m/%Y %H:%M")


@tool
def program_schedule(query: str = "", since: str = "", until: str = "", limit: int = 12) -> str:
    """Tra lịch chính thức của chương trình: workshop, office hour, hạn nộp, gate.

    Dùng khi người dùng hỏi lịch học, buổi nào diễn ra khi nào, hạn nộp daily /
    weekly / gate, deadline sắp tới của khóa. Đây là lịch do ban tổ chức công
    bố, khác với `calendar_search_events` (lịch Google cá nhân của người dùng).

    Chỉ tài khoản đã khớp danh tính chương trình mới đọc được. Lịch trực riêng
    của từng nhóm mentor không nằm trong tool này.

    Args:
        query: Từ khóa lọc theo tiêu đề/mô tả, bỏ trống là lấy cả khoảng
        since: Chỉ lấy từ mốc này trở đi, ví dụ "12/08/2026"
        until: Chỉ lấy tới mốc này, ví dụ "20/08/2026"
        limit: Số sự kiện tối đa, mặc định 12

    Returns:
        Danh sách mốc theo thứ tự thời gian, kèm loại mốc, người chủ trì và link
    """
    if not _scope_da_dat.get():
        return (
            "Chưa xác định được tài khoản này thuộc chương trình nào nên chưa đọc lịch. "
            "Tầng gọi phải đặt phạm vi trước."
        )

    level = _access_level.get()
    cohort = _cohort_slug.get()
    # Mức B/C phải nhận đúng lý do, không phải danh sách rỗng: trả về rỗng là
    # nói với học viên rằng chương trình không có buổi nào, sai hoàn toàn.
    if level != "A":
        return (
            "Tài khoản này chưa khớp danh tính chương trình nên chưa đọc được lịch chung. "
            "Kết nối Discord bằng đúng tài khoản đang tham gia khóa rồi thử lại."
        )
    if not cohort:
        return "Chưa biết tài khoản này thuộc khóa nào nên chưa đọc lịch chương trình."

    from src.agents.tools.core_tools import _parse_window

    window, window_error = _parse_window(since, until)
    if window_error:
        return window_error

    from src.db import SessionLocal
    from src.services.program_calendar import list_program_events

    try:
        with SessionLocal() as db:
            events = list_program_events(
                db,
                cohort_slug=cohort,
                since=window.get("since"),
                until=window.get("until"),
                query=query.strip(),
                limit=min(max(1, limit), _MAX_EVENTS_IN_CONTEXT),
            )
    except Exception as exc:  # Lỗi đọc DB phải thành câu trả lời có kiểm soát.
        logger.warning("Đọc lịch chương trình hỏng cho cohort %s: %s", cohort, exc)
        return "Không đọc được lịch chương trình lúc này. Hệ thống đã ghi nhận lỗi để xử lý."

    if not events:
        if window:
            return "Không có mốc nào của chương trình trong khoảng thời gian đó. Ngoài khoảng này có thể vẫn có."
        return "Chưa có mốc nào trong lịch chương trình đã nhập."

    lines = ["Lịch chương trình (giờ Việt Nam):"]
    for event in events:
        label = _TYPE_LABEL.get(event.event_type, "Sự kiện")
        when = _display_time(event.starts_at)
        if event.ends_at is not None:
            when += f" → {_display_time(event.ends_at)}"
        line = f"- [{label}] {event.title} — {when}"
        if event.host:
            line += f" · chủ trì: {event.host}"
        if event.location_url:
            line += f"\n  link: {event.location_url}"
        note = " ".join(event.description.split())[:300]
        if note:
            line += f"\n  ghi chú: {note}"
        lines.append(line)
    return "\n".join(lines)
