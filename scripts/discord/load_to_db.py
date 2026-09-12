"""TAPB-122 — nạp run Discord đã chuẩn hóa và chunk vào Postgres.

    python scripts/discord/load_to_db.py <run_id>

Chạy lại cùng một run không tạo bản trùng: item khoá theo (provider, external_id),
chunk khoá theo (run_id, chunk_key). Đây là yêu cầu FR-012.

Tin sửa lại sinh mã băm mới nên vào `source_item_versions` thành phiên bản mới,
không ghi đè bản cũ (FR-013).

Postgres không có cấu hình full-text cho tiếng Việt nên cột tsvector dùng
`simple` kèm `unaccent`, để "han nop" khớp được "hạn nộp". Bù lại mất stemming,
nhánh vector phải gánh nhiều hơn — xem discord-chunking-spike.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from src.db import Base, engine  # noqa: E402
from src.models import Chunk, ChunkItem, SourceItem, SourceItemVersion, SourceScope  # noqa: E402
from src.services.program_access import reconcile_all_discord_connections  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PROVIDER = "discord"

DDL_FTS = """
CREATE OR REPLACE FUNCTION mondaiy_fts(txt text) RETURNS tsvector AS $$
  SELECT to_tsvector('simple', unaccent(coalesce(txt, '')))
$$ LANGUAGE sql IMMUTABLE;

ALTER TABLE chunks
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (mondaiy_fts(text)) STORED;

CREATE INDEX IF NOT EXISTS ix_chunks_fts ON chunks USING GIN (fts);
CREATE INDEX IF NOT EXISTS ix_chunks_trgm ON chunks USING GIN (text gin_trgm_ops);
"""


def content_hash_of(*phan: Any) -> str:
    """Mã băm nội dung để phát hiện tin đã sửa."""
    h = hashlib.sha256()
    for p in phan:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


def init_schema() -> None:
    """Tạo bảng rồi thêm cột FTS sinh tự động mà SQLAlchemy không mô tả được."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(DDL_FTS)


def upsert_scope(db: Session, ch: dict[str, Any]) -> SourceScope:
    """Lấy hoặc tạo phạm vi nguồn cho một kênh; mức để mặc định B."""
    scope = (
        db.query(SourceScope)
        .filter_by(provider=PROVIDER, external_id=ch["id"])
        .one_or_none()
    )
    if scope is None:
        scope = SourceScope(provider=PROVIDER, external_id=ch["id"])
        db.add(scope)
    scope.name = ch.get("name")
    scope.parent_external_id = ch.get("parent_id")
    scope.guild_external_id = ch.get("guild_id")
    scope.kind = ch.get("type")
    scope.is_thread = ch.get("type") in {10, 11, 12}
    db.flush()
    return scope


def upsert_item(db: Session, m: dict[str, Any], scope: SourceScope, run_id: str, fetched: datetime) -> int:
    """Ghi một tin nhắn, tạo phiên bản mới nếu nội dung đã đổi."""
    author = m.get("author") or {}
    content = m.get("content") or ""
    updated = datetime.fromisoformat(m.get("edited_timestamp") or m["timestamp"])
    h = content_hash_of(content, len(m.get("attachments") or []), len(m.get("embeds") or []))

    item = (
        db.query(SourceItem)
        .filter_by(provider=PROVIDER, external_id=m["id"])
        .one_or_none()
    )
    if item is None:
        item = SourceItem(provider=PROVIDER, external_id=m["id"], observed_at=fetched)
        db.add(item)

    item.scope_id = scope.id
    item.author_external_id = author.get("id")
    item.author_name = author.get("global_name") or author.get("username")
    item.author_roles = [r.get("name") for r in (author.get("_dce") or {}).get("roles") or []]
    item.content = content
    item.item_type = m.get("type")
    item.reply_to_external_id = (m.get("message_reference") or {}).get("message_id")
    item.attachment_count = len(m.get("attachments") or [])
    item.deep_link = f"https://discord.com/channels/{scope.guild_external_id}/{scope.external_id}/{m['id']}"
    item.content_hash = h
    item.source_updated_at = updated
    item.observed_at = fetched
    item.run_id = run_id
    db.flush()

    ver = db.query(SourceItemVersion).filter_by(item_id=item.id, content_hash=h).one_or_none()
    if ver is None:
        db.add(
            SourceItemVersion(
                item_id=item.id,
                content_hash=h,
                content=content,
                source_updated_at=updated,
                first_observed_at=fetched,
                last_observed_at=fetched,
            )
        )
    else:
        ver.last_observed_at = fetched
    return item.id


def load_chunks(db: Session, run_id: str, path: Path, item_ids: dict[str, int]) -> int:
    """Ghi chunk và nối nó với từng tin nhắn để trích dẫn được."""
    count = 0
    with path.open(encoding="utf-8") as f:
        for lines in f:
            c = json.loads(lines)
            scope = (
                db.query(SourceScope)
                .filter_by(provider=PROVIDER, external_id=c["channel_id"])
                .one_or_none()
            )
            if scope is None:
                continue
            khoa = c["chunk_id"]
            ch = db.query(Chunk).filter_by(run_id=run_id, chunk_key=khoa).one_or_none()
            if ch is None:
                ch = Chunk(run_id=run_id, chunk_key=khoa)
                db.add(ch)
            ch.scope_id = scope.id
            ch.mode = c["mode"]
            ch.group_key = c["group_key"]
            ch.text = c["text"]
            ch.message_count = c["message_count"]
            ch.char_count = c["char_count"]
            ch.author_ids = [a["id"] for a in c["authors"]]
            ch.author_roles = sorted({r for a in c["authors"] for r in a.get("roles") or []})
            ch.first_timestamp = datetime.fromisoformat(c["first_timestamp"])
            ch.last_timestamp = datetime.fromisoformat(c["last_timestamp"])
            ch.deep_link = c["deep_link"]
            db.flush()

            db.query(ChunkItem).filter_by(chunk_id=ch.id).delete()
            for i, mid in enumerate(c["message_ids"]):
                if mid in item_ids:
                    db.add(ChunkItem(chunk_id=ch.id, item_id=item_ids[mid], position=i))
            count += 1
            if count % 500 == 0:
                db.commit()
    db.commit()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Nạp run Discord vào Postgres")
    parser.add_argument("run_id", help="tên run, ví dụ 20260807T014941Z")
    parser.add_argument("--reset", action="store_true", help="xoá sạch bảng bằng chứng rồi nạp lại")
    args = parser.parse_args()

    norm = REPO / "data" / "discord" / "normalized" / args.run_id
    chunks = REPO / "data" / "discord" / "chunks" / args.run_id / "chunks.jsonl"
    if not norm.is_dir():
        sys.exit(f"Không thấy {norm}")
    if not chunks.is_file():
        sys.exit(f"Không thấy {chunks}")

    init_schema()

    if args.reset:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "TRUNCATE chunk_items, chunks, source_item_versions, source_items, source_scopes "
                "RESTART IDENTITY CASCADE"
            )
        print("đã xoá sạch bảng bằng chứng", file=sys.stderr)

    item_ids: dict[str, int] = {}
    message_count = n_channels = 0
    with Session(engine) as db:
        for p in sorted(norm.glob("*.json")):
            if p.name.startswith("_"):
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            scope = upsert_scope(db, data["channel"])
            fetched = datetime.fromisoformat(data["fetched_at"])
            for m in data["messages"]:
                item_ids[m["id"]] = upsert_item(db, m, scope, args.run_id, fetched)
                message_count += 1
            n_channels += 1
            if n_channels % 25 == 0:
                db.commit()
                print(f"  {n_channels} kênh · {message_count} tin", file=sys.stderr)
        db.commit()
        print(f"item: {n_channels} kênh · {message_count} tin", file=sys.stderr)
        chunk_count = load_chunks(db, args.run_id, chunks, item_ids)
        print(f"chunk: {chunk_count}", file=sys.stderr)
        access_counts = reconcile_all_discord_connections(db)
        print(
            "program access: "
            + " · ".join(f"{level}={access_counts[level]}" for level in ("A", "B", "C")),
            file=sys.stderr,
        )
        if access_counts.get("skipped"):
            print(
                f"CẢNH BÁO: {access_counts['skipped']} connection Discord không khớp user nào, "
                "đã bỏ qua. Kho vẫn nạp đủ, nhưng nên dọn mấy dòng đó.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
