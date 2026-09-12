"""Kiểm tra vòng đời cuộc họp qua API: ghi chú → kết thúc → sinh task."""

import uuid
from unittest.mock import patch

import pytest

from src.db import SessionLocal
from src.models.user import User
from src.services.auth import decode_token
from src.services.meeting_notes import MeetingSummaryResult, ResolvedActionItem


def _unique_email() -> str:
    return f"test-meeting-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "correct-horse-1"},
    )
    assert response.status_code == 201
    data = response.json()
    return data["userId"], data["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_note(client, token: str, **payload) -> dict:
    body = {"title": "Standup dự án", "notes": "", "transcript": ""} | payload
    response = await client.post("/api/v1/meeting-notes", json=body, headers=_auth(token))
    assert response.status_code == 201, response.text
    return response.json()


def _summary_with_one_action() -> MeetingSummaryResult:
    return MeetingSummaryResult(
        summary="Chốt việc gửi báo cáo.",
        decisions=["An phụ trách báo cáo tuần"],
        action_items=[
            ResolvedActionItem(
                title="Gửi báo cáo tuần cho Phong",
                detail="Bản PDF",
                assignee="An",
                assignee_ambiguous=False,
                time_expression="cuối tuần này",
                due_at=None,
                ambiguous=True,
                evidence_quote="An gửi báo cáo tuần cho Phong",
            )
        ],
    )


@pytest.mark.asyncio
async def test_meeting_note_endpoints_require_authentication(client):
    response = await client.get("/api/v1/meeting-notes")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_note_without_title_gets_default(client):
    _, token = await _register(client)

    note = await _create_note(client, token, title="   ")

    assert note["title"] == "Cuộc họp mới"
    assert note["status"] == "open"
    assert note["actionItems"] == []


@pytest.mark.asyncio
async def test_patch_updates_only_fields_sent(client):
    """Autosave gửi từng ô một; ô không gửi phải giữ nguyên nội dung cũ."""
    _, token = await _register(client)
    note = await _create_note(client, token, notes="ghi chú gốc", transcript="transcript gốc")

    response = await client.patch(
        f"/api/v1/meeting-notes/{note['id']}",
        json={"notes": "ghi chú đã sửa"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "ghi chú đã sửa"
    assert response.json()["transcript"] == "transcript gốc"


@pytest.mark.asyncio
async def test_end_meeting_without_content_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_end_meeting_creates_action_items(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")

    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "summarized"
    assert body["endedAt"] is not None
    assert body["decisions"] == "An phụ trách báo cáo tuần"
    assert len(body["actionItems"]) == 1
    item = body["actionItems"][0]
    assert item["status"] == "suggested"
    assert item["dueAt"] is None
    assert item["ambiguous"] is True
    assert item["taskId"] is None


@pytest.mark.asyncio
async def test_end_meeting_twice_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")

    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        first = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))
        second = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_regular_user_can_summarize_only_one_meeting_per_day(client):
    _, token = await _register(client)
    first = await _create_note(client, token, notes="Tóm tắt cuộc họp thứ nhất.")
    second = await _create_note(client, token, notes="Tóm tắt cuộc họp thứ hai.")

    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        first_response = await client.post(f"/api/v1/meeting-notes/{first['id']}/end", headers=_auth(token))
        second_response = await client.post(f"/api/v1/meeting-notes/{second['id']}/end", headers=_auth(token))

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert "liên hệ đội ngũ phát triển" in second_response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_is_not_limited_to_one_meeting_summary_per_day(client):
    _, token = await _register(client)
    user_id = int(decode_token(token, "access"))
    with SessionLocal() as db:
        db.get(User, user_id).role = "admin"
        db.commit()

    first = await _create_note(client, token, notes="Tóm tắt cuộc họp quản trị thứ nhất.")
    second = await _create_note(client, token, notes="Tóm tắt cuộc họp quản trị thứ hai.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        first_response = await client.post(f"/api/v1/meeting-notes/{first['id']}/end", headers=_auth(token))
        second_response = await client.post(f"/api/v1/meeting-notes/{second['id']}/end", headers=_auth(token))

    assert first_response.status_code == 200
    assert second_response.status_code == 200


@pytest.mark.asyncio
async def test_patch_after_end_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    response = await client.patch(
        f"/api/v1/meeting-notes/{note['id']}",
        json={"notes": "sửa sau khi đã chốt"},
        headers=_auth(token),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_llm_failure_keeps_meeting_open(client):
    """Lỗi nhà cung cấp không được làm mất nội dung người dùng đã gõ."""
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong.")

    with patch("src.api.meeting_notes.summarize_meeting", side_effect=RuntimeError("provider 502")):
        response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.status_code == 502
    after = await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))
    assert after.json()["status"] == "open"
    assert after.json()["notes"] == "An gửi báo cáo tuần cho Phong."


@pytest.mark.asyncio
async def test_accept_action_item_creates_proposed_task(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        ended = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))
    item_id = ended.json()["actionItems"][0]["id"]

    response = await client.post(
        f"/api/v1/meeting-notes/{note['id']}/action-items/{item_id}/accept",
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text
    task = response.json()
    assert task["title"] == "Gửi báo cáo tuần cho Phong"
    # FR-062: chưa xác nhận thì chưa được coi là việc đã chốt.
    assert task["status"] == "proposed"
    assert task["dueAt"] is None

    tasks = await client.get("/api/v1/tasks", headers=_auth(token))
    assert [row["id"] for row in tasks.json()["tasks"]] == [task["id"]]


@pytest.mark.asyncio
async def test_accept_twice_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        ended = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))
    item_id = ended.json()["actionItems"][0]["id"]
    await client.post(f"/api/v1/meeting-notes/{note['id']}/action-items/{item_id}/accept", headers=_auth(token))

    response = await client.post(
        f"/api/v1/meeting-notes/{note['id']}/action-items/{item_id}/accept",
        headers=_auth(token),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_dismiss_action_item_does_not_create_task(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        ended = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))
    item_id = ended.json()["actionItems"][0]["id"]

    response = await client.post(
        f"/api/v1/meeting-notes/{note['id']}/action-items/{item_id}/dismiss",
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"
    tasks = await client.get("/api/v1/tasks", headers=_auth(token))
    assert tasks.json()["tasks"] == []


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_meeting(client):
    _, owner_token = await _register(client)
    _, other_token = await _register(client)
    note = await _create_note(client, owner_token, notes="nội dung riêng tư")

    response = await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(other_token))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_returns_action_item_counts(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    response = await client.get("/api/v1/meeting-notes", headers=_auth(token))

    assert response.status_code == 200
    row = next(item for item in response.json()["meetings"] if item["id"] == note["id"])
    assert row["actionItemCount"] == 1
    assert row["openActionItemCount"] == 1


@pytest.mark.asyncio
async def test_delete_removes_note_and_its_action_items(client):
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")
    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    response = await client.delete(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))

    assert response.status_code == 204
    assert (await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))).status_code == 404


@pytest.mark.asyncio
async def test_end_meeting_uses_summary_based_title(client):
    """Cuộc họp chưa được đặt tên phải nhận tên do LLM sinh từ bản tóm tắt."""
    _, token = await _register(client)
    note = await _create_note(
        client,
        token,
        title="Cuộc họp mới",
        notes="An gửi báo cáo tuần cho Phong cuối tuần này.",
    )

    with (
        patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()),
        patch(
            "src.api.meeting_notes.suggest_meeting_title",
            return_value="Chốt báo cáo tuần",
        ) as suggest,
    ):
        response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Chốt báo cáo tuần"
    # Tóm tắt phải được truyền xuống: đặt tên theo transcript thô hay bắt nhầm
    # chủ đề của mấy phút chào hỏi đầu buổi.
    assert suggest.await_args.kwargs["summary"] == "Chốt việc gửi báo cáo."


@pytest.mark.asyncio
async def test_end_meeting_preserves_user_defined_title(client):
    _, token = await _register(client)
    note = await _create_note(
        client,
        token,
        title="Standup dự án",
        notes="An gửi báo cáo tuần cho Phong cuối tuần này.",
    )

    with (
        patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()),
        patch("src.api.meeting_notes.suggest_meeting_title") as suggest,
    ):
        response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.json()["title"] == "Standup dự án"
    suggest.assert_not_called()


@pytest.mark.asyncio
async def test_end_meeting_preserves_recording_end_timestamp(client):
    """Bấm tổng hợp muộn không được thổi phồng thời lượng cuộc họp."""
    _, token = await _register(client)
    note = await _create_note(client, token, notes="An gửi báo cáo tuần cho Phong cuối tuần này.")

    with patch("src.api.meeting_notes.suggest_meeting_title", return_value="Đã đặt tên"):
        finalize = await client.post(
            f"/api/v1/meeting-notes/{note['id']}/finalize-recording",
            headers=_auth(token),
        )
    assert finalize.status_code == 200, finalize.text

    detail = await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))
    ended_after_recording = detail.json()["endedAt"]
    assert ended_after_recording is not None

    with patch("src.api.meeting_notes.summarize_meeting", return_value=_summary_with_one_action()):
        response = await client.post(f"/api/v1/meeting-notes/{note['id']}/end", headers=_auth(token))

    assert response.json()["endedAt"] == ended_after_recording
