from datetime import UTC
from types import SimpleNamespace

import pytest

from src.connectors.google_sheets import (
    GoogleSheetsConnector,
    SheetDescriptor,
    _cell,
    _find_header,
    _name_matches,
    cap_values,
    cap_workbook_values,
    extract_spreadsheet_id,
)
from src.services.google_sheet_task_extraction import GoogleSheetTaskCandidate


def _fake_settings() -> SimpleNamespace:
    """Settings giả cho connector: múi giờ + đủ ngưỡng cap của tầng chống spam token.

    Giữ đúng giá trị mặc định trong src/config.py để test bảng nhỏ không bao
    giờ chạm ngưỡng cắt.
    """
    return SimpleNamespace(
        app_timezone="Asia/Ho_Chi_Minh",
        google_sheet_max_rows=500,
        google_sheet_max_columns=20,
        google_document_max_chars=20_000,
    )


@pytest.fixture(autouse=True)
def _semantic_extraction_stub(monkeypatch):
    """Keep connector mapping tests deterministic.

    Production extraction is LLM-only. These older tests cover ownership/date
    mapping after extraction, so their stub translates the fixture rows into
    the new semantic candidate contract instead of calling OpenAI.
    """

    async def extract(values, *, sheet_name):
        del sheet_name
        header_index, mapping = _find_header(values)
        candidates = []
        for row_number, row in enumerate(values[header_index + 1 :], start=header_index + 2):
            title = _cell(row, mapping, "title")
            if not title:
                continue
            candidates.append(
                GoogleSheetTaskCandidate(
                    row_number=row_number,
                    external_key=_cell(row, mapping, "key") or None,
                    title=title,
                    detail=_cell(row, mapping, "detail"),
                    assignee=_cell(row, mapping, "assignee") or None,
                    due_at=_cell(row, mapping, "due") or None,
                    status=_cell(row, mapping, "status") or None,
                )
            )
        return candidates

    monkeypatch.setattr("src.connectors.google_sheets.extract_google_sheet_tasks", extract)


def test_extract_spreadsheet_id_accepts_google_url_and_rejects_other_url():
    spreadsheet_id = "1AbcdefghijklmnopqrstuvwxYZ_1234567890"
    assert extract_spreadsheet_id(f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit") == spreadsheet_id
    with pytest.raises(ValueError):
        extract_spreadsheet_id("https://example.com/spreadsheets/d/not-google")


@pytest.mark.asyncio
async def test_select_sheet_uses_requested_tab_without_preview(monkeypatch):
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_names(_spreadsheet_id):
        return ["Tổng quan", "Backlog"]

    async def fail_preview(*_args, **_kwargs):
        raise AssertionError("exact tab selection must not preview other tabs")

    monkeypatch.setattr(connector, "list_sheet_names", fake_names)
    monkeypatch.setattr(connector, "read_values", fail_preview)

    selected, names = await connector.select_sheet("sheet-id", "backlog")

    assert selected == "Backlog"
    assert names == ["Tổng quan", "Backlog"]


@pytest.mark.asyncio
async def test_select_sheet_matches_contextual_tab_name_without_diacritics(monkeypatch):
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_names(_spreadsheet_id):
        return ["Tổng quan", "Quản lý công việc"]

    async def fail_preview(*_args, **_kwargs):
        raise AssertionError("normalized exact tab selection must not preview other tabs")

    monkeypatch.setattr(connector, "list_sheet_names", fake_names)
    monkeypatch.setattr(connector, "read_values", fail_preview)

    selected, _ = await connector.select_sheet("sheet-id", "quan ly cong viec")

    assert selected == "Quản lý công việc"


def test_workbook_cap_is_global_and_distributed_across_tabs(monkeypatch):
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        lambda: SimpleNamespace(
            google_sheet_max_rows=4,
            google_sheet_max_columns=2,
            google_document_max_chars=12,
        ),
    )
    descriptors = [SheetDescriptor("A", 1), SheetDescriptor("B", 2)]

    capped, truncated = cap_workbook_values(
        [
            (descriptors[0], [["aaaa"], ["bbbb"], ["cccc"]]),
            (descriptors[1], [["1111"], ["2222"], ["3333"]]),
        ]
    )

    assert capped == {"A": [["aaaa"], ["bbbb"]], "B": [["1111"]]}
    assert sum(
        len(str(cell))
        for rows in capped.values()
        for row in rows
        for cell in row
    ) == 12
    assert truncated is True


def test_sheet_caps_preserve_blank_rows_and_following_tasks(monkeypatch):
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )
    rows = [
        ["BACKLOG — QUẢN LÝ CÔNG VIỆC"],
        ["Mọi công việc của dự án"],
        [],
        ["Mã", "Tên công việc"],
        ["T-001", "Khôi phục pipeline"],
    ]

    single, single_truncated = cap_values(rows)
    workbook, workbook_truncated = cap_workbook_values(
        [(SheetDescriptor("Backlog", 0), rows)]
    )

    assert single == rows
    assert workbook["Backlog"] == rows
    assert single_truncated is False
    assert workbook_truncated is False


@pytest.mark.asyncio
async def test_read_workbook_uses_one_batch_request_and_real_sheet_ids(monkeypatch):
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())
    descriptors = [SheetDescriptor("Backlog", 0), SheetDescriptor("Bug-tracking", 42)]
    calls = []

    async def fake_get_json(url, *, params):
        calls.append((url, params))
        return {
            "valueRanges": [
                {"values": [["T-001", "Việc A"]]},
                {"values": [["BUG-003", "Việc B"]]},
            ]
        }

    monkeypatch.setattr(connector, "_get_json", fake_get_json)
    monkeypatch.setattr("src.connectors.google_sheets.get_settings", _fake_settings)

    snapshot = await connector.read_workbook("sheet-id", descriptors)

    assert len(calls) == 1
    assert calls[0][0].endswith("/sheet-id/values:batchGet")
    assert [value for key, value in calls[0][1] if key == "ranges"] == [
        "'Backlog'!A1:U501",
        "'Bug-tracking'!A1:U501",
    ]
    assert snapshot.sheets["Bug-tracking"] == [["BUG-003", "Việc B"]]
    assert snapshot.sheet_ids == {"Backlog": 0, "Bug-tracking": 42}
    assert snapshot.truncated is False


@pytest.mark.asyncio
async def test_select_sheet_picks_tab_with_most_task_headers(monkeypatch):
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_names(_spreadsheet_id):
        return ["Tổng quan", "Danh sách việc"]

    async def fake_values(_spreadsheet_id, sheet_name, *, preview=False):
        assert preview is True
        if sheet_name == "Danh sách việc":
            return [["Tên công việc", "Người phụ trách", "Hạn chót", "Trạng thái"]]
        return [["Chào mừng"], ["Nội dung"]]

    monkeypatch.setattr(connector, "list_sheet_names", fake_names)
    monkeypatch.setattr(connector, "read_values", fake_values)

    selected, names = await connector.select_sheet("sheet-id", "")

    assert selected == "Danh sách việc"
    assert names == ["Tổng quan", "Danh sách việc"]


def test_preview_range_escapes_quotes_and_stays_bounded(monkeypatch):
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        lambda: SimpleNamespace(google_sheet_max_rows=500, google_sheet_max_columns=20),
    )

    assert (
        GoogleSheetsConnector._range_name("Tuần 'A'", preview=True) == "%27Tu%E1%BA%A7n%20%27%27A%27%27%27%21A1%3AT40"
    )


@pytest.mark.asyncio
async def test_task_proposals_map_vietnamese_headers_and_timezone(monkeypatch):
    rows = [
        ["Mã việc", "Tên công việc", "Người phụ trách", "Hạn chót", "Trạng thái", "Mô tả"],
        ["T-001", "Hoàn thành Project Charter", "Nguyễn Văn An", "31/08/2026", "Chưa làm", "Chốt phạm vi"],
        ["T-002", "Review API", "Người khác", "2026-09-01 14:30", "Đang làm", ""],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_values(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(connector, "read_values", fake_read_values)
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )

    proposals = await connector.task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Backlog",
        display_name="Nguyễn Văn An",
    )

    assert len(proposals) == 1
    assert proposals[0]["matched_user"] is True
    assert proposals[0]["needs_confirmation"] is False
    assert proposals[0]["due_at"].tzinfo == UTC
    assert proposals[0]["due_at"].hour == 17
    assert proposals[0]["all_day"] is True


@pytest.mark.asyncio
async def test_task_proposals_reads_structural_header_with_unfamiliar_title(monkeypatch):
    rows = [
        ["BACKLOG — QUẢN LÝ CÔNG VIỆC"],
        ["Mọi công việc của dự án Mondai"],
        [],
        ["Mã", "Mốc quan trọng", "Người chịu trách nhiệm"],
        ["M3", "Demo nhận diện task đa định dạng", "Người khác"],
        ["M4", "Hoàn thiện báo cáo", "An Hoài Thái"],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())
    monkeypatch.setattr("src.connectors.google_sheets.get_settings", _fake_settings)

    proposals = await connector.task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Quản lý công việc",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert len(proposals) == 1
    assert proposals[0]["external_key"] == "M4"
    assert proposals[0]["title"] == "Hoàn thiện báo cáo"
    assert proposals[0]["source"] == "Google Sheets · Quản lý công việc"


@pytest.mark.asyncio
async def test_task_proposals_find_header_after_template_title_rows(monkeypatch):
    rows = [
        ["BACKLOG — QUẢN LÝ CÔNG VIỆC THEO SPRINT"],
        ["Mọi công việc của dự án"],
        ["Mã việc", "Tên công việc", "Người phụ trách", "Hạn chót"],
        ["T-001", "Lập Project Charter", "An", "01/09/2026"],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_values(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(connector, "read_values", fake_read_values)
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )

    proposals = await connector.task_proposals(spreadsheet_id="sheet-id", sheet_name="Backlog", display_name="An")

    assert [proposal["row_number"] for proposal in proposals] == [4]


def test_name_matches_rejects_short_token_substring_false_positive():
    """Regression: "An" không được khớp nhầm vào "Nguyễn Văn Anh" chỉ vì là
    substring — đây chính là bug đã review (match quá lỏng dùng `in`)."""
    assert _name_matches("An", "Nguyễn Văn Anh") is False
    assert _name_matches("Nguyễn Văn Anh", "An") is False


def test_name_matches_rejects_partial_surname_overlap_false_positive():
    """Regression: trùng họ một phần (chỉ 2/3 token trùng nhưng không đủ theo
    hướng subset) không được coi là cùng một người."""
    assert _name_matches("Thái Hoài An", "Nguyễn Thái Hoài") is False


def test_name_matches_accepts_exact_name_after_normalize():
    assert _name_matches("Nguyễn Văn An", "nguyen van an") is True
    assert _name_matches("An", "An") is True


def test_name_matches_accepts_token_reorder_with_enough_overlap():
    assert _name_matches("Văn An Nguyễn", "Nguyễn Văn An") is True


@pytest.mark.asyncio
async def test_task_proposals_excludes_wrong_partial_name(monkeypatch):
    """Regression: không trả dòng có tên ngắn nhưng không liên quan user."""
    rows = [
        ["Mã việc", "Tên công việc", "Người phụ trách", "Hạn chót"],
        ["T-001", "Việc của người khác", "An", "01/09/2026"],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_values(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(connector, "read_values", fake_read_values)
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )

    proposals = await connector.task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Backlog",
        display_name="Nguyễn Văn Anh",
    )

    assert proposals == []


@pytest.mark.asyncio
async def test_task_proposals_flags_due_date_missing_year_as_ambiguous(monkeypatch):
    """Regression: hạn chót thiếu năm (vd "15/3") phải được đánh dấu ambiguous
    và kèm câu hỏi làm rõ, không im lặng tin theo năm hiện tại dateutil tự suy."""
    rows = [
        ["Mã việc", "Tên công việc", "Người phụ trách", "Hạn chót"],
        ["T-001", "Việc thiếu năm hạn chót", "An", "15/3"],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_values(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(connector, "read_values", fake_read_values)
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )

    proposals = await connector.task_proposals(spreadsheet_id="sheet-id", sheet_name="Backlog", display_name="An")

    proposal = proposals[0]
    assert proposal["date_ambiguous"] is True
    assert proposal["needs_confirmation"] is True
    assert "không rõ năm" in proposal["clarification_question"]


@pytest.mark.asyncio
async def test_task_proposals_due_date_with_explicit_year_not_ambiguous(monkeypatch):
    rows = [
        ["Mã việc", "Tên công việc", "Người phụ trách", "Hạn chót"],
        ["T-001", "Việc có năm rõ ràng", "An", "15/3/2027"],
    ]
    connector = GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace())

    async def fake_read_values(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(connector, "read_values", fake_read_values)
    monkeypatch.setattr(
        "src.connectors.google_sheets.get_settings",
        _fake_settings,
    )

    proposals = await connector.task_proposals(spreadsheet_id="sheet-id", sheet_name="Backlog", display_name="An")

    proposal = proposals[0]
    assert proposal["date_ambiguous"] is False
    assert proposal["needs_confirmation"] is False
