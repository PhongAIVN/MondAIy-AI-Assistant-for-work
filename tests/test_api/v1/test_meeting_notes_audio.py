"""Kiểm tra endpoint nhận chunk audio trong lúc họp và nối dần vào transcript."""

import uuid
from unittest.mock import patch

import pytest


def _unique_email() -> str:
    return f"test-meeting-audio-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[str, str]:
    """Tạo một tài khoản mới và trả về (user_id, access_token)."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "correct-horse-1"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return data["userId"], data["accessToken"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_note(client, token: str) -> dict:
    response = await client.post(
        "/api/v1/meeting-notes",
        json={"title": "Họp có ghi âm", "notes": "", "transcript": ""},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _chunk_files(content_type: str = "audio/webm") -> dict:
    """Dựng phần multipart cho một chunk audio giả, không đọc file thật nào."""
    return {"file": ("chunk.webm", b"fake-audio-bytes", content_type)}


async def _post_chunk(
    client,
    token: str,
    note_id: int,
    *,
    speaker: str = "mine",
    offset_ms: int = 20_000,
    content_type: str = "audio/webm",
):
    return await client.post(
        f"/api/v1/meeting-notes/{note_id}/audio-chunk",
        files=_chunk_files(content_type),
        data={"speaker": speaker, "offset_ms": str(offset_ms)},
        headers=_auth(token),
    )


async def _transcript_of(client, token: str, note_id: int) -> str:
    response = await client.get(f"/api/v1/meeting-notes/{note_id}", headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["transcript"]


@pytest.mark.asyncio
async def test_chunk_from_mic_appends_one_line(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Chào mọi người"):
        response = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=20_000)

    assert response.status_code == 200, response.text
    assert response.json()["appended"] is True
    assert response.json()["text"] == "Chào mọi người"
    assert response.json()["remainingMs"] > 0
    assert await _transcript_of(client, token, note["id"]) == "[00:20] Tôi: Chào mọi người"


@pytest.mark.asyncio
async def test_chunk_from_tab_is_labelled_as_other_speaker(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Bên mình nghe rõ"):
        response = await _post_chunk(client, token, note["id"], speaker="theirs", offset_ms=5_000)

    assert response.status_code == 200, response.text
    assert await _transcript_of(client, token, note["id"]) == "[00:05] Người khác: Bên mình nghe rõ"


@pytest.mark.asyncio
async def test_alternating_chunks_keep_send_order(client):
    """Hai kênh mic và tab gửi xen kẽ: transcript phải đủ dòng và đúng thứ tự."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    sent = [
        ("mine", 0, "Bắt đầu họp"),
        ("theirs", 40_000, "Tôi nghe được"),
        ("mine", 80_000, "Chốt lại nhé"),
        ("theirs", 120_000, "Đồng ý"),
    ]
    for speaker, offset_ms, text in sent:
        with patch("src.api.meeting_notes.transcribe_chunk", return_value=text):
            response = await _post_chunk(
                client, token, note["id"], speaker=speaker, offset_ms=offset_ms
            )
        assert response.status_code == 200, response.text

    assert (await _transcript_of(client, token, note["id"])).split("\n") == [
        "[00:00] Tôi: Bắt đầu họp",
        "[00:40] Người khác: Tôi nghe được",
        "[01:20] Tôi: Chốt lại nhé",
        "[02:00] Người khác: Đồng ý",
    ]


@pytest.mark.asyncio
async def test_silent_chunk_is_not_appended(client):
    """Chunk chỉ có tiếng ồn cho text rỗng — không được để lại dòng trống."""
    _, token = await _register(client)
    note = await _create_note(client, token)
    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Có nội dung"):
        await _post_chunk(client, token, note["id"], offset_ms=1_000)
    before = await _transcript_of(client, token, note["id"])

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="   "):
        response = await _post_chunk(client, token, note["id"], offset_ms=2_000)

    assert response.status_code == 200, response.text
    assert response.json()["appended"] is False
    assert response.json()["remainingMs"] > 0
    assert await _transcript_of(client, token, note["id"]) == before


@pytest.mark.asyncio
async def test_unknown_speaker_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="không nên được gọi"):
        response = await _post_chunk(client, token, note["id"], speaker="abc")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_non_audio_content_type_is_rejected(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="không nên được gọi"):
        response = await _post_chunk(client, token, note["id"], content_type="text/plain")

    assert response.status_code == 400
    assert await _transcript_of(client, token, note["id"]) == ""


@pytest.mark.asyncio
async def test_cannot_append_to_another_users_meeting(client):
    _, owner_token = await _register(client)
    _, other_token = await _register(client)
    note = await _create_note(client, owner_token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="nghe lén"):
        response = await _post_chunk(client, other_token, note["id"])

    assert response.status_code == 404
    assert await _transcript_of(client, owner_token, note["id"]) == ""


@pytest.mark.asyncio
async def test_stt_failure_keeps_previous_chunks(client):
    """STT lỗi giữa buổi họp không được làm mất phần đã nhận dạng trước đó."""
    _, token = await _register(client)
    note = await _create_note(client, token)
    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Phần đã ghi được"):
        await _post_chunk(client, token, note["id"], offset_ms=10_000)

    with patch("src.api.meeting_notes.transcribe_chunk", side_effect=RuntimeError("provider 503")):
        response = await _post_chunk(client, token, note["id"], offset_ms=30_000)

    assert response.status_code == 502
    assert await _transcript_of(client, token, note["id"]) == "[00:10] Tôi: Phần đã ghi được"


@pytest.mark.asyncio
async def test_offset_beyond_one_hour_keeps_counting_minutes(client):
    """Họp dài hơn 60 phút vẫn đếm tiếp phút thay vì quay vòng sang giờ."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Cuối buổi"):
        response = await _post_chunk(client, token, note["id"], offset_ms=4_512_000)

    assert response.status_code == 200, response.text
    assert await _transcript_of(client, token, note["id"]) == "[75:12] Tôi: Cuối buổi"
