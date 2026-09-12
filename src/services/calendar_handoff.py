"""Sinh mẫu chuyển sang ứng dụng lịch cho 1 Task đã confirmed — tệp .ics và
link mẫu Google Calendar (FR-064). Không OAuth, không CRUD event trực tiếp:
người dùng tự mở link/tệp và tự lưu bằng ứng dụng lịch của họ (FR-062)."""

from __future__ import annotations

from datetime import UTC, timedelta
from urllib.parse import urlencode

# Hạn chót chỉ có 1 mốc thời gian, không phải khoảng họp thật — chặn hiển thị
# thành block 0 phút (nhiều app lịch tự giãn về 1h nếu DTEND=DTSTART).
_DEFAULT_BLOCK = timedelta(minutes=15)

GOOGLE_CALENDAR_RENDER_URL = "https://calendar.google.com/calendar/render"
_ICS_LINE_OCTETS = 75


def _escape_ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_ics_line(line: str) -> str:
    """Gấp content line theo RFC 5545, không cắt giữa ký tự UTF-8.

    Dòng đầu tối đa 75 octet; các dòng tiếp theo bắt đầu bằng một space nên
    payload của chúng tối đa 74 octet.
    """
    if len(line.encode("utf-8")) <= _ICS_LINE_OCTETS:
        return line

    chunks: list[str] = []
    current = ""
    current_octets = 0
    limit = _ICS_LINE_OCTETS
    for char in line:
        char_octets = len(char.encode("utf-8"))
        if current and current_octets + char_octets > limit:
            chunks.append(current)
            current = ""
            current_octets = 0
            limit = _ICS_LINE_OCTETS - 1
        current += char
        current_octets += char_octets
    if current:
        chunks.append(current)
    return "\r\n ".join(chunks)


def _format_utc(dt) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _build_notes(detail: str, evidence: list[dict]) -> str:
    lines = [detail] if detail else []
    for item in evidence[:5]:
        quote = (item.get("evidence_quote") or "").strip()
        link = item.get("deep_link") or ""
        if link:
            lines.append(f"Nguồn: {link}" + (f" — {quote}" if quote else ""))
    return "\n".join(lines)


def build_ics(task, evidence: list[dict]) -> str:
    """`task` cần due_at != None (gọi trước khi validate ở API layer)."""
    start = task.due_at
    end = start + _DEFAULT_BLOCK
    notes = _build_notes(task.detail, evidence)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//mondaiy//calendar-handoff//VI",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:mondaiy-task-{task.cluster_key}@mondaiy.vn",
        f"DTSTAMP:{_format_utc(start)}",
        f"DTSTART:{_format_utc(start)}",
        f"DTEND:{_format_utc(end)}",
        f"SUMMARY:{_escape_ics_text(task.title)}",
    ]
    if notes:
        lines.append(f"DESCRIPTION:{_escape_ics_text(notes)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold_ics_line(line) for line in lines) + "\r\n"


def build_google_calendar_url(task, evidence: list[dict]) -> str:
    start = task.due_at
    end = start + _DEFAULT_BLOCK
    notes = _build_notes(task.detail, evidence)
    params = {
        "action": "TEMPLATE",
        "text": task.title,
        "dates": f"{_format_utc(start)}/{_format_utc(end)}",
        "details": notes,
    }
    return f"{GOOGLE_CALENDAR_RENDER_URL}?{urlencode(params)}"
