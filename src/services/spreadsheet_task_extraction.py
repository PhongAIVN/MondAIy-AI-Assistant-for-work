"""Đọc bảng công việc từ Excel theo cấu trúc linh hoạt, không tự ghi dữ liệu.

Nội dung trong bảng là dữ liệu không tin cậy. Module này chỉ chuẩn hoá và trả
đề xuất để API/UI yêu cầu người dùng xác nhận trước khi tạo task.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from datetime import UTC, date, datetime, time
from difflib import SequenceMatcher
from io import BytesIO
from zoneinfo import ZoneInfo

import openpyxl
from dateutil import parser as date_parser

MAX_XLSX_BYTES = 200 * 1024
_MAX_UNCOMPRESSED_XLSX_BYTES = 5 * 1024 * 1024
_MAX_WORKSHEET_ROWS = 2_000
_MAX_WORKSHEET_COLUMNS = 100
_HEADER_SCAN_ROWS = 40
_MAX_HEADER_CELL_CHARS = 160
_YEAR_TOKEN = re.compile(r"\b\d{4}\b")
_RACI_TOKENS = {"r", "a", "c", "i", "ra", "ar", "ri", "ci", "ai"}
_HONORIFICS = {"a", "anh", "chi", "ong", "ba", "dc", "dong chi"}
_HEADER_ALIASES = {
    "stt": ("stt", "so tt", "no", "#"),
    "title": (
        "ten cong viec", "noi dung cong viec", "noi dung", "cong viec", "hang muc", "dau viec",
        "task", "task name", "description", "mo ta", "title", "name",
    ),
    "assignee": (
        "lanh dao chi dao", "lanh dao phu trach", "nguoi phu trach", "nguoi chiu trach nhiem",
        "nguoi chi dao", "chu tri", "phu trach", "chi dao", "owner", "pic", "assignee",
        "responsible", "responsible person",
    ),
    "due": (
        "tien do", "han hoan thanh", "ngay hoan thanh", "thoi gian", "deadline", "due date",
        "han chot", "ngay ket thuc", "end date", "due", "han",
    ),
    "status": ("ket qua", "trien khai", "ghi chu", "note", "status", "tinh trang", "trang thai", "state"),
    "detail": ("mo ta chi tiet", "chi tiet", "notes", "ghi chu", "ket qua", "trien khai"),
    "key": ("ma viec", "task id", "task key", "id", "code"),
}


class SpreadsheetExtractionError(ValueError):
    """Lỗi có thể hiển thị khi tệp bảng không an toàn hoặc không đọc được."""


def normalize_text(value: object) -> str:
    """Bỏ dấu và chuẩn hoá khoảng trắng để so khớp tên/cột nhất quán."""
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def parse_due(value: str, timezone_name: str) -> tuple[datetime | None, bool, bool]:
    """Trả về hạn UTC, cờ cả ngày và cờ thiếu năm cần người dùng xác nhận."""
    if not value:
        return None, False, False
    try:
        parsed = date_parser.parse(value, dayfirst=True, fuzzy=False)
    except (TypeError, ValueError, OverflowError):
        return None, True, False
    all_day = not any(token in value.lower() for token in (":", "am", "pm", "giờ", "h"))
    date_ambiguous = not bool(_YEAR_TOKEN.search(value))
    timezone = ZoneInfo(timezone_name)
    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime.combine(parsed, time.min)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    else:
        parsed = parsed.astimezone(timezone)
    return parsed.astimezone(UTC), all_day, date_ambiguous


def _name_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(value))
    return [token for token in tokens if token not in _HONORIFICS]


def name_match_kind(assignee: str, display_name: str) -> str:
    """Phân loại khớp tên: exact, close, possible hoặc none.

    ``possible`` chỉ được dùng cho tên gọi một từ đủ dài ở cuối tên người dùng;
    caller luôn phải yêu cầu xác nhận. Điều này nhận diện ``A. Đức`` nhưng không
    tự gán nhầm những tên ngắn như ``An`` vào ``Nguyễn Văn Anh``.
    """
    left = normalize_text(assignee)
    right = normalize_text(display_name)
    if not left or not right:
        return "none"
    if left == right:
        return "exact"
    left_tokens, right_tokens = _name_tokens(assignee), _name_tokens(display_name)
    if not left_tokens or not right_tokens:
        return "none"
    left_set, right_set = set(left_tokens), set(right_tokens)
    smaller, larger = (left_set, right_set) if len(left_set) <= len(right_set) else (right_set, left_set)
    if len(smaller) >= 2 and smaller.issubset(larger):
        return "close"
    # Lỗi gõ nhẹ trên tên đầy đủ vẫn cần ít nhất hai token trùng hoặc độ giống
    # cao; tuyệt đối không dùng sequence matcher cho một token đơn.
    if len(left_set) >= 2 and len(right_set) >= 2 and len(left_set & right_set) >= 2:
        ratio = SequenceMatcher(None, " ".join(sorted(left_set)), " ".join(sorted(right_set))).ratio()
        if ratio >= 0.72:
            return "close"
    if len(left_tokens) == 1 and left_tokens[0] == right_tokens[-1] and len(left_tokens[0]) >= 3:
        return "possible"
    return "none"


def name_matches(assignee: str, display_name: str) -> bool:
    """Tương thích connector cũ: chỉ true với khớp đủ tin cậy."""
    return name_match_kind(assignee, display_name) in {"exact", "close"}


def full_name_mentioned(text: str, display_name: str) -> bool:
    """Fallback chỉ chấp nhận đầy đủ ít nhất hai token, không dùng alias ngắn."""
    target = normalize_text(display_name)
    return len(_name_tokens(display_name)) >= 2 and bool(target) and target in normalize_text(text)


def _safe_workbook(content: bytes):
    if not content:
        raise SpreadsheetExtractionError("Tệp Excel đang trống.")
    if len(content) > MAX_XLSX_BYTES:
        raise SpreadsheetExtractionError("Tệp Excel vượt quá giới hạn 200 KB.")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            uncompressed_size = sum(info.file_size for info in archive.infolist())
            if uncompressed_size > _MAX_UNCOMPRESSED_XLSX_BYTES:
                raise SpreadsheetExtractionError("Tệp Excel giải nén vượt quá giới hạn an toàn.")
    except zipfile.BadZipFile as exc:
        raise SpreadsheetExtractionError("Tệp tải lên không phải Excel .xlsx hợp lệ.") from exc
    try:
        return openpyxl.load_workbook(BytesIO(content), read_only=False, data_only=True, keep_links=False)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise SpreadsheetExtractionError("Không thể đọc tệp Excel này.") from exc


def _merged_values(ws) -> dict[tuple[int, int], object]:
    values: dict[tuple[int, int], object] = {}
    for merged_range in ws.merged_cells.ranges:
        anchor = ws.cell(merged_range.min_row, merged_range.min_col).value
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for col in range(merged_range.min_col, merged_range.max_col + 1):
                values[(row, col)] = anchor
    return values


def _cell_text(ws, merged: dict[tuple[int, int], object], row: int, col: int) -> str:
    value = merged.get((row, col), ws.cell(row, col).value)
    return str(value).strip() if value is not None else ""


def _header_matches(field: str, header: str) -> bool:
    """Chỉ coi nhãn ngắn là header, không suy diễn từ nội dung công việc."""
    aliases = _HEADER_ALIASES[field]
    if field == "stt":
        return header in aliases
    return any(alias in header for alias in aliases)


def _header_mapping(ws, merged: dict[tuple[int, int], object]) -> tuple[int, dict[str, int], dict[int, str]] | None:
    best: tuple[int, int, dict[str, int], dict[int, str]] | None = None
    max_row = min(ws.max_row, _HEADER_SCAN_ROWS)
    max_col = min(ws.max_column, _MAX_WORKSHEET_COLUMNS)
    for row in range(1, max_row + 1):
        mapping: dict[str, int] = {}
        headers: dict[int, str] = {}
        for col in range(1, max_col + 1):
            header = _cell_text(ws, merged, row, col)
            if not header:
                continue
            if len(header) > _MAX_HEADER_CELL_CHARS:
                # Một dòng mô tả dài có thể chứa các từ như “nội dung”,
                # “phụ trách”, nhưng không phải header của bảng.
                mapping = {}
                break
            headers[col] = header
            normalized = normalize_text(header)
            for field, aliases in _HEADER_ALIASES.items():
                if field not in mapping and _header_matches(field, normalized):
                    mapping[field] = col
        if "title" not in mapping or "assignee" not in mapping:
            continue
        score = len(mapping) + (5 if "stt" in mapping else 0)
        if best is None or score > best[0]:
            best = (score, row, mapping, headers)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _has_unassigned_task_table(ws, merged: dict[tuple[int, int], object]) -> bool:
    """Nhận biết bảng công việc có header nhưng không có cột người phụ trách."""
    max_row = min(ws.max_row, _HEADER_SCAN_ROWS)
    max_col = min(ws.max_column, _MAX_WORKSHEET_COLUMNS)
    for row in range(1, max_row + 1):
        fields: set[str] = set()
        for col in range(1, max_col + 1):
            value = _cell_text(ws, merged, row, col)
            if not value or len(value) > _MAX_HEADER_CELL_CHARS:
                continue
            normalized = normalize_text(value)
            for field in _HEADER_ALIASES:
                if _header_matches(field, normalized):
                    fields.add(field)
        if "stt" in fields and "title" in fields and "assignee" not in fields:
            return True
    return False


def _raci_columns(ws, merged: dict[tuple[int, int], object], header_row: int, excluded: set[int], headers: dict[int, str]) -> dict[int, str]:
    detected: dict[int, str] = {}
    last_row = min(ws.max_row, header_row + 40)
    for col, header in headers.items():
        if col in excluded:
            continue
        total = matched = 0
        for row in range(header_row + 1, last_row + 1):
            value = _cell_text(ws, merged, row, col)
            if not value:
                continue
            total += 1
            tokens = [token for token in re.split(r"[\/,;+&\s]+", value.lower()) if token]
            if tokens and all(token in _RACI_TOKENS for token in tokens):
                matched += 1
        if total >= 2 and matched / total >= 0.7:
            detected[col] = header
    return detected


def _raci_detail(ws, merged: dict[tuple[int, int], object], row: int, columns: dict[int, str]) -> str:
    accountable: list[str] = []
    responsible: list[str] = []
    other: list[str] = []
    for col, department in columns.items():
        code = _cell_text(ws, merged, row, col).upper()
        if not code:
            continue
        entry = f"{department} ({code})"
        if "A" in code:
            accountable.append(entry)
        elif "R" in code:
            responsible.append(entry)
        else:
            other.append(entry)
    lines = []
    if accountable:
        lines.append("Liên hệ chính (A): " + ", ".join(accountable))
    if responsible:
        lines.append("Phối hợp (R): " + ", ".join(responsible))
    if other:
        lines.append("Tham vấn/thông báo (C/I): " + ", ".join(other))
    return "\n".join(lines)


def extract_excel_task_proposals(content: bytes, *, filename: str, display_name: str, timezone_name: str) -> list[dict]:
    """Lấy các dòng task liên quan đến user từ mọi sheet của một tệp Excel."""
    workbook = _safe_workbook(content)
    proposals: list[dict] = []
    try:
        for ws in workbook.worksheets:
            if ws.max_row > _MAX_WORKSHEET_ROWS or ws.max_column > _MAX_WORKSHEET_COLUMNS:
                continue
            sheet_proposal_start = len(proposals)
            merged = _merged_values(ws)
            detected = _header_mapping(ws, merged)
            if detected is None:
                if _has_unassigned_task_table(ws, merged):
                    # Có bảng công việc rõ ràng nhưng không chỉ ra người phụ
                    # trách: không dùng chính nội dung task làm “tên” fallback.
                    continue
                for row in range(1, ws.max_row + 1):
                    text = " | ".join(_cell_text(ws, merged, row, col) for col in range(1, ws.max_column + 1) if _cell_text(ws, merged, row, col))
                    if not full_name_mentioned(text, display_name):
                        continue
                    proposals.append(
                        {
                            "row_number": row,
                            "external_key": f"{filename}:{ws.title}-row-{row}",
                            "title": text[:500],
                            "detail": "Dòng được nhận diện theo tên đầy đủ trong bảng chưa có cấu trúc chuẩn.",
                            "assignee": display_name,
                            "due_at": None,
                            "all_day": False,
                            "date_ambiguous": False,
                            "status": None,
                            "matched_user": False,
                            "match_kind": "possible",
                            "needs_confirmation": True,
                            "clarification_question": "Bảng chưa có cột công việc/người phụ trách rõ ràng. Bạn xác nhận dòng này là việc của mình nhé.",
                            "source": f"Excel · {filename} · {ws.title}",
                            "source_url": "",
                        }
                    )
                continue
            header_row, mapping, headers = detected
            raci_columns = _raci_columns(ws, merged, header_row, set(mapping.values()), headers)
            for row in range(header_row + 1, ws.max_row + 1):
                title = _cell_text(ws, merged, row, mapping["title"])
                assignee = _cell_text(ws, merged, row, mapping["assignee"])
                if not title or title.startswith(("[", "=")):
                    continue
                match_kind = name_match_kind(assignee, display_name)
                if match_kind == "none":
                    continue
                raw_due = _cell_text(ws, merged, row, mapping.get("due", 0)) if mapping.get("due") else ""
                due_at, all_day, date_ambiguous = parse_due(raw_due, timezone_name)
                parts = []
                detail = _cell_text(ws, merged, row, mapping.get("detail", 0)) if mapping.get("detail") else ""
                status = _cell_text(ws, merged, row, mapping.get("status", 0)) if mapping.get("status") else ""
                if detail:
                    parts.append(detail)
                if status and status != detail:
                    parts.append(f"Trạng thái/Kết quả: {status}")
                raci = _raci_detail(ws, merged, row, raci_columns)
                if raci:
                    parts.append(raci)
                clarification = []
                if match_kind == "possible":
                    clarification.append(f"Dòng {row} ghi “{assignee}”, gần với tên hồ sơ của bạn. Bạn xác nhận đây là việc của mình nhé.")
                if date_ambiguous and due_at is not None:
                    clarification.append(f"Dòng {row}: hạn '{raw_due}' không rõ năm, hãy xác nhận lại trước khi thêm task.")
                key = _cell_text(ws, merged, row, mapping.get("key", 0)) if mapping.get("key") else ""
                proposals.append(
                    {
                        "row_number": row,
                        "external_key": key or f"{filename}:{ws.title}-row-{row}",
                        "title": title[:500],
                        "detail": "\n".join(parts)[:2000],
                        "assignee": assignee or None,
                        "due_at": due_at,
                        "all_day": all_day,
                        "date_ambiguous": date_ambiguous and due_at is not None,
                        "status": status or None,
                        "matched_user": match_kind in {"exact", "close"},
                        "match_kind": match_kind,
                        "needs_confirmation": bool(clarification),
                        "clarification_question": " ".join(clarification) or None,
                        "source": f"Excel · {filename} · {ws.title}",
                        "source_url": "",
                    }
                )
            # Một bảng có header nhưng không nhận được cột người phụ trách
            # đáng tin vẫn có thể chứa tên đầy đủ trong chính dòng task. Chỉ
            # đưa ra proposal xác nhận, không tự coi đây là assignee.
            if len(proposals) == sheet_proposal_start:
                for row in range(header_row + 1, ws.max_row + 1):
                    text = " | ".join(_cell_text(ws, merged, row, col) for col in range(1, ws.max_column + 1) if _cell_text(ws, merged, row, col))
                    if not full_name_mentioned(text, display_name):
                        continue
                    proposals.append(
                        {
                            "row_number": row,
                            "external_key": f"{filename}:{ws.title}-fallback-row-{row}",
                            "title": _cell_text(ws, merged, row, mapping["title"])[:500] or text[:500],
                            "detail": "Dòng được nhận diện theo tên đầy đủ; cần xác nhận người phụ trách.\n" + text[:1500],
                            "assignee": display_name,
                            "due_at": None,
                            "all_day": False,
                            "date_ambiguous": False,
                            "status": None,
                            "matched_user": False,
                            "match_kind": "possible",
                            "needs_confirmation": True,
                            "clarification_question": "Tên xuất hiện trong dòng nhưng cột phụ trách không khớp rõ ràng. Bạn xác nhận đây là việc của mình nhé.",
                            "source": f"Excel · {filename} · {ws.title}",
                            "source_url": "",
                        }
                    )
    finally:
        workbook.close()
    return proposals


def collect_excel_assignee_candidates(content: bytes) -> list[str]:
    """Liệt kê tên ở cột phụ trách để hỏi lại user khi chưa lọc được task."""
    workbook = _safe_workbook(content)
    names: list[str] = []
    try:
        for ws in workbook.worksheets:
            if ws.max_row > _MAX_WORKSHEET_ROWS or ws.max_column > _MAX_WORKSHEET_COLUMNS:
                continue
            merged = _merged_values(ws)
            detected = _header_mapping(ws, merged)
            if detected is None:
                continue
            header_row, mapping, _ = detected
            assignee_col = mapping.get("assignee")
            if assignee_col is None:
                continue
            for row in range(header_row + 1, ws.max_row + 1):
                value = _cell_text(ws, merged, row, assignee_col)
                if value and value not in names:
                    names.append(value[:120])
                    if len(names) >= 20:
                        return names
    finally:
        workbook.close()
    return names
