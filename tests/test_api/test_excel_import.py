import uuid
from io import BytesIO

import openpyxl
import pytest
from docx import Document


async def _register(client, display_name: str = "Nguyễn Văn An") -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"excel-{uuid.uuid4().hex[:12]}@example.com",
            "password": "correct-horse-1",
            "displayName": display_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["accessToken"]


def _xlsx_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Tên công việc", "Người phụ trách", "Hạn chót"])
    sheet.append(["Chuẩn bị demo", "Nguyễn Văn An", "31/08/2026"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _docx_bytes() -> bytes:
    document = Document()
    table = document.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "Nội dung công việc"
    table.rows[0].cells[1].text = "Người phụ trách"
    table.rows[0].cells[2].text = "Hạn chót"
    table.rows[1].cells[0].text = "Chuẩn bị demo DOCX"
    table.rows[1].cells[1].text = "Nguyễn Văn An"
    table.rows[1].cells[2].text = "31/08/2026"
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@pytest.mark.asyncio
async def test_excel_import_returns_only_matching_proposals_and_agent_summary(client, monkeypatch):
    token = await _register(client)

    async def fake_analysis(**_kwargs):
        return "Bạn có một việc cần ưu tiên.", "", None

    monkeypatch.setattr("src.api.excel_import._agent_analysis", fake_analysis)
    response = await client.post(
        "/api/v1/excel/task-proposals",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("cong-viec.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["proposals"][0]["title"] == "Chuẩn bị demo"
    assert payload["proposals"][0]["matchedUser"] is True
    assert payload["agentResponse"] == "Bạn có một việc cần ưu tiên."


@pytest.mark.asyncio
async def test_excel_import_rejects_files_larger_than_200kb(client):
    token = await _register(client)
    response = await client.post(
        "/api/v1/excel/task-proposals",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("too-large.xlsx", b"x" * (200 * 1024 + 1), "application/octet-stream")},
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_file_import_accepts_docx_with_the_same_size_and_identity_rules(client, monkeypatch):
    token = await _register(client)

    async def fake_analysis(**_kwargs):
        return "Có một task từ DOCX.", "", None

    monkeypatch.setattr("src.api.excel_import._agent_analysis", fake_analysis)
    response = await client.post(
        "/api/v1/excel/task-proposals",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("lich.docx", _docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["proposals"][0]["title"] == "Chuẩn bị demo DOCX"


@pytest.mark.asyncio
async def test_file_import_asks_for_name_and_accepts_a_user_supplied_search_name(client, monkeypatch):
    token = await _register(client, display_name="Người Không Khớp")

    async def fake_analysis(**kwargs):
        if kwargs["proposals"]:
            return "Đã tìm thấy task.", "", None
        return "Bạn muốn tìm theo tên nào?", "", None

    monkeypatch.setattr("src.api.excel_import._agent_analysis", fake_analysis)
    unmatched = await client.post(
        "/api/v1/excel/task-proposals",
        headers={"Authorization": f"Bearer {token}"},
        files={"files": ("cong-viec.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert unmatched.status_code == 200, unmatched.text
    assert unmatched.json()["needsNameQuery"] is True
    assert "Nguyễn Văn An" in unmatched.json()["suggestedNames"]

    matched = await client.post(
        "/api/v1/excel/task-proposals",
        headers={"Authorization": f"Bearer {token}"},
        data={"search_name": "Nguyễn Văn An"},
        files={"files": ("cong-viec.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["searchedName"] == "Nguyễn Văn An"
    assert matched.json()["needsNameQuery"] is False
