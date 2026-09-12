"""Test adapter STT: parse response, che khoá khi lỗi, và ghép lượt nói.

Toàn bộ lời gọi mạng đi qua `httpx.MockTransport` — không test nào chạm API
thật, vì gọi thật vừa tốn tiền vừa làm test phụ thuộc dịch vụ ngoài.
"""

from __future__ import annotations

import httpx
import pytest

from src.config import get_settings
from src.services import stt

FAKE_API_KEY = "fake-stt-api-key-for-redaction-test"


@pytest.fixture(autouse=True)
def stt_settings(monkeypatch: pytest.MonkeyPatch):
    """Cắm khoá giả vào Settings đã cache để test không phụ thuộc .env của máy."""
    settings = get_settings()
    monkeypatch.setattr(settings, "fpt_api_key", FAKE_API_KEY)
    monkeypatch.setattr(settings, "fpt_base_url", "https://mkp-api.fptcloud.com")
    monkeypatch.setattr(settings, "stt_model", "whisper-large-v3-turbo", raising=False)
    monkeypatch.setattr(settings, "stt_language", "vi", raising=False)
    return settings


def mount_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    """Ép mọi AsyncClient trong test đi qua MockTransport và ghi lại request.

    Cơ chế: thay `httpx.AsyncClient` bằng lớp con luôn tự đính transport giả,
    nhờ vậy `transcribe_chunk` không cần tham số riêng chỉ để phục vụ test.
    """
    seen: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(recording_handler)
    real_client = httpx.AsyncClient

    class PatchedClient(real_client):
        def __init__(self, **kwargs):
            kwargs["transport"] = transport
            super().__init__(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedClient)
    return seen


@pytest.mark.asyncio
async def test_transcribe_chunk_parses_flat_response(monkeypatch: pytest.MonkeyPatch):
    """Response phẳng {"text","usage"} phải được đọc đúng và strip khoảng trắng đầu."""
    seen = mount_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "text": " Chào mọi người, mình sẽ trình bày phần đầu.",
                "usage": {"input_duration": 9.93, "output_tokens": 48},
            },
        ),
    )

    text = await stt.transcribe_chunk(b"fake-audio-bytes", "chunk.webm")

    assert text == "Chào mọi người, mình sẽ trình bày phần đầu."
    request = seen[0]
    assert request.url.path == "/v1/audio/transcriptions"
    assert request.headers["authorization"] == f"Bearer {FAKE_API_KEY}"
    body = request.content.decode("utf-8", errors="ignore")
    assert "whisper-large-v3-turbo" in body
    # Các tham số bị API bỏ qua thì không được gửi, tránh hiểu nhầm là có hiệu lực.
    for ignored in ("response_format", "timestamp_granularities", "stream", "prompt"):
        assert ignored not in body


@pytest.mark.asyncio
async def test_transcribe_chunk_gui_language_mac_dinh(monkeypatch: pytest.MonkeyPatch):
    """Mặc định phải gửi language=vi, nếu không webm/opus bị model dịch sang tiếng Anh."""
    seen = mount_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"text": " Chào mọi người", "usage": {}}),
    )

    await stt.transcribe_chunk(b"fake-audio-bytes", "chunk.webm")

    body = seen[0].content.decode("utf-8", errors="ignore")
    assert 'name="language"' in body
    assert "vi" in body


@pytest.mark.asyncio
async def test_transcribe_chunk_bo_language_khi_setting_rong(
    monkeypatch: pytest.MonkeyPatch, stt_settings
):
    """Để stt_language rỗng là tắt chủ đích: request không được có field language."""
    monkeypatch.setattr(stt_settings, "stt_language", "", raising=False)
    seen = mount_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"text": " Hello everyone", "usage": {}}),
    )

    await stt.transcribe_chunk(b"fake-audio-bytes", "chunk.webm")

    body = seen[0].content.decode("utf-8", errors="ignore")
    assert 'name="language"' not in body


@pytest.mark.asyncio
async def test_transcribe_chunk_401_khong_lo_api_key(monkeypatch: pytest.MonkeyPatch):
    """Lỗi 401 phải thành RuntimeError và tuyệt đối không kèm khoá API."""
    mount_transport(
        monkeypatch,
        lambda request: httpx.Response(
            401,
            text=f"Invalid api key {FAKE_API_KEY}",
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        await stt.transcribe_chunk(b"fake-audio-bytes", "chunk.mp3")

    message = str(exc_info.value)
    assert FAKE_API_KEY not in message
    assert "401" in message


@pytest.mark.asyncio
async def test_transcribe_chunk_500_raises_runtime_error(monkeypatch: pytest.MonkeyPatch):
    """Lỗi 500 phía dịch vụ cũng phải quy về RuntimeError chứ không ném lỗi httpx."""
    mount_transport(monkeypatch, lambda request: httpx.Response(500, text="internal error"))

    with pytest.raises(RuntimeError) as exc_info:
        await stt.transcribe_chunk(b"fake-audio-bytes", "chunk.mp3")

    assert "500" in str(exc_info.value)


def test_build_turns_sorts_by_offset():
    """Chunk về không đúng thứ tự vẫn phải ra transcript theo thời gian tăng dần."""
    turns = stt.build_turns(
        [
            ("Tôi", 60_000, "Câu thứ ba"),
            ("Người khác", 0, "Câu đầu tiên"),
            ("Tôi", 30_000, "Câu thứ hai"),
        ]
    )

    assert [turn.offset_ms for turn in turns] == [0, 30_000, 60_000]
    assert [turn.text for turn in turns] == ["Câu đầu tiên", "Câu thứ hai", "Câu thứ ba"]


def test_build_turns_merges_same_speaker_within_gap():
    """Cùng người nói, cách 20s (<25s) thì gộp thành một lượt, offset lấy chunk đầu."""
    turns = stt.build_turns(
        [
            ("Tôi", 5_000, "Phần đầu"),
            ("Tôi", 25_000, "phần sau"),
        ]
    )

    assert len(turns) == 1
    assert turns[0] == stt.Turn("Tôi", 5_000, "Phần đầu phần sau")


def test_build_turns_khong_gop_khi_cach_30s():
    """Khoảng lặng 30s vượt ngưỡng nên phải tách thành hai lượt."""
    turns = stt.build_turns(
        [
            ("Tôi", 0, "Phần đầu"),
            ("Tôi", 30_000, "Phần sau"),
        ]
    )

    assert len(turns) == 2
    assert turns[0].offset_ms == 0
    assert turns[1].offset_ms == 30_000


def test_build_turns_khong_gop_khi_khac_speaker():
    """Hai người nói sát nhau vẫn là hai lượt, không được nhập chung."""
    turns = stt.build_turns(
        [
            ("Tôi", 0, "Chào anh"),
            ("Người khác", 1_000, "Chào bạn"),
        ]
    )

    assert [turn.speaker for turn in turns] == ["Tôi", "Người khác"]
    assert len(turns) == 2


def test_build_turns_bo_chunk_rong():
    """Chunk rỗng hoặc chỉ khoảng trắng là đoạn im lặng, phải bị loại bỏ."""
    turns = stt.build_turns(
        [
            ("Tôi", 0, ""),
            ("Tôi", 40_000, "   "),
            ("Tôi", 80_000, "Có nội dung"),
        ]
    )

    assert len(turns) == 1
    assert turns[0].text == "Có nội dung"
    assert turns[0].offset_ms == 80_000


def test_build_turns_list_rong():
    """Không có chunk nào thì trả list rỗng chứ không lỗi."""
    assert stt.build_turns([]) == []


def test_turns_to_transcript_format():
    """Mỗi dòng đúng dạng [mm:ss] speaker: text."""
    transcript = stt.turns_to_transcript(
        [
            stt.Turn("Tôi", 65_000, "Mình mở đầu"),
            stt.Turn("Người khác", 0, "Ừ mình nghe"),
        ]
    )

    assert transcript == "[01:05] Tôi: Mình mở đầu\n[00:00] Người khác: Ừ mình nghe"


def test_turns_to_transcript_vuot_mot_gio():
    """Họp dài hơn một tiếng thì phút tiếp tục tăng, không quay vòng về 0."""
    transcript = stt.turns_to_transcript([stt.Turn("Tôi", 4_512_000, "Chốt lại")])

    assert transcript == "[75:12] Tôi: Chốt lại"
