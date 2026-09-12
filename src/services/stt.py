"""Adapter gọi STT của FPT Cloud marketplace và ghép kết quả thành transcript.

Endpoint `POST /v1/audio/transcriptions` tương thích kiểu OpenAI nhưng chỉ đọc
ba trường form là `model`, `file` và `language`. Các tham số quen thuộc còn lại
(`response_format`, `timestamp_granularities`, `stream`, `prompt`) đã đo là bị
bỏ qua hoàn toàn, và response luôn phẳng dạng `{"text": ..., "usage": ...}` —
không bao giờ có `segments` hay `words`. Vì vậy module này không gửi và cũng
không cố đọc những trường đó.

Riêng `language` thì có tác dụng thật và phải gửi: với đầu vào webm/opus, bỏ
trống nó khiến model tự dịch nội dung tiếng Việt sang tiếng Anh.

Do không có timestamp ở mức từ, thứ tự và mốc thời gian của hội thoại phải do
phía gọi cung cấp: mỗi chunk audio đi kèm người nói và offset tính từ lúc bắt
đầu ghi. `build_turns` chịu trách nhiệm ghép các chunk rời rạc đó lại thành
lượt nói cho dễ đọc.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.config import get_settings

# Trần thời gian cho một lời gọi STT. Dịch vụ chạy ~43 lần realtime nên 120s đã
# thừa cho một chunk vài phút; để cao hơn chỉ khiến lỗi mạng treo cả request.
REQUEST_TIMEOUT_SECONDS = 120.0

# Hai chunk cùng người nói cách nhau dưới ngưỡng này được coi là một mạch nói.
# 25 giây là khoảng im lặng đủ dài để người đọc thấy đây là hai lượt khác nhau.
TURN_MERGE_GAP_MS = 25_000


@dataclass(frozen=True)
class Turn:
    """Một lượt nói đã gộp: ai nói, bắt đầu ở giây thứ mấy, nói gì."""

    speaker: str
    offset_ms: int
    text: str


def _redact_secret(message: str, secret: str) -> str:
    """Thay mọi lần xuất hiện của khoá API trong chuỗi bằng dấu sao.

    Message lỗi có thể chứa lại nội dung response hoặc URL do thư viện dựng,
    và những chỗ đó từng làm rò khoá vào log. Hàm này là chốt chặn cuối cùng
    trước khi bất kỳ chuỗi nào được ném ra ngoài.
    """
    if not secret:
        return message
    return message.replace(secret, "***")


async def transcribe_chunk(audio: bytes, filename: str) -> str:
    """Gửi một chunk audio lên STT và trả về phần text đã bỏ khoảng trắng thừa.

    Cơ chế: dựng multipart với `model`, `file` và `language`, đính khoá vào
    header `Authorization`, gọi bất đồng bộ bằng `httpx.AsyncClient`. Mọi mã
    lỗi HTTP hoặc sự cố mạng đều được quy về `RuntimeError` kèm thông điệp
    tiếng Việt đã lọc khoá, để phía gọi không phải biết chi tiết của httpx.
    Response luôn phẳng nên chỉ cần đọc khoá `text`; dịch vụ trả text có một
    dấu cách ở đầu nên phải `strip()`.
    """
    settings = get_settings()
    api_key = settings.fpt_api_key
    if not api_key:
        # Không gửi "Authorization: Bearer " rỗng: nhà cung cấp trả 401 và lỗi
        # lộ ra ở tầng hoàn toàn khác với nguyên nhân thật là thiếu cấu hình.
        raise RuntimeError("Thiếu FPT_API_KEY nên không gọi được STT.")
    url = f"{settings.fpt_base_url.rstrip('/')}/v1/audio/transcriptions"

    # Chỉ gửi language khi có cấu hình: để rỗng là cách tắt chủ đích, trả về
    # hành vi auto-detect của model.
    form_data = {"model": settings.stt_model}
    if settings.stt_language:
        form_data["language"] = settings.stt_language

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                data=form_data,
                files={"file": (filename, audio)},
            )
    except httpx.HTTPError as exc:
        detail = _redact_secret(str(exc), api_key)
        raise RuntimeError(f"Không gọi được dịch vụ nhận dạng giọng nói: {detail}") from exc

    if response.status_code >= 400:
        detail = _redact_secret(response.text, api_key)
        raise RuntimeError(
            f"Dịch vụ nhận dạng giọng nói trả lỗi {response.status_code}: {detail}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Dịch vụ nhận dạng giọng nói trả về dữ liệu không đọc được") from exc

    text = payload.get("text")
    if not isinstance(text, str):
        raise RuntimeError("Dịch vụ nhận dạng giọng nói không trả về trường text")

    return text.strip()


def build_turns(chunks: list[tuple[str, int, str]]) -> list[Turn]:
    """Gộp các chunk `(speaker, offset_ms, text)` rời rạc thành danh sách lượt nói.

    Cơ chế: bỏ chunk không có nội dung thật (rỗng hoặc chỉ khoảng trắng) vì đó
    là đoạn im lặng chứ không phải lượt nói; sắp xếp lại theo offset vì chunk
    có thể về không đúng thứ tự khi transcribe song song; rồi duyệt một lượt,
    nối chunk vào lượt đang mở nếu cùng người nói và cách chunk trước dưới
    `TURN_MERGE_GAP_MS`. Khoảng cách được đo với chunk liền trước chứ không
    phải với đầu lượt, để một mạch nói dài liên tục không bị cắt vụn.
    """
    cleaned = [(speaker, offset_ms, text.strip()) for speaker, offset_ms, text in chunks if text.strip()]
    cleaned.sort(key=lambda chunk: chunk[1])

    turns: list[Turn] = []
    # Offset của chunk vừa xử lý, dùng làm mốc đo khoảng lặng cho chunk kế tiếp.
    previous_offset_ms: int | None = None
    # Các mảnh text của lượt đang mở, gom lại rồi mới nối một lần cho đỡ tốn.
    current_speaker: str | None = None
    current_offset_ms = 0
    current_parts: list[str] = []

    for speaker, offset_ms, text in cleaned:
        same_speaker = speaker == current_speaker
        close_enough = previous_offset_ms is not None and offset_ms - previous_offset_ms < TURN_MERGE_GAP_MS

        if current_parts and same_speaker and close_enough:
            current_parts.append(text)
        else:
            if current_parts and current_speaker is not None:
                turns.append(Turn(current_speaker, current_offset_ms, " ".join(current_parts)))
            current_speaker = speaker
            current_offset_ms = offset_ms
            current_parts = [text]

        previous_offset_ms = offset_ms

    if current_parts and current_speaker is not None:
        turns.append(Turn(current_speaker, current_offset_ms, " ".join(current_parts)))

    return turns


def _format_offset(offset_ms: int) -> str:
    """Đổi offset mili giây thành chuỗi `mm:ss` không giới hạn 60 phút.

    Buổi họp dài hơn một tiếng vẫn phải đọc được nên phút cứ tăng tiếp (75:12)
    thay vì quay vòng sang giờ; giây luôn hai chữ số để các dòng thẳng cột.
    """
    total_seconds = max(offset_ms, 0) // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def turns_to_transcript(turns: list[Turn]) -> str:
    """Kết xuất danh sách lượt nói thành transcript, mỗi lượt một dòng.

    Cơ chế: với mỗi lượt dựng một dòng `[mm:ss] {speaker}: {text}` rồi nối bằng
    xuống dòng. Định dạng này vừa cho người đọc vừa là đầu vào cho bước tóm tắt
    nên phải ổn định, không thêm dòng trống hay ký tự trang trí.
    """
    return "\n".join(f"[{_format_offset(turn.offset_ms)}] {turn.speaker}: {turn.text}" for turn in turns)
