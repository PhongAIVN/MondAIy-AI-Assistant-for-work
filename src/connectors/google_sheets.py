"""Connector chỉ đọc Google Sheets cho bảng công việc của nhóm."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import ConnectorAPIError
from src.connectors.google_http import fetch_json_capped
from src.models.connection import Connection
from src.services.connections import google
from src.services.google_sheet_task_extraction import (
    GoogleSheetTaskExtractionError,
    extract_google_sheet_tasks,
    extract_google_sheet_workbook_tasks,
)
from src.services.spreadsheet_task_extraction import name_match_kind, name_matches
from src.services.spreadsheet_task_extraction import parse_due as _parse_due

API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
_SPREADSHEET_ID = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_MAX_SHEET_CANDIDATES = 20
_HEADER_ALIASES = {
    "title": ("ten cong viec", "cong viec", "task", "task name", "title", "name", "nhiem vu", "hang muc", "dau viec"),
    "assignee": (
        "nguoi phu trach",
        "nguoi chiu trach nhiem",
        "nguoi thuc hien",
        "phu trach",
        "thuc hien",
        "assignee",
        "owner",
        "responsible",
    ),
    "due": ("han chot", "deadline", "due date", "due", "ngay ket thuc", "end date", "ngay het han", "han hoan thanh"),
    "status": ("trang thai", "status", "state"),
    "detail": ("mo ta", "mo ta chi tiet", "description", "detail", "ghi chu", "notes"),
    "key": ("ma viec", "ma", "stt", "task id", "task key", "id", "code"),
}


class GoogleSheetsAPIError(ConnectorAPIError):
    """Lỗi Google Sheets đã được làm sạch, an toàn để trả về API."""


@dataclass(frozen=True)
class SheetSnapshot:
    """Vùng dữ liệu đã cắt theo cap, kèm revision để làm khoá cache."""

    values: list[list[object]]
    truncated: bool
    revision: str


@dataclass(frozen=True)
class SheetDescriptor:
    title: str
    sheet_id: int


@dataclass(frozen=True)
class WorkbookSnapshot:
    sheets: dict[str, list[list[object]]]
    sheet_ids: dict[str, int]
    available_sheet_names: list[str]
    scanned_sheet_names: list[str]
    truncated: bool
    revision: str


def _cap_row(row: list[object], budget: int) -> tuple[list[object], int, bool]:
    """Cắt một hàng vừa đúng ngân sách ký tự còn lại.

    Trả (hàng đã cắt, số ký tự đã dùng, có cắt gì không). Ô vượt ngân sách bị
    cắt ngay giữa chuỗi chứ không được giữ nguyên: một ô duy nhất cũng có thể
    dài hơn cả ngưỡng của toàn bảng.
    """
    kept_cells: list[object] = []
    used = 0
    for cell in row:
        text = str(cell or "")
        if used + len(text) <= budget:
            kept_cells.append(cell)
            used += len(text)
            continue
        remaining = budget - used
        if remaining > 0:
            kept_cells.append(text[:remaining])
            used += remaining
        return kept_cells, used, True
    return kept_cells, used, False


def cap_values(values: list[list[object]]) -> tuple[list[list[object]], bool]:
    """Cắt bảng về trong ngưỡng cấu hình: số dòng, số cột, và tổng số ký tự.

    Ba ngưỡng chứ không một: một bảng 100 dòng nhưng mỗi ô là một đoạn văn vẫn
    đốt token như bảng 10.000 dòng. Cắt từ cuối lên nên phần đầu bảng — nơi
    người dùng để việc quan trọng — luôn được giữ.

    Ngân sách ký tự là ngưỡng CỨNG: tổng số ký tự giữ lại không bao giờ vượt
    `google_document_max_chars`, kể cả khi ngay hàng đầu tiên (hoặc một ô đơn
    lẻ trong nó) đã dài hơn cả ngưỡng. Bản trước giữ nguyên hàng đầu tiên và
    báo truncated=False — tức là chỉ cần dồn hết nội dung vào một hàng là lách
    được cap.
    """
    settings = get_settings()
    max_rows = settings.google_sheet_max_rows
    max_columns = settings.google_sheet_max_columns
    max_chars = settings.google_document_max_chars

    truncated = len(values) > max_rows
    capped = [row[:max_columns] for row in values[:max_rows]]
    truncated = truncated or any(len(row) > max_columns for row in values[:max_rows])

    total = 0
    kept: list[list[object]] = []
    for row in capped:
        capped_row, used, row_truncated = _cap_row(row, max_chars - total)
        truncated = truncated or row_truncated
        if not capped_row and row:
            # Hàng có dữ liệu nhưng không giữ được ô nào: ngân sách đã hết.
            truncated = True
            break
        total += used
        kept.append(capped_row)
        if row_truncated:
            break
    return kept, truncated


def cap_workbook_values(
    sheets: list[tuple[SheetDescriptor, list[list[object]]]],
) -> tuple[dict[str, list[list[object]]], bool]:
    """Distribute the document-wide row/character budget fairly across tabs."""
    settings = get_settings()
    max_rows = settings.google_sheet_max_rows
    max_columns = settings.google_sheet_max_columns
    max_chars = settings.google_document_max_chars

    prepared: list[tuple[SheetDescriptor, list[list[object]]]] = []
    truncated = False
    for descriptor, values in sheets:
        rows = [row[:max_columns] for row in values[:max_rows]]
        truncated = truncated or len(values) > max_rows
        truncated = truncated or any(
            len(row) > max_columns for row in values[:max_rows]
        )
        prepared.append((descriptor, rows))

    kept = {descriptor.title: [] for descriptor, _ in prepared}
    positions = [0] * len(prepared)
    total_rows = 0
    total_chars = 0
    while total_rows < max_rows and total_chars < max_chars:
        progressed = False
        for index, (descriptor, rows) in enumerate(prepared):
            if positions[index] >= len(rows):
                continue
            progressed = True
            row = rows[positions[index]]
            positions[index] += 1
            capped_row, used, row_truncated = _cap_row(
                row, max_chars - total_chars
            )
            if capped_row or not row:
                kept[descriptor.title].append(capped_row)
                total_rows += 1
                total_chars += used
            truncated = truncated or row_truncated
            if row_truncated or total_rows >= max_rows or total_chars >= max_chars:
                break
        if not progressed:
            break

    if any(position < len(rows) for position, (_, rows) in zip(positions, prepared)):
        truncated = True
    return kept, truncated


def _column_letter(index: int) -> str:
    """Số thứ tự cột (1-based) -> nhãn cột A1 (1 -> A, 27 -> AA)."""
    if index < 1:
        raise ValueError("Chỉ số cột phải bắt đầu từ 1.")
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def bounded_range(sheet_name: str) -> str:
    """Vùng A1 có biên để Google chỉ trả về phần ta thật sự dùng.

    Xin dư đúng 1 dòng và 1 cột so với ngưỡng: đủ để biết bảng có bị cắt hay
    không (`cap_values` thấy thừa thì bật truncated), nhưng không kéo về cả
    bảng 100.000 dòng chỉ để rồi vứt đi.

    Nháy đơn trong tên tab phải nhân đôi theo cú pháp A1, nếu không một tab tên
    `Tuần 'A'` sẽ làm hỏng cả biểu thức range.
    """
    settings = get_settings()
    escaped = sheet_name.replace("'", "''")
    last_column = _column_letter(settings.google_sheet_max_columns + 1)
    last_row = settings.google_sheet_max_rows + 1
    return f"'{escaped}'!A1:{last_column}{last_row}"


def _revision_of(values: list[list[object]]) -> str:
    """Định danh revision của bảng.

    Sheets values API không trả revisionId/modifiedTime nào cả, nên băm chính
    nội dung: nội dung không đổi thì khoá cache không đổi, đổi một ô là khoá
    khác — đúng ngữ nghĩa cần cho cache, không cần thêm quyền Drive.
    """
    raw = json.dumps(values, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _workbook_revision_of(
    sheets: dict[str, list[list[object]]],
    sheet_ids: dict[str, int],
) -> str:
    raw = json.dumps(
        {
            name: {"sheet_id": sheet_ids[name], "values": values}
            for name, values in sheets.items()
        },
        ensure_ascii=False,
        default=str,
    )
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_spreadsheet_id(value: str) -> str:
    """Nhận URL Google Sheets hoặc ID, không chấp nhận URL ngoài Google Sheets."""
    candidate = value.strip()
    match = _SPREADSHEET_ID.search(candidate)
    if match:
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or parsed.hostname != "docs.google.com":
            raise ValueError("spreadsheetUrl phải trỏ tới docs.google.com.")
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,200}", candidate):
        return candidate
    raise ValueError("spreadsheetUrl phải là URL Google Sheets hoặc spreadsheet ID hợp lệ.")


def _normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def _contains_phrase(header: str, alias: str) -> bool:
    """Alias phải xuất hiện như một DÃY TỪ, không phải chuỗi con bất kỳ.

    Khớp chuỗi con làm "name" dính vào "filename" và "id" dính vào "identity",
    ánh xạ nhầm sang cột không liên quan rồi đọc ra bảng rác — tệ hơn là báo
    không đọc được. Cắt theo từ thì "han chot (dd/mm)" vẫn nhận, còn "filename" thì không.
    """
    header_tokens = re.findall(r"[a-z0-9]+", header)
    alias_tokens = re.findall(r"[a-z0-9]+", alias)
    if not alias_tokens or not header_tokens:
        return False
    span = len(alias_tokens)
    matched = any(
        header_tokens[start : start + span] == alias_tokens
        for start in range(len(header_tokens) - span + 1)
    )
    if not matched:
        return False
    # Alias phải chiếm phần lớn ô, nếu không một Ô DỮ LIỆU cũng bị nhận là tiêu đề:
    # "Demo nhận diện task đa định dạng" chứa "task" nhưng là tên một công việc,
    # không phải tên cột. Đo trên dữ liệu thật đã bắt đúng ca này.
    # "Hạn chót (dd/mm)" = 2/4 và "Người thực hiện chính" = 3/4 vẫn qua.
    return span * 2 >= len(header_tokens)


def _match_exact(normalized: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for index, header in enumerate(normalized):
            if header in aliases:
                mapping[field] = index
                break
    return mapping


def _match_loose(normalized: list[str]) -> dict[str, int]:
    """Khớp mềm: tiêu đề CHỨA alias thay vì bằng đúng alias.

    Sheet thật hiếm khi ghi đúng "han chot" — người ta viết "Hạn chót (dd/mm)",
    "Deadline dự kiến", "Người thực hiện chính". Khớp bằng dấu bằng làm trượt hết
    những cái đó rồi báo "không tìm thấy hàng tiêu đề", trong khi bảng hoàn toàn đọc được.

    Alias ngắn dễ dính bậy (`id` nằm trong `identity`, `name` nằm trong `filename`)
    nên alias dưới 4 ký tự vẫn phải khớp tuyệt đối.
    """
    mapping: dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for index, header in enumerate(normalized):
            if not header:
                continue
            if any(_contains_phrase(header, alias) for alias in aliases):
                mapping[field] = index
                break
    return mapping


def _header_candidates(values: list[list[object]]) -> list[tuple[int, dict[str, int]]]:
    """Mọi hàng có thể là tiêu đề, theo thứ tự ưu tiên khớp chính xác trước."""
    found: list[tuple[int, dict[str, int]]] = []
    for matcher in (_match_exact, _match_loose):
        for row_index, row in enumerate(values[:40]):
            mapping = matcher([_normalize_header(cell) for cell in row])
            if "title" in mapping and ("assignee" in mapping or "due" in mapping):
                found.append((row_index, mapping))
        if found:
            return found
    # Không phải bảng nào cũng gọi cột nội dung là "Task" hay "Tên công việc".
    # Khi một hàng đã có ít nhất hai cột metadata nhận diện được và chỉ còn đúng
    # một cột có dữ liệu, cấu trúc của bảng đủ mạnh để suy ra đó là title. Cổng
    # này không dựa vào literal của ô lạ và không nhận một hàng dữ liệu thường.
    for row_index, row in enumerate(values[:40]):
        normalized = [_normalize_header(cell) for cell in row]
        mapping = {
            field: index
            for field, index in _match_loose(normalized).items()
            if field != "title"
        }
        if len(set(mapping.values())) < 2:
            continue
        claimed = set(mapping.values())
        unclaimed = [
            index
            for index, cell in enumerate(row)
            if index not in claimed and str(cell or "").strip()
        ]
        if len(unclaimed) != 1:
            continue
        title_index = unclaimed[0]
        data_rows = values[row_index + 1 : row_index + 12]
        title_has_data = any(
            title_index < len(data_row) and str(data_row[title_index] or "").strip()
            for data_row in data_rows
        )
        metadata_has_data = any(
            any(index < len(data_row) and str(data_row[index] or "").strip() for index in claimed)
            for data_row in data_rows
        )
        if title_has_data and metadata_has_data:
            found.append((row_index, {**mapping, "title": title_index}))
    if found:
        return found
    # Bậc cuối trước khi phải nhờ LLM: chỉ có cột tên việc cũng đã đọc được bảng,
    # ép buộc phải có thêm assignee/due là tự loại bỏ những sheet chỉ liệt kê việc.
    for row_index, row in enumerate(values[:40]):
        mapping = _match_loose([_normalize_header(cell) for cell in row])
        if "title" in mapping:
            found.append((row_index, mapping))
    return found


_LLM_HEADER_PROMPT = """Bạn đọc một bảng Google Sheet và chỉ ra ĐÂU là hàng tiêu đề của bảng công việc.

Trả về DUY NHẤT một JSON, không giải thích, không markdown:
{"header_row": <chỉ số hàng, đếm từ 0>, "columns": {"title": <chỉ số cột>, "assignee": <chỉ số cột hoặc null>, "due": <...>, "status": <...>, "detail": <...>, "key": <...>}}

Quy tắc:
- "title" là cột chứa TÊN CÔNG VIỆC. Bắt buộc phải có; không xác định được thì trả {"header_row": null}.
- Cột không tồn tại thì để null. Đừng bịa cột.
- Bảng có thể có vài dòng tiêu đề trang trí phía trên; hàng tiêu đề là hàng có tên cột, không phải tên bảng.
- Chỉ số cột đếm từ 0, theo đúng thứ tự ô trong hàng.

Dữ liệu (mỗi dòng là một hàng, dạng JSON):
"""


def _preview_for_llm(values: list[list[object]], rows: int = 15, cell_len: int = 60) -> str:
    lines = []
    for index, row in enumerate(values[:rows]):
        cells = [str(cell or "")[:cell_len] for cell in row[:20]]
        lines.append(f"{index}: {json.dumps(cells, ensure_ascii=False)}")
    return "\n".join(lines)


def _validate_llm_header(
    values: list[list[object]], header_row: object, columns: object
) -> tuple[int, dict[str, int]] | None:
    """Không tin LLM: mọi chỉ số phải nằm trong bảng thật và cột title phải có dữ liệu."""
    if not isinstance(header_row, int) or not 0 <= header_row < min(len(values), 40):
        return None
    if not isinstance(columns, dict):
        return None
    width = max((len(row) for row in values[: header_row + 20]), default=0)
    mapping: dict[str, int] = {}
    for field in _HEADER_ALIASES:
        index = columns.get(field)
        if isinstance(index, int) and 0 <= index < width:
            mapping[field] = index
    if "title" not in mapping:
        return None
    title_column = mapping["title"]
    has_data = any(
        len(row) > title_column and str(row[title_column] or "").strip()
        for row in values[header_row + 1 : header_row + 20]
    )
    return (header_row, mapping) if has_data else None


async def find_header_with_llm(values: list[list[object]]) -> tuple[int, dict[str, int]]:
    """Nhờ LLM đọc hàng tiêu đề khi bảng alias không phủ được format.

    Chỉ chạy sau khi cả khớp chính xác lẫn khớp mềm đã trượt, nên không làm chậm
    những sheet vốn đọc được và không tốn quota cho việc quy tắc tự làm nổi.
    Kết quả của LLM luôn phải qua `_validate_llm_header` trước khi dùng.
    """
    from langchain_core.messages import HumanMessage

    from src.services.llm import get_llm

    llm = get_llm("extract")
    response = await llm.ainvoke(
        [HumanMessage(content=_LLM_HEADER_PROMPT + _preview_for_llm(values))]
    )
    raw = str(getattr(response, "content", "") or "").strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError("Không tìm thấy hàng tiêu đề công việc trong Google Sheet.")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError("Không tìm thấy hàng tiêu đề công việc trong Google Sheet.") from exc

    resolved = _validate_llm_header(values, parsed.get("header_row"), parsed.get("columns"))
    if resolved is None:
        raise ValueError("Không tìm thấy hàng tiêu đề công việc trong Google Sheet.")
    return resolved


def _find_header(values: list[list[object]]) -> tuple[int, dict[str, int]]:
    candidates = _header_candidates(values)
    if candidates:
        return candidates[0]
    raise ValueError("Không tìm thấy hàng tiêu đề công việc trong Google Sheet.")


def _cell(row: list[object], mapping: dict[str, int], key: str) -> str:
    index = mapping.get(key)
    if index is None or index >= len(row):
        return ""
    return str(row[index] or "").strip()


def _name_matches(assignee: str, display_name: str) -> bool:
    """Giữ API nội bộ cũ cho connector và regression tests."""
    return name_matches(assignee, display_name)


class GoogleSheetsConnector:
    """Đọc values của một spreadsheet do người dùng đã cấp quyền."""

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await google.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise GoogleSheetsAPIError(f"Không lấy được access token Google Sheets: {exc}") from exc

    @staticmethod
    def _range_name(sheet_name: str, *, preview: bool = False) -> str:
        settings = get_settings()
        escaped = sheet_name.strip().replace("'", "''")
        if preview:
            last_column = _column_letter(min(settings.google_sheet_max_columns, 20))
            last_row = min(settings.google_sheet_max_rows, 40)
            range_name = f"'{escaped}'!A1:{last_column}{last_row}"
        else:
            range_name = bounded_range(sheet_name)
        return quote(range_name, safe="")

    async def _get_json(self, url: str, *, params: httpx.QueryParamTypes) -> dict:
        token = await self._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            status_code, body = await fetch_json_capped(client, url, params=params, source="Google Sheets")
        if status_code != 200:
            raise GoogleSheetsAPIError(f"Google Sheets API lỗi {status_code} khi đọc bảng.")
        return body

    async def list_sheets(self, spreadsheet_id: str) -> list[SheetDescriptor]:
        body = await self._get_json(
            f"{API_BASE}/{quote(spreadsheet_id, safe='')}",
            params={"fields": "sheets.properties(sheetId,title)"},
        )
        sheets = body.get("sheets", [])
        if not isinstance(sheets, list):
            raise GoogleSheetsAPIError("Google Sheets trả về danh sách tab không hợp lệ.")
        descriptors: list[SheetDescriptor] = []
        for sheet in sheets:
            if not isinstance(sheet, dict):
                continue
            properties = sheet.get("properties", {})
            if not isinstance(properties, dict):
                continue
            name = str(properties.get("title", "")).strip()
            sheet_id = properties.get("sheetId")
            if name and isinstance(sheet_id, int):
                descriptors.append(SheetDescriptor(title=name, sheet_id=sheet_id))
        return descriptors

    async def list_sheet_names(self, spreadsheet_id: str) -> list[str]:
        return [
            descriptor.title
            for descriptor in await self.list_sheets(spreadsheet_id)
        ]

    async def read_values(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        *,
        preview: bool = False,
    ) -> list[list[object]]:
        range_name = self._range_name(sheet_name, preview=preview)
        body = await self._get_json(
            f"{API_BASE}/{quote(spreadsheet_id, safe='')}/values/{range_name}",
            params={"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"},
        )
        values = body.get("values", [])
        if not isinstance(values, list):
            raise GoogleSheetsAPIError("Google Sheets trả về dữ liệu không hợp lệ.")
        return values

    async def select_sheet(self, spreadsheet_id: str, requested_name: str) -> tuple[str, list[str]]:
        names = await self.list_sheet_names(spreadsheet_id)
        if not names:
            raise GoogleSheetsAPIError("Google Sheets không có tab nào để đọc.")

        requested = _normalize_header(requested_name)
        exact = next((name for name in names if _normalize_header(name) == requested), None) if requested else None
        if exact:
            return exact, names

        best_name = names[0]
        best_score = -1
        for name in names[:_MAX_SHEET_CANDIDATES]:
            try:
                preview = await self.read_values(spreadsheet_id, name, preview=True)
                _, mapping = _find_header(preview)
            except (GoogleSheetsAPIError, ValueError):
                continue
            score = len(mapping)
            if score > best_score:
                best_name, best_score = name, score
        return best_name, names

    async def read_sheet(self, spreadsheet_id: str, sheet_name: str) -> SheetSnapshot:
        """Đọc bảng, cắt theo cap, kèm revision để làm khoá cache."""
        values = await self.read_values(spreadsheet_id, sheet_name)
        capped, truncated = cap_values(values)
        return SheetSnapshot(values=capped, truncated=truncated, revision=_revision_of(capped))

    async def read_workbook(
        self,
        spreadsheet_id: str,
        descriptors: list[SheetDescriptor],
    ) -> WorkbookSnapshot:
        """Read bounded ranges for up to 20 tabs, then apply one workbook cap."""
        selected = descriptors[:_MAX_SHEET_CANDIDATES]
        if not selected:
            raise GoogleSheetsAPIError("Google Sheets không có tab nào để đọc.")
        params: list[tuple[str, str]] = [
            ("ranges", bounded_range(descriptor.title))
            for descriptor in selected
        ]
        params.extend(
            [
                ("majorDimension", "ROWS"),
                ("valueRenderOption", "FORMATTED_VALUE"),
            ]
        )
        body = await self._get_json(
            f"{API_BASE}/{quote(spreadsheet_id, safe='')}/values:batchGet",
            params=params,
        )
        value_ranges = body.get("valueRanges", [])
        if not isinstance(value_ranges, list):
            raise GoogleSheetsAPIError(
                "Google Sheets trả về dữ liệu workbook không hợp lệ."
            )
        raw: list[tuple[SheetDescriptor, list[list[object]]]] = []
        for index, descriptor in enumerate(selected):
            value_range = value_ranges[index] if index < len(value_ranges) else {}
            values = value_range.get("values", []) if isinstance(value_range, dict) else []
            if not isinstance(values, list):
                raise GoogleSheetsAPIError(
                    f"Google Sheets trả về dữ liệu tab “{descriptor.title}” không hợp lệ."
                )
            raw.append((descriptor, values))
        capped, content_truncated = cap_workbook_values(raw)
        sheet_ids = {
            descriptor.title: descriptor.sheet_id for descriptor in selected
        }
        return WorkbookSnapshot(
            sheets=capped,
            sheet_ids=sheet_ids,
            available_sheet_names=[descriptor.title for descriptor in descriptors],
            scanned_sheet_names=[descriptor.title for descriptor in selected],
            truncated=content_truncated or len(descriptors) > len(selected),
            revision=_workbook_revision_of(capped, sheet_ids),
        )

    def _proposal_from_candidate(
        self,
        candidate,
        *,
        spreadsheet_id: str,
        sheet_name: str,
        sheet_id: int,
        display_name: str,
        namespace_key: bool,
    ) -> dict | None:
        offset = candidate.row_number
        title = candidate.title.strip()
        if not title or title.startswith("[") or title.startswith("="):
            return None
        assignee = (candidate.assignee or "").strip()
        raw_due = (candidate.due_at or "").strip()
        timezone_name = get_settings().app_timezone or "Asia/Ho_Chi_Minh"
        due_at, all_day, date_ambiguous = _parse_due(raw_due, timezone_name)
        match_kind = name_match_kind(assignee, display_name)
        if match_kind == "none":
            return None
        matched = match_kind in {"exact", "close"}
        name_ambiguous = match_kind == "possible"
        clarification_parts: list[str] = []
        if name_ambiguous:
            person = assignee or "chưa có người phụ trách"
            clarification_parts.append(
                f"Dòng {offset} ghi người phụ trách là “{person}”. Đây có phải là việc của bạn không?"
            )
        if date_ambiguous and due_at is not None:
            clarification_parts.append(
                f"Dòng {offset}: hạn chót '{raw_due}' không rõ năm, hệ thống đang hiểu là {due_at.isoformat()}. Bạn xác nhận lại nhé."
            )
        needs_confirmation = name_ambiguous or (
            date_ambiguous and due_at is not None
        )
        raw_key = (candidate.external_key or "").strip() or f"row-{offset}"
        external_key = (
            f"{sheet_name}:{raw_key}:row-{offset}" if namespace_key else raw_key
        )
        return {
            "row_number": offset,
            "external_key": external_key,
            "title": title,
            "detail": candidate.detail.strip(),
            "assignee": assignee or None,
            "due_at": due_at,
            "all_day": all_day,
            "date_ambiguous": date_ambiguous and due_at is not None,
            "status": (candidate.status or "").strip() or None,
            "matched_user": matched,
            "match_kind": match_kind,
            "needs_confirmation": needs_confirmation,
            "clarification_question": " ".join(clarification_parts) or None,
            "source": f"Google Sheets · {sheet_name}",
            "source_url": (
                f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/"
                f"edit#gid={sheet_id}&range={offset}:{offset}"
            ),
        }

    async def task_proposals(
        self,
        *,
        spreadsheet_id: str,
        sheet_name: str,
        display_name: str,
        values: list[list[object]] | None = None,
        sheet_id: int = 0,
    ) -> list[dict]:
        """`values` cho phép caller đã đọc sẵn bảng (để tính cache/cap) truyền
        lại, tránh gọi Google Sheets API hai lần cho một lượt."""
        if values is None:
            values, _ = cap_values(await self.read_values(spreadsheet_id, sheet_name))
        try:
            candidates = await extract_google_sheet_tasks(values, sheet_name=sheet_name)
        except GoogleSheetTaskExtractionError as exc:
            raise GoogleSheetsAPIError(str(exc)) from exc
        proposals: list[dict] = []
        for candidate in candidates:
            proposal = self._proposal_from_candidate(
                candidate,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sheet_id=sheet_id,
                display_name=display_name,
                namespace_key=False,
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals

    async def workbook_task_proposals(
        self,
        *,
        spreadsheet_id: str,
        display_name: str,
        snapshot: WorkbookSnapshot,
    ) -> list[dict]:
        try:
            candidates = await extract_google_sheet_workbook_tasks(snapshot.sheets)
        except GoogleSheetTaskExtractionError as exc:
            raise GoogleSheetsAPIError(str(exc)) from exc
        proposals: list[dict] = []
        seen_keys: set[str] = set()
        for candidate in candidates:
            sheet_name = (candidate.sheet_name or "").strip()
            sheet_id = snapshot.sheet_ids.get(sheet_name)
            if sheet_id is None:
                continue
            proposal = self._proposal_from_candidate(
                candidate,
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                sheet_id=sheet_id,
                display_name=display_name,
                namespace_key=True,
            )
            if (
                proposal is not None
                and proposal["external_key"] not in seen_keys
            ):
                proposals.append(proposal)
                seen_keys.add(proposal["external_key"])
        return proposals
