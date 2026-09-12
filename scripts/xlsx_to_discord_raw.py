"""TAPB-122 — dựng raw message đúng shape Discord API từ file xlsx của DiscordChatExporter.

Dùng khi chưa có bot token. Đầu ra giống hệt `scripts/discord_fetch_raw.py`
nên pipeline phía sau không cần biết dữ liệu tới từ đâu.

    python scripts/xlsx_to_discord_raw.py <file.xlsx> [ra.json]

xlsx chỉ có 6 cột nên phải bù lại phần thiếu:

- `message_id` mất hẳn -> sinh snowflake từ mốc thời gian, giữ đúng thứ tự
  thời gian để logic phân trang `before` và dedupe chạy như hàng thật.
- `AuthorID` bị Excel lưu thành float nên mất chữ số cuối, không cứu được ->
  sinh id giả, ổn định theo tên.
- `channel_id` moi ra từ URL attachment, dạng cdn.discordapp.com/attachments/<channel_id>/...
- `guild_id`, `referenced_message`, `thread` không có trong xlsx -> để None.

Đầu ra chứa nội dung chat thật nên không commit; `.gitignore` đã chặn
discord_raw_*.json.
"""

import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DISCORD_EPOCH_MS = 1420070400000
EXCEL_EPOCH = datetime(1899, 12, 30)

# DiscordChatExporter ghi giờ theo múi giờ máy chạy nó, xlsx không lưu offset.
# Dataset cào ở Việt Nam nên gán GMT+7. Đổi hằng số này nếu cào ở nơi khác.
SOURCE_TZ = timezone(timedelta(hours=7))

REACTION_RE = re.compile(r"([^,]+?)\s*\((\d+)\)")
CDN_RE = re.compile(r"cdn\.discordapp\.com/attachments/(\d+)/(\d+)/([^?\s]+)")


def read_sheet(path: str) -> list[dict[str, str]]:
    """Đọc sheet đầu của xlsx bằng stdlib, trả về list dict theo tên cột ở dòng 1."""
    with zipfile.ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in root.iter(NS + "si")]

        rows: list[list[str]] = []
        for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(NS + "row"):
            cells: dict[str, str] = {}
            for c in row.iter(NS + "c"):
                col = re.match(r"[A-Z]+", c.get("r") or "A").group(0)
                v = c.find(NS + "v")
                if c.get("t") == "inlineStr":
                    cells[col] = "".join(t.text or "" for t in c.iter(NS + "t"))
                elif v is None:
                    cells[col] = ""
                elif c.get("t") == "s":
                    cells[col] = strings[int(v.text)]
                else:
                    cells[col] = v.text or ""
            rows.append([cells.get(chr(ord("A") + i), "") for i in range(6)])

    header, *body = rows
    return [dict(zip(header, r, strict=False)) for r in body]


def snowflake(when: datetime, nonce: int) -> str:
    """Sinh snowflake giữ đúng thứ tự thời gian, 22 bit thấp dùng làm bộ đếm."""
    ms = int(when.timestamp() * 1000) - DISCORD_EPOCH_MS
    return str((ms << 22) | (nonce & 0x3FFFFF))


def fake_author_id(name: str) -> str:
    """Id giả nhưng ổn định theo tên, để dedupe theo người vẫn chạy."""
    digest = int(hashlib.sha256(name.encode()).hexdigest()[:15], 16)
    return str(10**17 + digest % 10**17)


def parse_reactions(raw: str) -> list[dict]:
    return [
        {"emoji": {"id": None, "name": name.strip()}, "count": int(count), "me": False}
        for name, count in REACTION_RE.findall(raw)
    ]


def parse_attachments(raw: str) -> list[dict]:
    out = []
    for channel_id, attachment_id, filename in CDN_RE.findall(raw):
        # Bỏ tham số ex/is/hm: chữ ký CDN đã hết hạn và không nên lưu lại.
        out.append(
            {
                "id": attachment_id,
                "filename": filename,
                "url": f"https://cdn.discordapp.com/attachments/{channel_id}/{attachment_id}/{filename}",
                "proxy_url": f"https://media.discordapp.net/attachments/{channel_id}/{attachment_id}/{filename}",
                "size": None,
                "content_type": None,
            }
        )
    return out


def to_discord_raw(rows: list[dict[str, str]], channel_name: str) -> dict:
    """Chuyển các dòng xlsx thành payload giống GET /channels/{id}/messages."""
    # Một file export có thể trải nhiều kênh/thread. Kênh của từng tin chỉ suy ra
    # được khi tin đó có attachment; tin không có attachment thì lấy kênh hay gặp
    # nhất làm mặc định — đây là suy đoán, không phải dữ liệu thật.
    seen = Counter(m.group(1) for r in rows if (m := CDN_RE.search(r.get("Attachments", ""))))
    fallback_channel_id = seen.most_common(1)[0][0] if seen else None

    messages = []
    for i, row in enumerate(rows):
        author = row.get("Author", "").strip()
        if not author:
            continue
        found = CDN_RE.search(row.get("Attachments", ""))
        channel_id = found.group(1) if found else fallback_channel_id
        when = (EXCEL_EPOCH + timedelta(days=float(row["Date"]))).replace(tzinfo=SOURCE_TZ)
        username, _, discriminator = author.partition("#")
        messages.append(
            {
                "id": snowflake(when, i),
                "type": 0,
                "channel_id": channel_id,
                "guild_id": None,
                "author": {
                    "id": fake_author_id(author),
                    "username": username,
                    "global_name": None,
                    "discriminator": discriminator or "0",
                    # DiscordChatExporter chỉ còn giữ #dddd cho tài khoản bot.
                    "bot": bool(discriminator),
                },
                "content": row.get("Content", ""),
                "timestamp": when.astimezone(timezone.utc).isoformat(),
                "edited_timestamp": None,
                "attachments": parse_attachments(row.get("Attachments", "")),
                "reactions": parse_reactions(row.get("Reactions", "")),
                "embeds": [],
                "mentions": [],
                "mention_roles": [],
                "mention_everyone": False,
                "pinned": False,
                "tts": False,
                "flags": 0,
                "message_reference": None,
                "referenced_message": None,
            }
        )

    # API trả tin mới nhất trước, xlsx xếp cũ trước — đảo lại cho khớp.
    messages.reverse()
    return {
        "channel": {"id": fallback_channel_id, "type": 0, "guild_id": None, "name": channel_name},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "xlsx-discordchatexporter",
        "channel_ids_seen": sorted(seen),
        "messages": messages,
    }


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    src = sys.argv[1]
    rows = read_sheet(src)
    data = to_discord_raw(rows, channel_name=src.rsplit("/", 1)[-1].removesuffix(".xlsx"))
    out_path = sys.argv[2] if len(sys.argv) > 2 else f"discord_raw_{data['channel']['id']}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    bots = sum(1 for m in data["messages"] if m["author"]["bot"])
    print(f"{len(data['messages'])} tin -> {out_path}", file=sys.stderr)
    print(f"channel_id={data['channel']['id']} · {bots} tin của bot", file=sys.stderr)
    print("Thiếu: guild_id, referenced_message, thread, embeds — xlsx không có.", file=sys.stderr)
    if len(data["channel_ids_seen"]) > 1:
        print(
            f"CẢNH BÁO: export trải {len(data['channel_ids_seen'])} kênh/thread. Tin không có "
            "attachment bị gán kênh mặc định — channel_id của chúng là suy đoán.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
