from types import SimpleNamespace

import pytest

from src.agents.tools.google_document_tool import (
    _read_google_sheets,
    google_docs_task_proposals,
    google_sheets_task_proposals,
    reset_google_document_scope,
)
from src.connectors.google_sheets import (
    SheetDescriptor,
    SheetSnapshot,
    WorkbookSnapshot,
)


@pytest.fixture(autouse=True)
def _reset_scope():
    reset_google_document_scope()
    yield
    reset_google_document_scope()


@pytest.mark.asyncio
async def test_google_sheets_tool_refuses_unscoped_read():
    result = await google_sheets_task_proposals.ainvoke(
        {"spreadsheet_url": "https://docs.google.com/spreadsheets/d/abc_123/edit"}
    )

    assert "Chưa xác định được người dùng" in result


@pytest.mark.asyncio
async def test_google_docs_tool_refuses_unscoped_read():
    result = await google_docs_task_proposals.ainvoke(
        {"document_url": "https://docs.google.com/document/d/doc_123/edit"}
    )

    assert "Chưa xác định được người dùng" in result


def _proposal(title: str, source: str, external_key: str) -> dict:
    return {
        "title": title,
        "source": source,
        "external_key": external_key,
    }


@pytest.mark.asyncio
async def test_google_sheets_tool_scans_workbook_and_ignores_obsolete_cache(
    monkeypatch,
):
    descriptors = [
        SheetDescriptor("Backlog", 0),
        SheetDescriptor("Lộ trình", 11),
        SheetDescriptor("Bug-tracking", 22),
        SheetDescriptor("Thành viên nhóm", 33),
    ]
    snapshot = WorkbookSnapshot(
        sheets={
            "Backlog": [["T-001", "Khôi phục pipeline"]],
            "Lộ trình": [["M1", "Chốt kiến trúc"]],
            "Bug-tracking": [["BUG-003", "Sửa luồng Sheet"]],
            "Thành viên nhóm": [["An Hoài Thái", "Trưởng nhóm"]],
        },
        sheet_ids={item.title: item.sheet_id for item in descriptors},
        available_sheet_names=[item.title for item in descriptors],
        scanned_sheet_names=[item.title for item in descriptors],
        truncated=False,
        revision="sha256:workbook",
    )
    proposals = [
        _proposal(
            "Khôi phục pipeline",
            "Google Sheets · Backlog",
            "Backlog:T-001:row-1",
        ),
        _proposal(
            "Chốt kiến trúc",
            "Google Sheets · Lộ trình",
            "Lộ trình:M1:row-1",
        ),
        _proposal(
            "Sửa luồng Sheet",
            "Google Sheets · Bug-tracking",
            "Bug-tracking:BUG-003:row-1",
        ),
    ]
    calls: dict[str, object] = {}

    async def list_sheets(_self, _spreadsheet_id):
        return descriptors

    async def read_workbook(_self, _spreadsheet_id, received):
        assert received == descriptors
        return snapshot

    async def workbook_proposals(_self, **kwargs):
        calls["workbook"] = kwargs
        return proposals

    async def fail_single_tab(*_args, **_kwargs):
        raise AssertionError("implicit request must not select one tab")

    def build_cache_key(**kwargs):
        calls["cache_key"] = kwargs
        return "current-version-key"

    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.google_sheet_extraction_contract",
        lambda: "google-sheets:semantic-v2:gpt-4o-mini",
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.list_sheets",
        list_sheets,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.read_workbook",
        read_workbook,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.workbook_task_proposals",
        workbook_proposals,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.select_sheet",
        fail_single_tab,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.build_cache_key",
        build_cache_key,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.read_cache",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.consume_document_read",
        lambda *_args, **_kwargs: 19,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.write_cache",
        lambda *_args, **kwargs: calls.setdefault("write_cache", kwargs),
    )

    result = await _read_google_sheets(
        SimpleNamespace(),
        user_id="101",
        user=SimpleNamespace(display_name="Thái Hoài An"),
        connection=SimpleNamespace(),
        spreadsheet_url="https://docs.google.com/spreadsheets/d/abcdefghijklmnopqrstuvwxyz/edit",
        sheet_name="",
    )

    assert result["proposal_count"] == 3
    assert result["scanned_sheet_names"] == [item.title for item in descriptors]
    assert result["coverage_complete"] is True
    assert calls["cache_key"]["extractor_version"] == "google-sheets:semantic-v2:gpt-4o-mini"
    assert calls["cache_key"]["sheet_name"] == "*workbook*"
    assert calls["write_cache"]["proposals"] == proposals


@pytest.mark.asyncio
async def test_google_sheets_tool_keeps_explicit_tab_scope(monkeypatch):
    descriptors = [
        SheetDescriptor("Backlog", 7),
        SheetDescriptor("Bug-tracking", 8),
    ]
    calls: dict[str, object] = {}

    async def list_sheets(_self, _spreadsheet_id):
        return descriptors

    async def select_sheet(_self, _spreadsheet_id, requested):
        assert requested == "Backlog"
        return "Backlog", [item.title for item in descriptors]

    async def read_sheet(_self, _spreadsheet_id, selected):
        assert selected == "Backlog"
        return SheetSnapshot([["T-001", "Việc A"]], False, "sha256:tab")

    async def task_proposals(_self, **kwargs):
        calls["task"] = kwargs
        return [_proposal("Việc A", "Google Sheets · Backlog", "T-001")]

    async def fail_workbook(*_args, **_kwargs):
        raise AssertionError("explicit request must not scan workbook")

    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.list_sheets",
        list_sheets,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.select_sheet",
        select_sheet,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.read_sheet",
        read_sheet,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.task_proposals",
        task_proposals,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.GoogleSheetsConnector.read_workbook",
        fail_workbook,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.read_cache",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.consume_document_read",
        lambda *_args, **_kwargs: 19,
    )
    monkeypatch.setattr(
        "src.agents.tools.google_document_tool.document_read_quota.write_cache",
        lambda *_args, **_kwargs: None,
    )

    result = await _read_google_sheets(
        SimpleNamespace(),
        user_id="101",
        user=SimpleNamespace(display_name="An Hoài Thái"),
        connection=SimpleNamespace(),
        spreadsheet_url="https://docs.google.com/spreadsheets/d/abcdefghijklmnopqrstuvwxyz/edit",
        sheet_name="Backlog",
    )

    assert result["sheet_name"] == "Backlog"
    assert result["scanned_sheet_names"] == ["Backlog"]
    assert calls["task"]["sheet_id"] == 7
