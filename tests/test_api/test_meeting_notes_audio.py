"""Kiểm tra endpoint nhận chunk audio trong lúc họp và nối dần vào transcript."""

import uuid
from unittest.mock import patch

import pytest

from src.config import get_settings

# Một lát hạn mức dài đúng bằng chu kỳ cắt chunk. Đọc từ cấu hình thay vì ghi số
# cứng để chỉnh độ dài chunk không phải sửa lại từng con số trong file này.
SLOT_MS = get_settings().recording_chunk_duration_ms


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
    # remainingMs được kiểm riêng ở test hạn mức, ở đây chỉ khẳng định phần nội dung.
    body = response.json()
    assert body["appended"] is True
    assert body["text"] == "Chào mọi người"
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
            response = await _post_chunk(client, token, note["id"], speaker=speaker, offset_ms=offset_ms)
        assert response.status_code == 200, response.text

    assert (await _transcript_of(client, token, note["id"])).split("\n") == [
        "[00:00] Tôi: Bắt đầu họp",
        "[00:40] Người khác: Tôi nghe được",
        "[01:20] Tôi: Chốt lại nhé",
        "[02:00] Người khác: Đồng ý",
    ]


@pytest.mark.asyncio
async def test_chunks_that_finish_out_of_order_are_sorted_by_recording_time(client):
    """STT kênh sau xong trước không được làm hội thoại hiển thị đảo thứ tự."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Câu nói sau"):
        later = await _post_chunk(client, token, note["id"], speaker="theirs", offset_ms=40_000)
    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Câu mở đầu"):
        earlier = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=0)

    assert later.status_code == 200
    assert earlier.status_code == 200
    assert (await _transcript_of(client, token, note["id"])).split("\n") == [
        "[00:00] Tôi: Câu mở đầu",
        "[00:40] Người khác: Câu nói sau",
    ]


@pytest.mark.asyncio
async def test_retry_of_same_speaker_and_offset_does_not_duplicate_transcript(client):
    """Response upload thất lạc có thể khiến extension gửi lại đúng một chunk."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Nội dung gốc"):
        first = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=20_000)
    # Provider có thể trả câu chữ hơi khác ở lần gọi lại; định danh chunk phải
    # dựa trên kênh + offset, không dựa vào text nhận dạng.
    with patch("src.api.meeting_notes.transcribe_chunk", return_value="Nội dung gốc."):
        retried = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=20_000)

    assert first.json()["appended"] is True
    assert retried.json()["appended"] is False
    assert await _transcript_of(client, token, note["id"]) == "[00:20] Tôi: Nội dung gốc"


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
    body = response.json()
    assert body["appended"] is False
    assert "text" not in body
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


async def _promote_to_admin(user_id: str) -> None:
    """Nâng quyền trực tiếp trong DB — không có endpoint tự phong admin."""
    from src.db import SessionLocal
    from src.models.user import User

    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        assert user is not None
        user.role = "admin"
        db.commit()


@pytest.mark.asyncio
async def test_han_muc_tra_ve_day_du_cho_nguoi_dung_moi(client):
    _, token = await _register(client)

    response = await client.get("/api/v1/meeting-notes/recording-quota", headers=_auth(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["limitMs"] == 15 * 60 * 1000
    assert body["usedMs"] == 0
    assert body["remainingMs"] == 15 * 60 * 1000
    assert body["unlimited"] is False


@pytest.mark.asyncio
async def test_route_han_muc_khong_bi_nuot_boi_route_note_id(client):
    """ "recording-quota" phải khớp route riêng chứ không rơi vào "/{note_id}".

    Nếu thứ tự khai báo sai, FastAPI ép "recording-quota" sang int và trả 422.
    """
    _, token = await _register(client)

    response = await client.get("/api/v1/meeting-notes/recording-quota", headers=_auth(token))

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_moi_chunk_tru_dan_han_muc_va_hai_kenh_chi_tinh_mot_lan(client):
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="nội dung"):
        first = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=0)
        # Kênh tab của đúng lát đó không được trừ thêm lần nữa.
        same_slot = await _post_chunk(client, token, note["id"], speaker="theirs", offset_ms=0)
        next_slot = await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=20_000)

    limit = 15 * 60 * 1000
    assert first.json()["remainingMs"] == limit - SLOT_MS
    assert same_slot.json()["remainingMs"] == limit - SLOT_MS
    assert next_slot.json()["remainingMs"] == limit - 2 * SLOT_MS


@pytest.mark.asyncio
async def test_hai_kenh_lech_vai_mili_giay_van_chi_tinh_mot_lat(client):
    """Mic và tab cắt chunk lệch nhau vài ms nhưng vẫn là một lát họp.

    Hai kênh có `setInterval` riêng và tự lấy `Date.now()` lúc cắt, nên cùng một
    lát ra hai offset thô khác nhau. Trước khi offset được quy về lưới, khoá
    chống tính đôi trượt và người dùng bị trừ hai lần cho một lát duy nhất.
    """
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="nội dung"):
        await _post_chunk(client, token, note["id"], speaker="mine", offset_ms=SLOT_MS + 3)
        drifted = await _post_chunk(client, token, note["id"], speaker="theirs", offset_ms=SLOT_MS + 47)

    assert drifted.status_code == 200, drifted.text
    assert drifted.json()["remainingMs"] == 15 * 60 * 1000 - SLOT_MS


@pytest.mark.asyncio
async def test_het_han_muc_thi_chan_429_va_khong_goi_stt(client):
    user_id, token = await _register(client)
    note = await _create_note(client, token)

    # Nạp sẵn đủ 15 phút cho hôm nay thay vì gửi 45 chunk thật.
    from src.db import SessionLocal
    from src.models.recording_quota import RecordingQuotaSlot
    from src.services.recording_quota import quota_day

    with SessionLocal() as db:
        for index in range(45):
            db.add(
                RecordingQuotaSlot(
                    user_id=user_id,
                    usage_date=quota_day(),
                    note_id=note["id"],
                    offset_ms=index * 20_000,
                    duration_ms=20_000,
                )
            )
        db.commit()

    with patch("src.api.meeting_notes.transcribe_chunk") as stt:
        response = await _post_chunk(client, token, note["id"], offset_ms=900_000)

    assert response.status_code == 429, response.text
    assert "15 phút" in response.json()["detail"]
    # Chặn phải xảy ra TRƯỚC khi gọi nhà cung cấp, không trả tiền cho audio bị từ chối.
    stt.assert_not_called()


@pytest.mark.asyncio
async def test_admin_khong_bi_chan_du_da_qua_15_phut(client):
    user_id, token = await _register(client)
    await _promote_to_admin(user_id)
    note = await _create_note(client, token)

    from src.db import SessionLocal
    from src.models.recording_quota import RecordingQuotaSlot
    from src.services.recording_quota import quota_day

    with SessionLocal() as db:
        for index in range(45):
            db.add(
                RecordingQuotaSlot(
                    user_id=user_id,
                    usage_date=quota_day(),
                    note_id=note["id"],
                    offset_ms=index * 20_000,
                    duration_ms=20_000,
                )
            )
        db.commit()

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="admin nói"):
        response = await _post_chunk(client, token, note["id"], offset_ms=900_000)

    assert response.status_code == 200, response.text
    assert response.json()["appended"] is True

    quota = await client.get("/api/v1/meeting-notes/recording-quota", headers=_auth(token))
    assert quota.json()["unlimited"] is True


@pytest.mark.asyncio
async def test_chunk_loi_stt_khong_an_mat_han_muc(client):
    """Lỗi nhà cung cấp không được trừ phút của người dùng."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", side_effect=RuntimeError("provider down")):
        failed = await _post_chunk(client, token, note["id"], offset_ms=0)
    assert failed.status_code == 502

    quota = await client.get("/api/v1/meeting-notes/recording-quota", headers=_auth(token))
    assert quota.json()["usedMs"] == 0


@pytest.mark.asyncio
async def test_chunk_im_lang_van_tru_han_muc(client):
    """Im lặng vẫn chiếm thời gian họp thật và vẫn tốn một lượt gọi provider."""
    _, token = await _register(client)
    note = await _create_note(client, token)

    with patch("src.api.meeting_notes.transcribe_chunk", return_value="   "):
        response = await _post_chunk(client, token, note["id"], offset_ms=0)

    assert response.status_code == 200, response.text
    assert response.json()["appended"] is False

    quota = await client.get("/api/v1/meeting-notes/recording-quota", headers=_auth(token))
    assert quota.json()["usedMs"] == SLOT_MS
