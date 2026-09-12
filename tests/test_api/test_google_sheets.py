"""Test quyền và contract endpoint đọc Google Sheets."""

import uuid

import pytest

from src.connectors.google_sheets import SheetSnapshot
from src.db import SessionLocal
from src.models.connection import Connection


async def _register(client) -> tuple[str, str]:
    email = f"sheet-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-1", "displayName": "Nguyễn Văn An"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["userId"], body["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_google_sheets_requires_a_connection(client):
    _, token = await _register(client)
    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={"spreadsheetUrl": "https://docs.google.com/spreadsheets/d/1AbcdefghijklmnopqrstuvwxYZ_1234567890/edit"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_google_sheets_returns_proposals_after_scope_check(client, monkeypatch):
    user_id, token = await _register(client)
    db = SessionLocal()
    try:
        db.add(
            Connection(
                user_id=user_id,
                provider="google",
                scopes="openid email https://www.googleapis.com/auth/spreadsheets.readonly",
                status="connected_ready",
            )
        )
        db.commit()
    finally:
        db.close()

    async def fake_select_sheet(self, _spreadsheet_id, requested_name):
        assert requested_name == ""
        return "Danh sách việc", ["Tổng quan", "Danh sách việc"]

    async def fake_proposals(self, **_kwargs):
        return [
            {
                "row_number": 4,
                "external_key": "T-001",
                "title": "Lập Project Charter",
                "detail": "",
                "assignee": "Nguyễn Văn An",
                "due_at": None,
                "all_day": False,
                "status": "Chưa làm",
                "matched_user": True,
                "needs_confirmation": False,
                "clarification_question": None,
                "source": "Google Sheets · Backlog",
                "source_url": "https://docs.google.com/",
            }
        ]

    monkeypatch.setattr("src.api.google_sheets.GoogleSheetsConnector.select_sheet", fake_select_sheet)
    monkeypatch.setattr("src.api.google_sheets.GoogleSheetsConnector.task_proposals", fake_proposals)

    async def fake_read_sheet(self, spreadsheet_id: str, sheet_name: str) -> SheetSnapshot:
        """Chặn lượt gọi Sheets API thật; endpoint đọc bảng để tính khoá cache."""
        assert sheet_name == "Danh sách việc"
        return SheetSnapshot(values=[["Tên công việc"]], truncated=False, revision=uuid.uuid4().hex)

    monkeypatch.setattr("src.api.google_sheets.GoogleSheetsConnector.read_sheet", fake_read_sheet)
    response = await client.post(
        "/api/v1/google-sheets/task-proposals",
        headers=_auth(token),
        json={
            "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/1AbcdefghijklmnopqrstuvwxYZ_1234567890/edit",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sheetName"] == "Danh sách việc"
    assert body["availableSheetNames"] == ["Tổng quan", "Danh sách việc"]
    assert body["proposals"][0]["title"] == "Lập Project Charter"
