"""Lớp gọi HTTP dùng chung cho các connector Google, có chặn kích thước phản hồi.

Cắt nội dung SAU khi đã tải xong không bảo vệ được gì ngoài túi tiền token:
người dùng chỉ cần trỏ vào một file khổng lồ là bơm được RAM và băng thông của
server, dù chuỗi cuối cùng đưa cho LLM vẫn bị cắt về 20.000 ký tự. Nên chặn
ngay ở tầng request: xem `Content-Length` trước khi đọc, và đọc theo luồng để
huỷ giữa chừng khi máy chủ không khai báo độ dài.
"""

from __future__ import annotations

import json

import httpx

from src.config import get_settings
from src.connectors.base import ConnectorAPIError


class GoogleResponseTooLargeError(ConnectorAPIError):
    """File nguồn lớn hơn ngưỡng cho phép — lỗi của đầu vào, không phải của Google.

    Cố ý KHÔNG kế thừa GoogleDocsAPIError/GoogleSheetsAPIError: hai lỗi đó map
    sang 502 (Google hỏng), còn lỗi này map sang 422 (file người dùng chọn
    không dùng được). Là lớp anh em nên thứ tự `except` ở tầng API không thể
    vô tình nuốt nó thành 502.
    """


def _megabytes(value: int) -> str:
    return f"{value / 1_000_000:.1f} MB"


def _too_large(source: str, *, observed: int | None, cap: int, complete: bool) -> GoogleResponseTooLargeError:
    """Thông báo phải nói rõ vượt bao nhiêu, để người dùng biết cần tách nhỏ cỡ nào."""
    if complete and observed is not None:
        size = f"nặng {_megabytes(observed)}"
    elif observed is not None:
        size = f"đã vượt {_megabytes(observed)} mà chưa hết"
    else:
        size = "vượt ngưỡng"
    return GoogleResponseTooLargeError(
        f"File {source} quá lớn để xử lý: dữ liệu tải về {size}, "
        f"trong khi ngưỡng cho phép là {_megabytes(cap)}. "
        "Hãy tách nhỏ file hoặc chọn phạm vi hẹp hơn rồi thử lại."
    )


async def fetch_json_capped(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    source: str,
) -> tuple[int, dict]:
    """GET một endpoint Google, trả (status_code, body đã parse JSON).

    Ném GoogleResponseTooLargeError NGAY khi phản hồi vượt
    `google_api_max_response_bytes`, không đợi tải xong. Trả status_code thô để
    caller giữ nguyên thông điệp lỗi riêng của từng API.
    """
    cap = get_settings().google_api_max_response_bytes
    async with client.stream("GET", url, params=params) as response:
        if response.status_code != 200:
            # Thân lỗi của Google luôn nhỏ; đọc hết để đóng kết nối sạch sẽ.
            await response.aread()
            return response.status_code, {}

        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > cap:
            raise _too_large(source, observed=int(declared), cap=cap, complete=True)

        buffer = bytearray()
        async for chunk in response.aiter_bytes():
            buffer.extend(chunk)
            if len(buffer) > cap:
                raise _too_large(source, observed=len(buffer), cap=cap, complete=False)

    try:
        body = json.loads(bytes(buffer))
    except json.JSONDecodeError as exc:
        raise ConnectorAPIError(f"{source} trả về dữ liệu không phải JSON hợp lệ.") from exc
    if not isinstance(body, dict):
        raise ConnectorAPIError(f"{source} trả về dữ liệu không hợp lệ.")
    return response.status_code, body
