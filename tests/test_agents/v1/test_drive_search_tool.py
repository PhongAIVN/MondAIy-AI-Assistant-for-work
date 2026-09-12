from types import SimpleNamespace

import pytest

from src.agents.nodes import core_nodes
from src.agents.tools.drive_search_tool import (
    drive_search_files,
    reset_drive_search_scope,
    set_drive_search_scope,
)
from src.connectors.google_drive import GoogleDriveAPIError


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_drive_search_scope()
    yield
    reset_drive_search_scope()


def _connection(scopes=("drive.readonly",)):
    return SimpleNamespace(scopes=list(scopes))


def _patch_connection(monkeypatch, connection):
    monkeypatch.setattr(
        "src.services.connections.preferred_connection",
        lambda db, user_id, provider="google": connection,
    )


def _patch_list_files(monkeypatch, result=None, error: Exception | None = None):
    class FakeConnector:
        def __init__(self, connection, db):
            self.connection = connection
            self.db = db

        async def list_files(self, **kwargs):
            if error is not None:
                raise error
            return result

    monkeypatch.setattr("src.connectors.google_drive.GoogleDriveConnector", FakeConnector)


@pytest.mark.asyncio
async def test_drive_tool_refuses_to_search_without_user_scope():
    result = await drive_search_files.ainvoke({"query": "kế hoạch"})
    assert "Drive của ai" in result


@pytest.mark.asyncio
async def test_drive_tool_reports_missing_connection(monkeypatch):
    set_drive_search_scope("user-1")
    _patch_connection(monkeypatch, None)

    result = await drive_search_files.ainvoke({"query": "kế hoạch"})

    assert result.startswith("Chưa có kết nối")


@pytest.mark.asyncio
async def test_drive_tool_returns_bounded_files_with_source_links(monkeypatch):
    set_drive_search_scope("user-1")
    _patch_connection(monkeypatch, _connection())
    _patch_list_files(
        monkeypatch,
        result={
            "files": [
                {
                    "id": "f1",
                    "name": "Kế hoạch Q3",
                    "kind": "document",
                    "modified_time": "2026-08-20T09:00:00Z",
                    "web_view_link": "https://docs.google.com/document/d/f1/edit",
                }
            ],
            "next_page_token": None,
        },
    )

    result = await drive_search_files.ainvoke({"query": "kế hoạch"})

    assert "Kế hoạch Q3" in result
    assert "[document]" in result
    assert "https://docs.google.com/document/d/f1/edit" in result


@pytest.mark.asyncio
async def test_drive_tool_caps_number_of_files_shown(monkeypatch):
    set_drive_search_scope("user-1")
    _patch_connection(monkeypatch, _connection())
    files = [
        {
            "id": f"f{i}",
            "name": f"File {i}",
            "kind": "document",
            "modified_time": "2026-08-20T09:00:00Z",
            "web_view_link": f"https://docs.google.com/document/d/f{i}/edit",
        }
        for i in range(30)
    ]
    _patch_list_files(monkeypatch, result={"files": files, "next_page_token": None})

    result = await drive_search_files.ainvoke({})

    for i in range(20):
        assert f"File {i}" in result
    for i in range(20, 30):
        assert f"File {i}" not in result
    assert "Còn file khác" in result


@pytest.mark.asyncio
async def test_drive_tool_translates_403_into_controlled_answer(monkeypatch):
    set_drive_search_scope("user-1")
    _patch_connection(monkeypatch, _connection())
    _patch_list_files(
        monkeypatch,
        error=GoogleDriveAPIError("Google Drive từ chối quyền liệt kê file (403).", status_code=403),
    )

    result = await drive_search_files.ainvoke({"query": "kế hoạch"})

    assert "Không tìm được file Google Drive" in result
    assert "403" in result


@pytest.mark.asyncio
async def test_drive_tool_reports_missing_scope(monkeypatch):
    set_drive_search_scope("user-1")
    _patch_connection(monkeypatch, _connection(scopes=["gmail.readonly"]))

    result = await drive_search_files.ainvoke({"query": "kế hoạch"})

    assert "chưa có quyền duyệt Drive" in result


def test_drive_tool_is_bound_as_read_only():
    names = {tool.name for tool in core_nodes._tools()}

    assert "drive_search_files" in names
    assert "drive_search_files" in core_nodes._READ_ONLY_TOOLS
