"""TAPB-122 — chuyển JSON của DiscordChatExporter sang đúng shape Discord API.

Thay cho `scripts/xlsx_to_discord_raw.py`: bản xlsx chỉ có 6 cột nên phải bịa
message id, bịa author id và đoán múi giờ. Bản JSON của DCE giữ id thật, guild
id, reply, reaction, sticker và thread — không còn chỗ nào phải đoán.

    python scripts/discord/dce_to_raw.py <file_dce.json> [-o ra.json]
    python scripts/discord/dce_to_raw.py <thư_mục_run> -o <thư_mục_ra>

Đầu ra giống `scripts/discord_fetch_raw.py` để pipeline phía sau không cần biết
dữ liệu tới từ bot hay từ DCE.

Những gì DCE có mà Discord API không có chỗ chứa — nickname trong server, role
của người gửi, ai đã thả reaction — nằm dưới khóa `_dce`. Bỏ mọi khóa `_dce` đi
là còn lại đúng payload API. Bản DCE gốc vẫn giữ nguyên trong kho raw nên `_dce`
chỉ cần mang phần hay dùng, không cần chép lại tất cả.

Bốn trường không lấy được nguyên bản, liệt kê luôn trong `_dce.derived`:

- `mention_roles` suy từ `<@&id>` trong nội dung, DCE không tách riêng.
- `mention_everyone` suy từ chuỗi @everyone/@here trong nội dung.
- `referenced_message` luôn None; DCE chỉ cho id của tin được trả lời, join lại
  bằng `message_reference.message_id` trong cùng file.
- `author.avatar` moi từ URL CDN; ai để avatar mặc định thì không có hash.

Đầu ra chứa nội dung chat thật nên không commit; `.gitignore` đã chặn `data/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

CHANNEL_KIND: dict[str, int] = {
    "GuildTextChat": 0,
    "DirectTextChat": 1,
    "GuildVoiceChat": 2,
    "DirectGroupTextChat": 3,
    "GuildCategory": 4,
    "GuildNews": 5,
    "GuildNewsThread": 10,
    "GuildPublicThread": 11,
    "GuildPrivateThread": 12,
    "GuildStageVoice": 13,
    "GuildDirectory": 14,
    "GuildForum": 15,
}

MESSAGE_KIND: dict[str, int] = {
    "Default": 0,
    "RecipientAdd": 1,
    "RecipientRemove": 2,
    "Call": 3,
    "ChannelNameChange": 4,
    "ChannelIconChange": 5,
    "ChannelPinnedMessage": 6,
    "GuildMemberJoin": 7,
    "ThreadCreated": 18,
    "Reply": 19,
    "ThreadStarterMessage": 21,
}

THREAD_KINDS = {10, 11, 12}

ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
AVATAR_HASH_RE = re.compile(r"/avatars/[^/]+/(a_)?([0-9a-fA-F]+)\.")

DERIVED_NOTES = [
    "mention_roles suy từ <@&id> trong content",
    "mention_everyone suy từ chuỗi @everyone/@here trong content",
    "referenced_message luôn None, join bằng message_reference.message_id",
    "author.avatar moi từ avatarUrl, avatar mặc định thì None",
]


def to_kind(value: Any, bang: dict[str, int]) -> int | None:
    """Đổi tên loại của DCE sang số của API; DCE trả số thô khi nó chưa đặt tên."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value in bang:
            return bang[value]
        if value.isdigit():
            return int(value)
    return None


def to_utc(raw: str | None) -> str | None:
    """Đưa mốc thời gian của DCE về UTC, giữ nguyên chuỗi nếu không đọc được."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).astimezone(timezone.utc).isoformat()
    except ValueError:
        return raw


def to_color(raw: str | None) -> int | None:
    """Đổi màu dạng #RRGGBB của DCE sang số nguyên như Discord API dùng."""
    if not raw or not raw.startswith("#"):
        return None
    try:
        return int(raw[1:7], 16)
    except ValueError:
        return None


def avatar_hash(url: str | None) -> str | None:
    """Moi hash avatar khỏi URL CDN; avatar mặc định không có hash nên trả None."""
    if not url:
        return None
    found = AVATAR_HASH_RE.search(url)
    if not found:
        return None
    return (found.group(1) or "") + found.group(2)


def to_author(raw: dict[str, Any]) -> dict[str, Any]:
    """Dựng user object của Discord API từ author của DCE.

    Chỗ lệch cần biết trước khi tin vào `global_name`: DCE gộp nickname riêng
    trong server và display name toàn cục vào chung một trường `nickname`. Tên
    kiểu "T004 - Nguyễn Văn A - 01234" nhiều khả năng là nickname bắt buộc của
    server chứ không phải global name thật của tài khoản. Đặt vào `global_name`
    để pipeline chạy như với dữ liệu bot, giá trị gốc giữ ở `_dce.nickname`.
    """
    return {
        "id": raw.get("id"),
        "username": raw.get("name"),
        "global_name": raw.get("nickname"),
        "discriminator": raw.get("discriminator") or "0",
        "avatar": avatar_hash(raw.get("avatarUrl")),
        "bot": bool(raw.get("isBot")),
        "_dce": {
            "nickname": raw.get("nickname"),
            "color": raw.get("color"),
            "avatar_url": raw.get("avatarUrl"),
            "roles": raw.get("roles") or [],
        },
    }


def to_attachment(raw: dict[str, Any]) -> dict[str, Any]:
    """Đổi attachment sang key của API; kích thước ảnh và content_type thì DCE không có."""
    url = raw.get("url") or ""
    return {
        "id": raw.get("id"),
        "filename": raw.get("fileName"),
        "url": url,
        "proxy_url": url.replace("cdn.discordapp.com", "media.discordapp.net", 1) or None,
        "size": raw.get("fileSizeBytes"),
        "content_type": None,
    }


def _embed_media(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if not node:
        return None
    return {"url": node.get("url"), "width": node.get("width"), "height": node.get("height")}


def to_embed(raw: dict[str, Any]) -> dict[str, Any]:
    """Đổi embed sang key snake_case của API, phần riêng của DCE để dưới `_dce`."""
    author = raw.get("author")
    footer = raw.get("footer")
    return {
        "title": raw.get("title"),
        "description": raw.get("description"),
        "url": raw.get("url"),
        "timestamp": to_utc(raw.get("timestamp")),
        "color": to_color(raw.get("color")),
        "author": (
            {"name": author.get("name"), "url": author.get("url"), "icon_url": author.get("iconUrl")}
            if author
            else None
        ),
        # DCE gọi dòng chữ dưới chân embed là `name`, API gọi là `text`.
        "footer": ({"text": footer.get("name"), "icon_url": footer.get("iconUrl")} if footer else None),
        "image": _embed_media(raw.get("image")),
        "thumbnail": _embed_media(raw.get("thumbnail")),
        "video": _embed_media(raw.get("video")),
        "fields": [
            {"name": f.get("name"), "value": f.get("value"), "inline": bool(f.get("isInline"))}
            for f in raw.get("fields") or []
        ],
        "_dce": {
            "images": raw.get("images") or [],
            "inline_emojis": raw.get("inlineEmojis") or [],
        },
    }


def to_reaction(raw: dict[str, Any]) -> dict[str, Any]:
    """Đổi reaction sang shape API; danh sách người thả là phần API không trả."""
    emoji = raw.get("emoji") or {}
    return {
        "count": raw.get("count"),
        "me": False,
        "emoji": {
            "id": emoji.get("id") or None,
            "name": emoji.get("name"),
            "animated": bool(emoji.get("isAnimated")),
        },
        "_dce": {"users": raw.get("users") or [], "code": emoji.get("code")},
    }


def to_sticker(raw: dict[str, Any]) -> dict[str, Any]:
    """Đổi sticker sang sticker_items; DCE ghi format bằng chữ nên giữ ở `_dce`."""
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "format_type": None,
        "_dce": {"format": raw.get("format"), "source_url": raw.get("sourceUrl")},
    }


def to_message(
    raw: dict[str, Any],
    channel_id: str | None,
    guild_id: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    """Dựng một message đúng shape API từ một message của DCE."""
    content = raw.get("content") or ""
    kind = raw.get("type")
    numeric_kind = to_kind(kind, MESSAGE_KIND)
    if numeric_kind is None:
        warnings.append(f"type tin lạ {kind!r} ở tin {raw.get('id')}")

    reference = raw.get("reference") or {}
    message_reference = None
    if reference.get("messageId"):
        message_reference = {
            "message_id": reference.get("messageId"),
            "channel_id": reference.get("channelId"),
            "guild_id": reference.get("guildId"),
        }

    return {
        "id": raw.get("id"),
        "type": numeric_kind,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "author": to_author(raw.get("author") or {}),
        "content": content,
        "timestamp": to_utc(raw.get("timestamp")),
        "edited_timestamp": to_utc(raw.get("timestampEdited")),
        "attachments": [to_attachment(a) for a in raw.get("attachments") or []],
        "embeds": [to_embed(e) for e in raw.get("embeds") or []],
        "reactions": [to_reaction(r) for r in raw.get("reactions") or []],
        "sticker_items": [to_sticker(s) for s in raw.get("stickers") or []],
        "mentions": [to_author(m) for m in raw.get("mentions") or []],
        "mention_roles": ROLE_MENTION_RE.findall(content),
        "mention_everyone": "@everyone" in content or "@here" in content,
        "pinned": bool(raw.get("isPinned")),
        "tts": False,
        "flags": 0,
        "components": [],
        "message_reference": message_reference,
        "referenced_message": None,
        "_dce": {
            "kind": kind,
            "call_ended_timestamp": to_utc(raw.get("callEndedTimestamp")),
            "inline_emojis": raw.get("inlineEmojis") or [],
            "forwarded_message": raw.get("forwardedMessage"),
            "interaction": raw.get("interaction"),
            "reference_type": reference.get("type"),
        },
    }


def to_discord_raw(dce: dict[str, Any]) -> dict[str, Any]:
    """Chuyển trọn một file export của DCE thành payload giống bot đã kéo."""
    guild = dce.get("guild") or {}
    channel = dce.get("channel") or {}
    guild_id = guild.get("id")
    channel_id = channel.get("id")

    warnings: list[str] = []
    channel_kind = channel.get("type")
    numeric_kind = to_kind(channel_kind, CHANNEL_KIND)
    if numeric_kind is None:
        warnings.append(f"type kênh lạ {channel_kind!r}")

    messages = [to_message(m, channel_id, guild_id, warnings) for m in dce.get("messages") or []]
    # API trả tin mới nhất trước, DCE ghi cũ trước — đảo lại cho khớp.
    messages.reverse()

    is_thread = numeric_kind in THREAD_KINDS

    return {
        "channel": {
            "id": channel_id,
            "type": numeric_kind,
            "guild_id": guild_id,
            "name": channel.get("name"),
            "topic": channel.get("topic"),
            # DCE đặt tên trường là `categoryId` từ thời chưa có thread, nhưng nó
            # ghi `Channel.Parent`: category với kênh thường, kênh cha với thread.
            # Trùng đúng ngữ nghĩa `parent_id` của Discord API nên map thẳng.
            "parent_id": channel.get("categoryId"),
            "last_message_id": messages[0]["id"] if messages else None,
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "dce-json",
        "messages": messages,
        "_dce": {
            "schema_version": SCHEMA_VERSION,
            "guild": guild,
            "channel_kind": channel_kind,
            "category": channel.get("category"),
            "category_id": channel.get("categoryId"),
            "is_thread": is_thread,
            "date_range": dce.get("dateRange"),
            "exported_at": dce.get("exportedAt"),
            "message_count": dce.get("messageCount"),
            "derived": DERIVED_NOTES,
            "warnings": warnings,
        },
    }


def sha256_of(path: Path) -> str:
    """Băm file để manifest truy được bản nào sinh ra bản nào."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def convert_file(src: Path, dst: Path) -> dict[str, Any]:
    """Chuyển một file DCE, ghi ra `dst`, trả về một dòng cho manifest."""
    with src.open(encoding="utf-8") as f:
        data = to_discord_raw(json.load(f))

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    messages = data["messages"]
    return {
        "channel_id": data["channel"]["id"],
        "channel_name": data["channel"]["name"],
        "channel_type": data["channel"]["type"],
        "is_thread": data["_dce"]["is_thread"],
        "guild_id": data["channel"]["guild_id"],
        "message_count": len(messages),
        # messages xếp mới nhất trước nên tin cũ nhất nằm cuối mảng.
        "first_timestamp": messages[-1]["timestamp"] if messages else None,
        "last_timestamp": messages[0]["timestamp"] if messages else None,
        "last_message_id": data["channel"]["last_message_id"],
        "source_file": src.name,
        "source_sha256": sha256_of(src),
        "output_file": dst.name,
        "output_sha256": sha256_of(dst),
        "warnings": data["_dce"]["warnings"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuyển JSON DiscordChatExporter sang shape Discord API")
    parser.add_argument("src", type=Path, help="file .json của DCE, hoặc thư mục chứa nhiều file")
    parser.add_argument("-o", "--out", type=Path, help="file hoặc thư mục đích")
    args = parser.parse_args()

    if not args.src.exists():
        sys.exit(f"Không thấy {args.src}")

    if args.src.is_file():
        dst = args.out or args.src.with_name(f"{args.src.stem}.raw.json")
        row = convert_file(args.src, dst)
        print(f"{row['message_count']} tin -> {dst}", file=sys.stderr)
        for w in row["warnings"]:
            print(f"CẢNH BÁO: {w}", file=sys.stderr)
        return

    sources = sorted(p for p in args.src.glob("*.json") if not p.name.startswith("_"))
    if not sources:
        sys.exit(f"Không có file .json nào trong {args.src}")

    out_dir = args.out or args.src.parent.parent / "normalized" / args.src.name
    rows: list[dict[str, Any]] = []
    bo_qua: list[dict[str, str]] = []
    for p in sources:
        try:
            rows.append(convert_file(p, out_dir / f"{p.stem}.json"))
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
            # File đang được DCE ghi dở, hoặc đứt giữa chừng vì mất mạng. Bỏ qua
            # và ghi lại để chạy lại sau, chứ không làm hỏng cả mẻ.
            bo_qua.append({"file": p.name, "loi": f"{type(e).__name__}: {e}"[:200]})

    if not rows:
        sys.exit(f"Không đọc được file nào trong {args.src}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.src.name,
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(args.src),
        "channels": rows,
        "skipped": bo_qua,
        "total_messages": sum(r["message_count"] for r in rows),
    }
    manifest_path = out_dir / "_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"{len(rows)} kênh · {manifest['total_messages']} tin -> {out_dir}", file=sys.stderr)
    print(f"manifest: {manifest_path}", file=sys.stderr)
    for b in bo_qua:
        print(f"BỎ QUA {b['file']}: {b['loi']}", file=sys.stderr)
    for row in rows:
        for w in row["warnings"]:
            print(f"CẢNH BÁO [{row['channel_name']}]: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
