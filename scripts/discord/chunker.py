"""TAPB-122 — gom tin nhắn Discord đã chuẩn hóa thành chunk để đưa vào index.

    python scripts/discord/chunker.py data/discord/normalized/<run_id>

Hai chế độ, chọn theo hình dạng thật của kênh chứ không dùng chung một luật.
Số liệu ở docs/projects/engineering/discord-chunking-spike.md.

`session` — dùng cho thread lớp học và lab. Hoạt động dồn vào buổi học nên ranh giới
tự nhiên là ngày, không phải khoảng lặng. Ngày đông thì hai cách cho kết quả như
nhau; ngày thưa thì cắt theo khoảng lặng băm 14 tin thành 6 mẩu.

`thread` — dùng cho kênh chat chung. Một phiên 30 phút ở đó chứa tới 645 mạch reply
riêng biệt của 471 người, nên gom theo thời gian chỉ trộn các mẩu chuyện rời vào
nhau. Đơn vị đúng là mạch reply, cộng những tin lẻ đủ dài để tự đứng một mình.

Tin bị loại khỏi index vẫn nằm nguyên trong `normalized/`. Chunker không xóa gì,
chỉ chọn cái gì được đánh index — bằng chứng phải còn đủ để trích dẫn.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

PROGRAM_TZ_OFFSET = timedelta(hours=7)

# Ngân sách ký tự cho một chunk. Chọn theo p90 của các chunk đo được, chưa đối
# chiếu với cửa sổ của model embedding — xem CH-03 trong spike.
CHAR_BUDGET = 1200

# Tin lẻ ngắn hơn ngưỡng này không vào index. Đo trên kênh chung: bỏ 58% số tin
# mà chỉ mất một phần tư khối lượng chữ, phần mất là "Em cảm ơn ạ", "Vì kẹt xe ạ".
ORPHAN_MIN_CHARS = 60

# Dưới ngưỡng này thì cả kênh gom thành một nhóm, khỏi chia buổi hay chia mạch.
SMALL_CHANNEL_MAX = 200

THREAD_KINDS = {10, 11, 12}
KEPT_MESSAGE_TYPES = {0, 19}


def local_time(iso: str) -> datetime:
    """Đổi timestamp UTC sang giờ chương trình để chia buổi cho đúng ngày."""
    return datetime.fromisoformat(iso).astimezone(timezone.utc) + PROGRAM_TZ_OFFSET


def content_of(msg: dict[str, Any]) -> str:
    return (msg.get("content") or "").strip()


def is_kept(msg: dict[str, Any]) -> bool:
    """Tin hệ thống và tin của bot không phải bằng chứng hội thoại."""
    if msg.get("type") not in KEPT_MESSAGE_TYPES:
        return False
    if (msg.get("author") or {}).get("bot"):
        return False
    return bool(content_of(msg) or msg.get("attachments"))


def pick_mode(channel: dict[str, Any], message_count: int) -> str:
    """Chọn chế độ gom theo loại kênh và khối lượng."""
    if message_count < SMALL_CHANNEL_MAX:
        return "whole"
    if channel.get("type") in THREAD_KINDS:
        return "session"
    return "thread"


def reply_tree(msgs: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Dựng quan hệ cha con từ message_reference, chỉ giữ cạnh trỏ vào trong corpus."""
    present = {m["id"] for m in msgs}
    parent: dict[str, str] = {}
    for m in msgs:
        p = (m.get("message_reference") or {}).get("message_id")
        if p and p in present:
            parent[m["id"]] = p
    children: dict[str, list[str]] = defaultdict(list)
    for c, p in parent.items():
        children[p].append(c)
    return parent, children


def group_by_session(msgs: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Gom theo ngày giờ địa phương, vì lớp và lab chỉ chạy trong buổi."""
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in msgs:
        by_day[local_time(m["timestamp"]).date().isoformat()].append(m)
    return sorted(by_day.items())


def group_by_thread(
    msgs: list[dict[str, Any]],
) -> tuple[list[tuple[str, list[dict[str, Any]]]], list[dict[str, Any]]]:
    """Gom theo mạch reply; tin lẻ đủ dài đứng riêng, tin lẻ ngắn bị loại."""
    by_id = {m["id"]: m for m in msgs}
    parent, children = reply_tree(msgs)

    def root(mid: str) -> str:
        while mid in parent:
            mid = parent[mid]
        return mid

    in_thread: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in msgs:
        if m["id"] in parent or children.get(m["id"]):
            in_thread[root(m["id"])].append(m)

    already_in = {m["id"] for v in in_thread.values() for m in v}
    orphans_kept, orphans_dropped = [], []
    for m in msgs:
        if m["id"] in already_in:
            continue
        (orphans_kept if len(content_of(m)) >= ORPHAN_MIN_CHARS else orphans_dropped).append(m)

    groups = [(f"thread:{k}", sorted(v, key=lambda m: m["timestamp"])) for k, v in in_thread.items()]
    groups += [(f"orphan:{m['id']}", [m]) for m in orphans_kept]
    groups.sort(key=lambda kv: kv[1][0]["timestamp"])
    _ = by_id
    return groups, orphans_dropped


def pack_by_budget(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cắt một nhóm thành nhiều chunk khi vượt ngân sách, không gộp qua nhóm."""
    packs, cur, size = [], [], 0
    for m in items:
        c = len(content_of(m)) + 24
        if cur and size + c > CHAR_BUDGET:
            packs.append(cur)
            cur, size = [], 0
        cur.append(m)
        size += c
    if cur:
        packs.append(cur)
    return packs


def render_text(msgs: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> str:
    """Kết xuất chunk thành chữ, giữ ai nói gì và tin nào trả lời tin nào."""
    lines = []
    in_chunk = {m["id"] for m in msgs}
    for m in msgs:
        a = m.get("author") or {}
        name = a.get("global_name") or a.get("username") or "?"
        t = local_time(m["timestamp"]).strftime("%Y-%m-%d %H:%M")
        prefix = ""
        ref = (m.get("message_reference") or {}).get("message_id")
        if ref:
            root = by_id.get(ref)
            if root and ref not in in_chunk:
                ga = (root.get("author") or {}).get("global_name") or "?"
                prefix = f"↳ trả lời {ga}: {content_of(root)[:40]!r} — "
            elif root:
                prefix = "↳ "
        attach_note = ""
        if m.get("attachments"):
            attach_note = f" [{len(m['attachments'])} tệp đính kèm]"
        lines.append(f"[{t}] {name}: {prefix}{content_of(m)}{attach_note}")
    return "\n".join(lines)


def chunk_channel(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Gom một kênh đã chuẩn hóa thành danh sách chunk kèm số liệu."""
    ch = data["channel"]
    all_msgs = sorted(data["messages"], key=lambda m: m["timestamp"])
    msgs = [m for m in all_msgs if is_kept(m)]
    by_id = {m["id"]: m for m in all_msgs}

    mode = pick_mode(ch, len(msgs))
    orphans_dropped: list[dict[str, Any]] = []
    if mode == "session":
        groups = group_by_session(msgs)
    elif mode == "thread":
        groups, orphans_dropped = group_by_thread(msgs)
    else:
        groups = [("whole_channel", msgs)] if msgs else []

    chunks = []
    for group_key, items in groups:
        for packs in pack_by_budget(items):
            if not packs:
                continue
            authors_seen = {}
            for m in packs:
                a = m.get("author") or {}
                if a.get("id") and a["id"] not in authors_seen:
                    authors_seen[a["id"]] = {
                        "id": a["id"],
                        "name": a.get("global_name") or a.get("username"),
                        "roles": [r.get("name") for r in (a.get("_dce") or {}).get("roles") or []],
                    }
            text = render_text(packs, by_id)
            chunks.append(
                {
                    "chunk_id": f"{ch['id']}:{len(chunks):04d}",
                    "channel_id": ch["id"],
                    "channel_name": ch.get("name"),
                    "guild_id": ch.get("guild_id"),
                    "parent_id": ch.get("parent_id"),
                    "is_thread": ch.get("type") in THREAD_KINDS,
                    "mode": mode,
                    "group_key": group_key,
                    "message_ids": [m["id"] for m in packs],
                    "first_timestamp": packs[0]["timestamp"],
                    "last_timestamp": packs[-1]["timestamp"],
                    "authors": list(authors_seen.values()),
                    "message_count": len(packs),
                    "char_count": sum(len(content_of(m)) for m in packs),
                    "deep_link": f"https://discord.com/channels/{ch.get('guild_id')}/{ch['id']}/{packs[0]['id']}",
                    "text": text,
                }
            )

    stats = {
        "channel_id": ch["id"],
        "channel_name": ch.get("name"),
        "mode": mode,
        "messages_total": len(all_msgs),
        "messages_kept": len(msgs),
        "orphans_dropped": len(orphans_dropped),
        "messages_indexed": sum(c["message_count"] for c in chunks),
        "chunk_count": len(chunks),
        "avg_chars": round(sum(c["char_count"] for c in chunks) / len(chunks)) if chunks else 0,
    }
    return chunks, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Gom tin Discord đã chuẩn hóa thành chunk")
    parser.add_argument("src", type=Path, help="thư mục normalized/<run_id> hoặc một file .json")
    parser.add_argument("-o", "--out", type=Path, help="thư mục đích, mặc định chunks/<run_id>")
    parser.add_argument("--preview", type=int, default=0, help="in ra N chunk mẫu rồi thoát, không ghi file")
    args = parser.parse_args()

    if not args.src.exists():
        sys.exit(f"Không thấy {args.src}")

    sources = [args.src] if args.src.is_file() else sorted(
        p for p in args.src.glob("*.json") if not p.name.startswith("_")
    )
    if not sources:
        sys.exit(f"Không có file .json nào trong {args.src}")

    all_chunks: list[dict[str, Any]] = []
    table: list[dict[str, Any]] = []
    for p in sources:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"BỎ QUA {p.name}: {e}", file=sys.stderr)
            continue
        chunks, stats = chunk_channel(data)
        all_chunks += chunks
        table.append(stats)

    if args.preview:
        for c in all_chunks[: args.preview]:
            print(f"\n{'-' * 72}")
            print(
                f"{c['chunk_id']} · {c['channel_name']} · chế độ {c['mode']} · nhóm {c['group_key']}"
                f" · {c['message_count']} tin · {c['char_count']} ký tự"
            )
            print(f"{'-' * 72}")
            print(c["text"][:1400])
        return

    out_dir = args.out or args.src.parent.parent / "chunks" / args.src.name
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": args.src.name,
        "chunked_at": datetime.now(timezone.utc).isoformat(),
        "ngan_sach_ky_tu": CHAR_BUDGET,
        "nguong_tin_le": ORPHAN_MIN_CHARS,
        "nguong_kenh_nho": SMALL_CHANNEL_MAX,
        "tong_chunk": len(all_chunks),
        "channel": sorted(table, key=lambda r: -r["messages_total"]),
    }
    with (out_dir / "_chunks_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"{len(table)} kênh · {len(all_chunks)} chunk -> {out_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
