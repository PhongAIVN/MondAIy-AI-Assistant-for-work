"""Công cụ chatbot cho Planning Workspace; không ghi lịch bên ngoài."""

from __future__ import annotations

import re
from contextvars import ContextVar

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from src.agents.tools.time_tool import now
from src.db import engine
from src.services.planner.workspace import build_workspace_plan, get_or_create_preferences, validate_preferences

_user_id: ContextVar[str | None] = ContextVar("planner_workspace_user_id", default=None)
_CLOCK = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")


def set_planner_workspace_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_planner_workspace_scope() -> None:
    _user_id.set(None)


def _minute(value: str) -> int:
    clean = (value or "").strip()
    if not _CLOCK.fullmatch(clean):
        raise ValueError("Giờ phải có dạng HH:MM, ví dụ 16:00.")
    hour, minute = (int(part) for part in clean.split(":"))
    return hour * 60 + minute


def _require_user() -> str | None:
    return _user_id.get()


@tool
def generate_planner_plan(days: int = 1) -> str:
    """Tự động lập kế hoạch hôm nay hoặc tuần này từ các task đang mở.

    Dùng khi người dùng nói "lên kế hoạch hôm nay/tuần này", "xếp lịch làm
    việc", hoặc muốn biết giờ nào làm/gửi/trao đổi việc gì. ``days`` chỉ nhận
    1 (hôm nay) hoặc 7 (tuần này). Kết quả là bản nháp editable trong trang
    Planning; không tạo/sửa Google Calendar, không gửi tin nhắn và không đổi
    deadline/task.
    """
    user_id = _require_user()
    if not user_id:
        return "Chưa xác định được người dùng nên chưa thể lập kế hoạch."
    if days not in (1, 7):
        return "Chỉ lập kế hoạch 1 ngày hoặc 7 ngày."
    try:
        with Session(engine) as db:
            plan = build_workspace_plan(db, user_id, start=now(), days=days)
    except Exception as exc:  # noqa: BLE001 - trả lỗi có kiểm soát cho chat
        return f"Chưa lập được kế hoạch: {exc}"
    blocks = plan["blocks"]
    if not blocks:
        return "Chưa có task nào vừa vào thời gian làm việc. Hãy thêm task hoặc nới Workday Contract trong trang Lập kế hoạch."
    lines = [f"Bản nháp kế hoạch {days} ngày ({len(blocks)} block):"]
    for block in blocks:
        line = f"- {block.start:%a %d/%m %H:%M}–{block.end:%H:%M}: {block.title} ({block.minutes} phút). {block.why}"
        if block.communication:
            line += f" {block.communication}"
        lines.append(line)
    if plan["at_risk"]:
        lines.append("Chưa có chỗ phù hợp: " + "; ".join(item.title for item in plan["at_risk"]))
    lines.append("Bạn có thể sửa giờ hoặc Workday Contract trong /planner; MondAIy chưa ghi gì lên Google Calendar.")
    return "\n".join(lines)


@tool
def configure_planner_workday(
    workday_start: str = "",
    lunch_start: str = "",
    lunch_end: str = "",
    workday_end: str = "",
    happy_time_start: str = "",
    happy_time_end: str = "",
    happy_time_enabled: bool | None = None,
) -> str:
    """Cập nhật Workday Contract của người dùng bằng giờ địa phương HH:MM.

    Ví dụ: nghỉ trưa 12:00–14:00, Happy Time 16:00–17:00. Chỉ ghi những trường
    người dùng đã nói rõ; không đoán giờ thiếu. Đây là cấu hình nội bộ editable,
    không tạo/sửa sự kiện Google Calendar.
    """
    user_id = _require_user()
    if not user_id:
        return "Chưa xác định được người dùng nên chưa thể cập nhật lịch làm việc."
    fields = {
        "workday_start": "workday_start_minute", "lunch_start": "lunch_start_minute",
        "lunch_end": "lunch_end_minute", "workday_end": "workday_end_minute",
        "happy_time_start": "happy_time_start_minute", "happy_time_end": "happy_time_end_minute",
    }
    supplied = {
        "workday_start": workday_start,
        "lunch_start": lunch_start,
        "lunch_end": lunch_end,
        "workday_end": workday_end,
        "happy_time_start": happy_time_start,
        "happy_time_end": happy_time_end,
    }
    requested = {key: value for key, value in supplied.items() if value.strip()}
    if not requested and happy_time_enabled is None:
        return "Hãy nêu ít nhất một giờ cần đổi, ví dụ Happy Time 16:00–17:00."
    try:
        with Session(engine) as db:
            pref = get_or_create_preferences(db, user_id)
            for input_name, value in requested.items():
                setattr(pref, fields[input_name], _minute(value))
            if happy_time_enabled is not None:
                pref.happy_time_enabled = happy_time_enabled
            validate_preferences(pref)
            db.commit()
            db.refresh(pref)
    except ValueError as exc:
        return f"Chưa lưu Workday Contract: {exc}"
    return "Đã cập nhật Workday Contract. Bạn có thể mở /planner để sửa tiếp hoặc bảo mình lập lại kế hoạch."
