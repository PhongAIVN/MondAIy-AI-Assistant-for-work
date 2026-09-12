"""Kiểm tra bước khép lại phiên ghi âm: xoá cuộc họp rỗng và tự đặt tên."""

import uuid
from unittest.mock import patch

import pytest

from src.services.meeting_notes import MeetingSummaryResult


def _unique_email() -> str:
    return f"test-finalize-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "correct-horse-1"},
    )
    assert response.status_code == 201, response.text
    return response.json()["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_note(client, token: str, **payload) -> dict:
    body = {"title": "", "notes": "", "transcript": ""} | payload
    response = await client.post("/api/v1/meeting-notes", json=body, headers=_auth(token))
    assert response.status_code == 201, response.text
    return response.json()


async def _finalize(client, token: str, note_id: int):
    return await client.post(
        f"/api/v1/meeting-notes/{note_id}/finalize-recording",
        headers=_auth(token),
    )


@pytest.mark.asyncio
async def test_empty_recording_is_deleted(client):
    """Bấm dừng mà mic tắt hoặc bấm nhầm sẽ để lại cuộc họp trống — phải xoá."""
    token = await _register(client)
    note = await _create_note(client, token)

    response = await _finalize(client, token, note["id"])

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True}

    gone = await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_whitespace_only_recording_is_deleted(client):
    token = await _register(client)
    note = await _create_note(client, token, transcript="   \n  \n")

    response = await _finalize(client, token, note["id"])

    assert response.json()["deleted"] is True


@pytest.mark.asyncio
async def test_finalize_keeps_default_title_until_summary_exists(client):
    """Finalize chưa có summary nên không được chốt một tên AI sơ bộ."""
    token = await _register(client)
    note = await _create_note(
        client,
        token,
        transcript=(
            "[00:20] Tôi: mình chốt lại là tuần này đẩy xong phần đăng nhập\n"
            "[00:41] Người khác: ừ phần phân quyền để sang tuần sau nhé"
        ),
    )

    with patch("src.api.meeting_notes.suggest_meeting_title") as suggest:
        response = await _finalize(client, token, note["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deleted"] is False
    assert body["title"] == "Cuộc họp mới"
    suggest.assert_not_called()


@pytest.mark.asyncio
async def test_create_upload_finalize_end_uses_summary_based_title(client):
    """Regression cho luồng ghi âm thật từ đầu tới cuối.

    Tên tự động phải dựa trên summary tại `/end`, không phải bản
    transcript thô có đầy lời chào tại `/finalize-recording`.
    """
    token = await _register(client)
    note = await _create_note(client, token)

    with patch(
        "src.api.meeting_notes.transcribe_chunk",
        return_value="Alo mọi người, hôm nay chốt kế hoạch chuyển hạ tầng tháng chín.",
    ):
        uploaded = await client.post(
            f"/api/v1/meeting-notes/{note['id']}/audio-chunk",
            files={"file": ("chunk.webm", b"fake-audio", "audio/webm")},
            data={"speaker": "mine", "offset_ms": "0"},
            headers=_auth(token),
        )
    assert uploaded.status_code == 200, uploaded.text

    finalized = await _finalize(client, token, note["id"])
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["title"] == "Cuộc họp mới"

    summary = MeetingSummaryResult(
        summary="Cuộc họp chốt kế hoạch chuyển hạ tầng sang môi trường mới trong tháng chín."
    )
    with (
        patch("src.api.meeting_notes.summarize_meeting", return_value=summary),
        patch(
            "src.api.meeting_notes.suggest_meeting_title",
            return_value="Kế hoạch chuyển hạ tầng",
        ) as suggest,
    ):
        ended = await client.post(
            f"/api/v1/meeting-notes/{note['id']}/end",
            headers=_auth(token),
        )

    assert ended.status_code == 200, ended.text
    assert ended.json()["title"] == "Kế hoạch chuyển hạ tầng"
    assert suggest.await_args.kwargs["summary"] == summary.summary


@pytest.mark.asyncio
async def test_user_title_edited_after_finalize_is_preserved_on_end(client):
    """Tên người dùng là authoritative, kể cả khi sửa sau lúc dừng ghi."""
    token = await _register(client)
    note = await _create_note(client, token, transcript="Nội dung cuộc họp đủ để tóm tắt.")
    finalized = await _finalize(client, token, note["id"])
    assert finalized.status_code == 200, finalized.text

    edited = await client.patch(
        f"/api/v1/meeting-notes/{note['id']}",
        json={"title": "Tên do người dùng chốt"},
        headers=_auth(token),
    )
    assert edited.status_code == 200, edited.text

    with (
        patch(
            "src.api.meeting_notes.summarize_meeting",
            return_value=MeetingSummaryResult(summary="Tóm tắt tự động."),
        ),
        patch("src.api.meeting_notes.suggest_meeting_title") as suggest,
    ):
        ended = await client.post(
            f"/api/v1/meeting-notes/{note['id']}/end",
            headers=_auth(token),
        )

    assert ended.status_code == 200, ended.text
    assert ended.json()["title"] == "Tên do người dùng chốt"
    suggest.assert_not_called()


@pytest.mark.asyncio
async def test_user_defined_title_is_preserved(client):
    """Người dùng đã đặt tên thì tên đó thắng — tự động ghi đè là cướp quyền."""
    token = await _register(client)
    note = await _create_note(client, token, title="Họp sprint 12", transcript="[00:20] Tôi: nội dung dài đủ để xử lý")

    with patch("src.api.meeting_notes.suggest_meeting_title") as suggest:
        response = await _finalize(client, token, note["id"])

    assert response.json()["title"] == "Họp sprint 12"
    suggest.assert_not_called()


@pytest.mark.asyncio
async def test_handwritten_notes_keep_an_empty_recording(client):
    """Người dùng gõ tay nhưng ghi âm không ra chữ — nội dung đó vẫn phải giữ."""
    token = await _register(client)
    note = await _create_note(client, token, notes="Nhớ hỏi lại anh Phong về deadline")

    with patch("src.api.meeting_notes.suggest_meeting_title", return_value="Việc cần hỏi lại"):
        response = await _finalize(client, token, note["id"])

    assert response.json()["deleted"] is False
    still_there = await client.get(f"/api/v1/meeting-notes/{note['id']}", headers=_auth(token))
    assert still_there.status_code == 200


@pytest.mark.asyncio
async def test_other_users_recordings_return_not_found(client):
    token_a = await _register(client)
    token_b = await _register(client)
    note = await _create_note(client, token_a, transcript="nội dung")

    response = await _finalize(client, token_b, note["id"])

    assert response.status_code == 404
