"""TAPB-122 — kéo toàn bộ raw message của một kênh Discord, chưa chuẩn hóa.

Dùng bot token vì OAuth2 user token không đọc được nội dung kênh: scope
`messages.read` chỉ chạy qua RPC cục bộ, không dùng được cho web app.

    DISCORD_BOT_TOKEN=... python scripts/discord_fetch_raw.py <channel_id> [max] [ra.json]

Ghi ra JSON gồm object kênh (để có `guild_id` dựng deep link) và mảng message
giữ nguyên payload Discord trả về. Không đụng vào nội dung message.

Bot phải ở trong server, có quyền View Channel + Read Message History, và bật
Message Content Intent trong Developer Portal — thiếu intent thì trường
`content` trả về rỗng mà API vẫn trả 200.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import httpx

API = "https://discord.com/api/v10"
PAGE = 100


async def _get(client: httpx.AsyncClient, path: str, params: dict | None = None):
    """GET một endpoint Discord, tự chờ và thử lại khi bị rate limit."""
    while True:
        response = await client.get(f"{API}{path}", params=params)
        if response.status_code == 429:
            await asyncio.sleep(float(response.headers.get("retry-after", 1)))
            continue
        response.raise_for_status()
        return response.json()


async def fetch_channel_raw(
    channel_id: str,
    token: str,
    max_messages: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Trả về object kênh và toàn bộ message lấy được, mới nhất trước."""
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=30, transport=transport) as client:
        channel = await _get(client, f"/channels/{channel_id}")

        messages: list[dict] = []
        before: str | None = None
        while len(messages) < max_messages:
            params: dict = {"limit": min(PAGE, max_messages - len(messages))}
            if before:
                params["before"] = before
            page = await _get(client, f"/channels/{channel_id}/messages", params)
            if not page:
                break
            messages.extend(page)
            before = page[-1]["id"]
            if len(page) < params["limit"]:
                break

        return {
            "channel": channel,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
        }


def thieu_content(message: dict) -> bool:
    """Tin lẽ ra phải có chữ mà lại rỗng — dấu hiệu chưa bật Message Content Intent.

    Chỉ tin thường (0) và tin trả lời (19) mới bắt buộc có chữ. Tin hệ thống như
    thành viên tham gia (7) hay ghim tin (6) vốn dĩ content rỗng, và tin chỉ gửi
    ảnh hay sticker cũng vậy — đếm cả mấy loại đó là báo động giả.
    """
    if message.get("type") not in (0, 19):
        return False
    if message.get("content"):
        return False
    return not (message.get("attachments") or message.get("embeds") or message.get("sticker_items"))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        sys.exit("Thiếu DISCORD_BOT_TOKEN trong môi trường.")

    channel_id = sys.argv[1]
    max_messages = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    out_path = sys.argv[3] if len(sys.argv) > 3 else f"discord_raw_{channel_id}.json"

    # ponytail: gom hết vào RAM rồi ghi một lần. Kênh mẫu vài nghìn tin thì thoải
    # mái; khi kéo kênh thật hàng trăm nghìn tin thì đổi sang ghi NDJSON từng trang.
    data = asyncio.run(fetch_channel_raw(channel_id, token, max_messages))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    guild_id = data["channel"].get("guild_id")
    empty = sum(1 for m in data["messages"] if thieu_content(m))
    print(f"{len(data['messages'])} tin -> {out_path}", file=sys.stderr)
    print(f"kênh #{data['channel'].get('name')} guild={guild_id}", file=sys.stderr)
    if data["messages"]:
        print(f"khóa của tin đầu: {sorted(data['messages'][0])}", file=sys.stderr)
    if empty:
        print(
            f"CẢNH BÁO: {empty} tin có content rỗng — nhiều khả năng chưa bật Message Content Intent.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
