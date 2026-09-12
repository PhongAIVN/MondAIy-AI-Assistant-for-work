from types import SimpleNamespace

import pytest

from src.connectors.google_sheets import (
    GoogleSheetsAPIError,
    GoogleSheetsConnector,
    WorkbookSnapshot,
)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        app_timezone="Asia/Ho_Chi_Minh",
        openai_api_key="test-openai-key",
        google_sheet_extraction_model="gpt-4o-mini",
        llm_request_timeout_seconds=5.0,
    )


class _FakeOpenAI:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.messages = None

    def with_structured_output(self, _schema):
        return self

    async def ainvoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.response


def _install_openai(monkeypatch, response=None, error: Exception | None = None):
    fake = _FakeOpenAI(response=response, error=error)
    calls = []

    def client(model, api_key, timeout):
        calls.append((model, api_key, timeout))
        return fake

    monkeypatch.setattr("src.services.google_sheet_task_extraction._openai_client", client)
    monkeypatch.setattr("src.services.google_sheet_task_extraction.get_settings", _settings)
    monkeypatch.setattr("src.connectors.google_sheets.get_settings", _settings)
    return fake, calls


@pytest.mark.asyncio
async def test_semantic_extraction_reads_banner_backlog_without_header_aliases(monkeypatch):
    rows = [
        ["BACKLOG — QUẢN LÝ CÔNG VIỆC"],
        ["Mọi công việc của dự án Mondai"],
        [],
        ["Mã", "Mốc quan trọng", "Người chịu trách nhiệm"],
        ["M3", "Demo nhận diện task đa định dạng", "Người khác"],
        ["M4", "Hoàn thiện báo cáo", "An Hoài Thái"],
    ]
    fake, calls = _install_openai(
        monkeypatch,
        {
            "tasks": [
                {
                    "row_number": 6,
                    "external_key": "M4",
                    "title": "Hoàn thiện báo cáo",
                    "assignee": "An Hoài Thái",
                }
            ]
        },
    )

    proposals = await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="BACKLOG",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert [(item["row_number"], item["title"]) for item in proposals] == [(6, "Hoàn thiện báo cáo")]
    assert calls == [("gpt-4o-mini", "test-openai-key", 5.0)]
    assert "BACKLOG — QUẢN LÝ CÔNG VIỆC" in fake.messages[1].content
    assert "Hoàn thiện báo cáo" in fake.messages[1].content


@pytest.mark.asyncio
async def test_semantic_extraction_accepts_nonstandard_columns(monkeypatch):
    rows = [
        ["SPRINT CARD", "August"],
        ["Work Item ID", "Deliverable", "PIC", "Target Date"],
        ["R-17", "Publish release notes", "An Hoài Thái", "25/08/2026"],
    ]
    _install_openai(
        monkeypatch,
        {
            "tasks": [
                {
                    "row_number": 3,
                    "external_key": "R-17",
                    "title": "Publish release notes",
                    "assignee": "An Hoài Thái",
                    "due_at": "25/08/2026",
                }
            ]
        },
    )

    proposals = await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Sprint",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert proposals[0]["external_key"] == "R-17"
    assert proposals[0]["due_at"] is not None


@pytest.mark.asyncio
async def test_semantic_extraction_handles_hierarchical_sections(monkeypatch):
    _install_openai(
        monkeypatch,
        {
            "tasks": [
                {
                    "row_number": 3,
                    "title": "Ship API contract",
                    "detail": "Phase 1 · Backend",
                    "assignee": "An Hoài Thái",
                }
            ]
        },
    )
    rows = [["Phase 1"], ["Backend"], ["Ship API contract", "An Hoài Thái"], ["Phase 2"]]

    proposals = await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Roadmap",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert proposals[0]["title"] == "Ship API contract"
    assert proposals[0]["detail"] == "Phase 1 · Backend"


@pytest.mark.asyncio
async def test_semantic_extraction_does_not_invent_tasks_from_non_task_table(monkeypatch):
    _install_openai(monkeypatch, {"tasks": []})
    rows = [["Chi phí", "Tháng 7", "Tháng 8"], ["Hạ tầng", "100", "120"]]

    proposals = await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Ngân sách",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert proposals == []


@pytest.mark.asyncio
async def test_semantic_extraction_rejects_ungrounded_row_number(monkeypatch):
    _install_openai(
        monkeypatch,
        {"tasks": [{"row_number": 99, "title": "Invented task", "assignee": "An Hoài Thái"}]},
    )
    rows = [["Chi phí", "Tháng 8"], ["Hạ tầng", "120"]]

    proposals = await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
        spreadsheet_id="sheet-id",
        sheet_name="Ngân sách",
        display_name="An Hoài Thái",
        values=rows,
    )

    assert proposals == []


@pytest.mark.asyncio
async def test_openai_failure_is_safe_and_never_requests_schema_change(monkeypatch):
    _install_openai(monkeypatch, error=TimeoutError("provider timeout"))

    with pytest.raises(GoogleSheetsAPIError) as caught:
        await GoogleSheetsConnector(SimpleNamespace(), SimpleNamespace()).task_proposals(
            spreadsheet_id="sheet-id",
            sheet_name="BACKLOG",
            display_name="An Hoài Thái",
            values=[["Task data"]],
        )

    message = str(caught.value)
    assert "OpenAI" in message
    assert "cột" not in message
    assert "header" not in message.lower()


@pytest.mark.asyncio
async def test_semantic_extraction_scans_workbook_once_and_keeps_tab_source(monkeypatch):
    fake, calls = _install_openai(
        monkeypatch,
        {
            "tasks": [
                {
                    "sheet_name": "Backlog",
                    "row_number": 2,
                    "external_key": "T-001",
                    "title": "Khôi phục pipeline",
                    "assignee": "An Hoài Thái",
                },
                {
                    "sheet_name": "Bug-tracking",
                    "row_number": 2,
                    "external_key": "BUG-003",
                    "title": "Sửa luồng Google Sheet",
                    "assignee": "An Hoài Thái",
                },
                {
                    "sheet_name": "Bug-tracking",
                    "row_number": 2,
                    "external_key": "BUG-003",
                    "title": "Sửa luồng Google Sheet",
                    "assignee": "An Hoài Thái",
                },
                {
                    "sheet_name": "Thành viên nhóm",
                    "row_number": 99,
                    "title": "Task bịa",
                    "assignee": "An Hoài Thái",
                },
            ]
        },
    )
    snapshot = WorkbookSnapshot(
        sheets={
            "Backlog": [["Mã", "Tên việc"], ["T-001", "Khôi phục pipeline"]],
            "Bug-tracking": [["Mã", "Tiêu đề"], ["BUG-003", "Sửa luồng Google Sheet"]],
            "Thành viên nhóm": [["Tên", "Vai trò"], ["An Hoài Thái", "Trưởng nhóm"]],
        },
        sheet_ids={"Backlog": 0, "Bug-tracking": 42, "Thành viên nhóm": 99},
        available_sheet_names=["Backlog", "Bug-tracking", "Thành viên nhóm"],
        scanned_sheet_names=["Backlog", "Bug-tracking", "Thành viên nhóm"],
        truncated=False,
        revision="sha256:workbook",
    )

    proposals = await GoogleSheetsConnector(
        SimpleNamespace(), SimpleNamespace()
    ).workbook_task_proposals(
        spreadsheet_id="sheet-id",
        display_name="Thái Hoài An",
        snapshot=snapshot,
    )

    assert [item["external_key"] for item in proposals] == [
        "Backlog:T-001:row-2",
        "Bug-tracking:BUG-003:row-2",
    ]
    assert proposals[1]["source"] == "Google Sheets · Bug-tracking"
    assert "gid=42&range=2:2" in proposals[1]["source_url"]
    assert calls == [("gpt-4o-mini", "test-openai-key", 5.0)]
    assert '"sheet_name": "Backlog"' in fake.messages[1].content
    assert '"sheet_name": "Bug-tracking"' in fake.messages[1].content


@pytest.mark.asyncio
async def test_semantic_extraction_keeps_non_task_workbook_empty(monkeypatch):
    _install_openai(monkeypatch, {"tasks": []})
    snapshot = WorkbookSnapshot(
        sheets={
            "FAQ": [["Câu hỏi", "Trả lời"], ["Giờ hỗ trợ?", "8:00-17:00"]],
            "Thành viên": [["Tên", "Vai trò"], ["An", "Backend"]],
        },
        sheet_ids={"FAQ": 1, "Thành viên": 2},
        available_sheet_names=["FAQ", "Thành viên"],
        scanned_sheet_names=["FAQ", "Thành viên"],
        truncated=False,
        revision="sha256:non-task",
    )

    proposals = await GoogleSheetsConnector(
        SimpleNamespace(), SimpleNamespace()
    ).workbook_task_proposals(
        spreadsheet_id="sheet-id",
        display_name="An Hoài Thái",
        snapshot=snapshot,
    )

    assert proposals == []
