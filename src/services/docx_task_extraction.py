"""Đọc task cá nhân từ DOCX dạng bảng công việc hoặc lịch công tác tuần."""

from __future__ import annotations

import re
from io import BytesIO
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from src.guardrail.attachment_safety import AttachmentRejectedError, assert_uncompressed_size_ok
from src.services.spreadsheet_task_extraction import full_name_mentioned, name_match_kind, normalize_text, parse_due

DOCX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MAX_UNCOMPRESSED_DOCX_BYTES = 5 * 1024 * 1024
_DAY_DATE_PATTERN = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
_WEEKDAY_PATTERN = re.compile(r"\b(Thứ\s*(?:Hai|Ba|Tư|Năm|Sáu|Bảy)|Chủ\s*nhật|CN)\b", re.IGNORECASE)
_TIME_PATTERN = re.compile(r"^\s*(\d{1,2}[h:\.]\d{0,2}(?:\s*[-–]\s*\d{1,2}[h:\.]?\d{0,2})?)\s*[:\.]?\s*")
_SESSION_PATTERN = re.compile(r"^\s*(Sáng|Chiều|Tối|Cả ngày|Cả ngày và tối)\s*[:\.]?\s*", re.IGNORECASE)
_LOCATION_PATTERN = re.compile(r"^\s*(Tại|Địa điểm|Location)\b[\s:]*", re.IGNORECASE)
_PARTICIPANT_PATTERN = re.compile(r"^\s*(Thành phần|Đại biểu|Attendees?|Mời)\s*:\s*", re.IGNORECASE)
_ASSIGNEE_VERBS = (
    "dự|tham dự|họp|làm việc|khảo sát|tham gia|kiểm tra|thăm|chủ trì|báo cáo|tiếp|"
    "ký kết|nghiệm thu|giám sát|chỉ đạo|trao đổi|hội ý|hội nghị|gặp|đón tiếp|"
    "tổng kết|sơ kết|dự thảo|duyệt|phê duyệt|nghe báo cáo|làm trưởng đoàn|trực"
)
_ASSIGNEE_PATTERN = re.compile(
    rf"^\s*((?:A\.?|Anh|Chị|Ông|Bà|Đ/c|Đồng chí)\s+[^,.;:]+?)(?=\s+(?:{_ASSIGNEE_VERBS})\b)",
    re.UNICODE | re.IGNORECASE,
)
_GENERIC_HEADERS = {
    "title": ("ten cong viec", "noi dung cong viec", "noi dung", "cong viec", "hang muc", "dau viec", "task", "title"),
    "assignee": ("nguoi phu trach", "nguoi chiu trach nhiem", "lanh dao chi dao", "lanh dao phu trach", "owner", "assignee", "chu tri"),
    "due": ("han chot", "han hoan thanh", "ngay hoan thanh", "deadline", "due date", "han"),
    "status": ("trang thai", "tinh trang", "ket qua", "ghi chu", "status", "note"),
}


class DocxExtractionError(ValueError):
    """Lỗi DOCX an toàn để API trả trực tiếp cho người dùng."""


def _lines(cell) -> list[str]:
    return [
        line.strip()
        for paragraph in cell.paragraphs
        for line in paragraph.text.splitlines()
        if line.strip()
    ]


def _cell_text(cell) -> str:
    return " ".join(_lines(cell))


def _best_match(values: list[str], display_name: str) -> tuple[str, str]:
    ranked = {"none": 0, "possible": 1, "close": 2, "exact": 3}
    best_value, best_kind = "", "none"
    for value in values:
        parts = re.split(r"[;,/]\s*|\s+và\s+", value, flags=re.IGNORECASE)
        for part in [value, *parts]:
            kind = name_match_kind(part, display_name)
            if ranked[kind] > ranked[best_kind]:
                best_value, best_kind = part.strip(), kind
    # Một họ tên đầy đủ xuất hiện trong danh sách thành phần vẫn là khớp gần
    # tin cậy, dù ô có thêm tên người khác.
    display = normalize_text(display_name)
    if best_kind == "none" and len(display.split()) >= 2 and display and any(display in normalize_text(value) for value in values):
        return display_name, "close"
    return best_value, best_kind


def _time_marker(line: str) -> tuple[str | None, str]:
    match = _TIME_PATTERN.match(line)
    if match:
        return match.group(1), _TIME_PATTERN.sub("", line, count=1)
    match = _SESSION_PATTERN.match(line)
    if match:
        return match.group(1), _SESSION_PATTERN.sub("", line, count=1)
    return None, line


def _group_blocks(lines: list[str]) -> list[list[str]]:
    if not any(_time_marker(line)[0] for line in lines):
        return [lines] if lines else []
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _time_marker(line)[0]:
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
        else:
            current = [line]
    if current:
        blocks.append(current)
    return blocks


def _parse_block(lines: list[str]) -> dict[str, str | None]:
    time_value, first = _time_marker(lines[0])
    content = [first] if first else []
    locations: list[str] = []
    participants: list[str] = []
    participant_mode = False
    for line in lines[1:]:
        if _LOCATION_PATTERN.match(line):
            locations.append(_LOCATION_PATTERN.sub("", line).strip())
            participant_mode = False
        elif _PARTICIPANT_PATTERN.match(line):
            participants.append(_PARTICIPANT_PATTERN.sub("", line).strip())
            participant_mode = True
        elif participant_mode:
            participants.append(line)
        else:
            content.append(line)
    full_content = " ".join(part for part in content if part).strip()
    assignee_match = _ASSIGNEE_PATTERN.match(full_content)
    return {
        "time": time_value,
        "content": full_content,
        "assignee": assignee_match.group(1).strip(" -") if assignee_match else None,
        "participants": "; ".join(participants) if participants else None,
        "location": "; ".join(locations) if locations else None,
    }


def _generic_header_map(table) -> tuple[int, dict[str, int]] | None:
    for row_index, row in enumerate(table.rows[:5]):
        mapping: dict[str, int] = {}
        for column, cell in enumerate(row.cells):
            header = normalize_text(_cell_text(cell))
            for field, aliases in _GENERIC_HEADERS.items():
                if field not in mapping and any(alias in header for alias in aliases):
                    mapping[field] = column
        if "title" in mapping and "assignee" in mapping:
            return row_index, mapping
    return None


def _proposal(*, title: str, detail: str, assignee: str, due_raw: str, status: str, match_kind: str, source: str, row_number: int, external_key: str, timezone_name: str, force_confirmation: bool = False) -> dict:
    due_at, all_day, date_ambiguous = parse_due(due_raw, timezone_name)
    clarification: list[str] = []
    if match_kind == "possible":
        clarification.append(f"Dòng {row_number} ghi “{assignee}”, gần với tên hồ sơ của bạn. Bạn xác nhận đây là việc của mình nhé.")
    if date_ambiguous and due_at is not None:
        clarification.append(f"Dòng {row_number}: mốc '{due_raw}' không rõ năm, hãy xác nhận lại trước khi thêm task.")
    if force_confirmation:
        clarification.append("Nội dung được nhận diện từ DOCX chưa có cấu trúc chuẩn; bạn xác nhận đây là việc của mình nhé.")
    return {
        "row_number": row_number,
        "external_key": external_key,
        "title": title[:500],
        "detail": detail[:2000],
        "assignee": assignee or None,
        "due_at": due_at,
        "all_day": all_day,
        "date_ambiguous": date_ambiguous and due_at is not None,
        "status": status or None,
        "matched_user": match_kind in {"exact", "close"},
        "match_kind": match_kind,
        "needs_confirmation": bool(clarification),
        "clarification_question": " ".join(clarification) or None,
        "source": source,
        "source_url": "",
    }


def _extract_generic_table(table, *, filename: str, table_index: int, display_name: str, timezone_name: str) -> list[dict]:
    detected = _generic_header_map(table)
    if detected is None:
        return []
    header_row, mapping = detected
    proposals: list[dict] = []
    for row_number, row in enumerate(table.rows[header_row + 1 :], start=header_row + 2):
        def value(field: str) -> str:
            column = mapping.get(field)
            return _cell_text(row.cells[column]) if column is not None and column < len(row.cells) else ""

        title, assignee = value("title"), value("assignee")
        match_kind = name_match_kind(assignee, display_name)
        if not title or match_kind == "none":
            continue
        status = value("status")
        proposals.append(
            _proposal(
                title=title,
                detail=f"Trạng thái/Kết quả: {status}" if status else "",
                assignee=assignee,
                due_raw=value("due"),
                status=status,
                match_kind=match_kind,
                source=f"DOCX · {filename} · Bảng {table_index + 1}",
                row_number=row_number,
                external_key=f"{filename}:table-{table_index + 1}-row-{row_number}",
                timezone_name=timezone_name,
            )
        )
    return proposals


def _day_column(table) -> int | None:
    scores = [0] * len(table.columns)
    for row in table.rows[1:]:
        for index, cell in enumerate(row.cells):
            if _DAY_DATE_PATTERN.search(_cell_text(cell)) or _WEEKDAY_PATTERN.search(_cell_text(cell)):
                scores[index] += 1
    if not scores or max(scores) == 0:
        return None
    return scores.index(max(scores))


def _extract_schedule_table(table, *, filename: str, table_index: int, display_name: str, timezone_name: str) -> list[dict]:
    day_column = _day_column(table)
    if day_column is None or len(table.rows) < 2:
        return []
    headers = table.rows[0].cells
    session_columns = [index for index in range(len(headers)) if index != day_column]
    current_day = current_date = ""
    proposals: list[dict] = []
    for row_number, row in enumerate(table.rows[1:], start=2):
        day_text = _cell_text(row.cells[day_column]) if day_column < len(row.cells) else ""
        date_match = _DAY_DATE_PATTERN.search(day_text)
        if date_match:
            current_date = date_match.group(1)
        clean_day = _DAY_DATE_PATTERN.sub("", day_text).strip(" ,/-")
        if clean_day:
            current_day = clean_day
        for column in session_columns:
            if column >= len(row.cells):
                continue
            session = _cell_text(headers[column]) or f"Cột {column + 1}"
            for block in _group_blocks(_lines(row.cells[column])):
                parsed = _parse_block(block)
                title = str(parsed["content"] or "")
                if not title:
                    continue
                assignee, match_kind = _best_match(
                    [str(value) for value in (parsed["assignee"], parsed["participants"]) if value],
                    display_name,
                )
                inferred_from_block = False
                if match_kind == "none":
                    # Lịch thực tế thường để người phụ trách ở dòng riêng hoặc trong
                    # ô gộp, không có nhãn "Thành phần" mà parser có thể nhận diện.
                    assignee, match_kind = _best_match(block, display_name)
                    inferred_from_block = match_kind != "none"
                if match_kind == "none":
                    continue
                detail_parts = [f"Lịch: {current_day}" if current_day else "", f"Buổi: {session}"]
                if parsed["time"]:
                    detail_parts.append(f"Giờ: {parsed['time']}")
                if parsed["participants"]:
                    detail_parts.append(f"Thành phần: {parsed['participants']}")
                if parsed["location"]:
                    detail_parts.append(f"Địa điểm: {parsed['location']}")
                proposals.append(
                    _proposal(
                        title=title,
                        detail="\n".join(part for part in detail_parts if part),
                        assignee=assignee,
                        due_raw=current_date,
                        status="",
                        match_kind=match_kind,
                        source=f"DOCX · {filename} · Bảng {table_index + 1} · {session}",
                        row_number=row_number,
                        external_key=f"{filename}:table-{table_index + 1}-row-{row_number}-col-{column + 1}",
                        timezone_name=timezone_name,
                        force_confirmation=inferred_from_block,
                    )
                )
    return proposals


def extract_docx_task_proposals(content: bytes, *, filename: str, display_name: str, timezone_name: str) -> list[dict]:
    """Trích task từ bảng DOCX; không dùng đoạn văn tự do để tránh suy đoán."""
    if not content:
        raise DocxExtractionError("Tệp DOCX đang trống.")
    try:
        assert_uncompressed_size_ok(content, DOCX_MIME_TYPE, _MAX_UNCOMPRESSED_DOCX_BYTES)
        document = Document(BytesIO(content))
    except (AttachmentRejectedError, BadZipFile, KeyError, OSError, PackageNotFoundError, ValueError) as exc:
        raise DocxExtractionError("Không thể đọc tệp DOCX an toàn.") from exc
    proposals: list[dict] = []
    for table_index, table in enumerate(document.tables):
        generic = _extract_generic_table(
            table,
            filename=filename,
            table_index=table_index,
            display_name=display_name,
            timezone_name=timezone_name,
        )
        proposals.extend(generic or _extract_schedule_table(
            table,
            filename=filename,
            table_index=table_index,
            display_name=display_name,
            timezone_name=timezone_name,
        ))
    if not proposals:
        for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
            for line in paragraph.text.splitlines():
                task_text = line.strip()
                if not full_name_mentioned(task_text, display_name):
                    continue
                proposals.append(
                    _proposal(
                        title=task_text,
                        detail="Đoạn văn tự do chứa tên đầy đủ; cần xác nhận trước khi tạo task.",
                        assignee=display_name,
                        due_raw="",
                        status="",
                        match_kind="possible",
                        source=f"DOCX · {filename} · Đoạn {paragraph_index}",
                        row_number=paragraph_index,
                        external_key=f"{filename}:paragraph-{paragraph_index}",
                        timezone_name=timezone_name,
                        force_confirmation=True,
                    )
                )
    return proposals


def collect_docx_assignee_candidates(content: bytes) -> list[str]:
    """Lấy các tên/đầu mối trong bảng DOCX, không suy ra task cho người dùng."""
    if not content:
        raise DocxExtractionError("Tệp DOCX đang trống.")
    try:
        assert_uncompressed_size_ok(content, DOCX_MIME_TYPE, _MAX_UNCOMPRESSED_DOCX_BYTES)
        document = Document(BytesIO(content))
    except (AttachmentRejectedError, BadZipFile, KeyError, OSError, PackageNotFoundError, ValueError) as exc:
        raise DocxExtractionError("Không thể đọc tệp DOCX an toàn.") from exc
    names: list[str] = []
    for table in document.tables:
        generic = _generic_header_map(table)
        if generic is not None:
            header_row, mapping = generic
            assignee_col = mapping["assignee"]
            for row in table.rows[header_row + 1 :]:
                value = _cell_text(row.cells[assignee_col]) if assignee_col < len(row.cells) else ""
                if value and value not in names:
                    names.append(value[:120])
            continue
        day_column = _day_column(table)
        if day_column is None:
            continue
        for row in table.rows[1:]:
            for column, cell in enumerate(row.cells):
                if column == day_column:
                    continue
                for block in _group_blocks(_lines(cell)):
                    parsed = _parse_block(block)
                    # “Thành phần” trong lịch thường là phòng/ban hoặc một danh
                    # sách hỗn hợp. Chỉ gợi ý người chủ trì đã nhận diện được ở
                    # đầu mục lịch để người dùng không chọn nhầm tên đơn vị.
                    value = parsed["assignee"]
                    if value and str(value) not in names:
                        names.append(str(value)[:120])
                        if len(names) >= 20:
                            return names
    return names
