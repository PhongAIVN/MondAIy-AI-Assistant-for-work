"""TAPB-122 — nhúng chunk bằng OpenRouter rồi ghi vào cột vector của Postgres.

    python scripts/discord/embed_chunks.py <run_id>

Số chiều không hardcode: script gọi thử một câu để dò, rồi chỉnh cột `embedding`
wait khớp. pgvector khoá số chiều theo cột nên đổi model là phải nhúng lại toàn bộ,
và script chỉ tự chỉnh cột khi cột đang rỗng hoàn toàn.

Chạy lại chỉ nhúng phần còn thiếu, nên đứt giữa chừng thì chạy tiếp được. Muốn
nhúng lại từ đầu thì thêm `--lam-lai`.

Lưu ý phạm vi dữ liệu: bước này **gửi nội dung chunk ra dịch vụ ngoài**. Chunk nào
không được phép rời máy thì phải lọc trước khi tới đây, không phải sau.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db import engine  # noqa: E402


def embed_batch(client: httpx.Client, model: str, inputs: list[str]) -> list[list[float]]:
    """Gọi endpoint embeddings, thử lại khi bị giới hạn tần suất hoặc lỗi tạm."""
    for attempt in range(6):
        r = client.post("/embeddings", json={"model": model, "input": inputs})
        if r.status_code == 200:
            data = r.json()["data"]
            return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
        if r.status_code in (429, 500, 502, 503, 504):
            wait = min(2**attempt, 60)
            print(f"  HTTP {r.status_code}, đợi {wait}s rồi thử lại", file=sys.stderr)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Provider embedding trả HTTP {r.status_code}: {r.text[:300]}")
    raise RuntimeError("Thử lại 6 lần vẫn không xong")


def ensure_dims(dims: int) -> None:
    """Chỉnh số chiều cột `embedding` wait khớp model, chỉ khi cột đang rỗng."""
    with engine.begin() as conn:
        current = conn.execute(
            text(
                "SELECT a.atttypmod FROM pg_attribute a "
                "JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname = 'chunks' AND a.attname = 'embedding'"
            )
        ).scalar()
        if current == dims:
            return
        already = conn.execute(text("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL")).scalar()
        if already:
            sys.exit(
                f"Cột embedding đang là {current} chiều, model trả {dims} chiều, "
                f"và đã có {already} dòng được nhúng. Chạy với --lam-lai để xoá rồi nhúng lại."
            )
        # Đã đo trên Postgres thật: index vector cũ KHÔNG chặn ALTER TYPE, nó
        # sống sót với định nghĩa cũ. Production có `ix_chunks_embedding_half`
        # = hnsw((embedding::halfvec(2048))); giữ nó lại thì cột thành
        # vector(1024) mà index vẫn đòi 2048, và lệnh ghi đầu tiên nổ
        # "expected 2048 dimensions, not 1024" — tức ALTER báo xong rồi mới
        # hỏng lúc nhúng. `build_index` dựng lại đúng loại cho số chiều mới.
        for ten in ("ix_chunks_embedding", "ix_chunks_embedding_half"):
            conn.execute(text(f"DROP INDEX IF EXISTS {ten}"))
        conn.execute(text(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({dims})"))
        print(f"đã chỉnh cột embedding sang {dims} chiều", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nhúng chunk bằng provider embedding đang cấu hình")
    parser.add_argument("run_id", help="tên run, ví dụ 20260807T014941Z")
    parser.add_argument("--reset-vectors", action="store_true", help="xoá vector cũ rồi nhúng lại từ đầu")
    parser.add_argument("--limit", type=int, default=0, help="chỉ nhúng N chunk đầu, để thử")
    args = parser.parse_args()

    s = get_settings()
    # Đi theo đúng provider mà runtime đang dùng. Script nhúng bằng một model mà
    # `embed_queries` lại truy vấn bằng model khác thì vector và câu hỏi nằm ở
    # hai không gian khác nhau — truy hồi trả kết quả sai mà không báo lỗi.
    if s.embedding_provider == "fpt":
        if not s.fpt_api_key:
            sys.exit("EMBEDDING_PROVIDER=fpt nhưng thiếu FPT_API_KEY trong .env")
        base_url = f"{s.fpt_base_url.rstrip('/')}/v1"
        api_key = s.fpt_api_key
        model = s.fpt_embedding_model
    else:
        if not s.openrouter_api_key:
            sys.exit("Thiếu OPENROUTER_API_KEY trong .env")
        base_url = s.openrouter_base_url
        api_key = s.openrouter_api_key
        model = s.embedding_model

    client = httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120.0,
    )

    probe = embed_batch(client, model, ["xin chào"])
    dims = len(probe[0])
    print(f"model {model} trả {dims} chiều", file=sys.stderr)

    # `ensure_dims` PHẢI chạy trước khi xoá vector của run này.
    #
    # Thứ tự cũ xoá trước rồi mới gọi ensure_dims. Khi số chiều đổi và có run
    # KHÁC còn vector, ensure_dims thoát bằng sys.exit — nhưng lệnh xoá đã
    # commit rồi. Kết quả: run được chỉ định mất sạch vector, cột vẫn ở chiều
    # cũ, và không có gì được nhúng lại. Chạy lại lệnh cũng không cứu vì
    # ensure_dims vẫn thoát ở cùng chỗ.
    ensure_dims(dims)

    if args.reset_vectors:
        with engine.begin() as conn:
            conn.execute(text("UPDATE chunks SET embedding = NULL WHERE run_id = :r"), {"r": args.run_id})

    with engine.connect() as conn:
        remaining = conn.execute(
            text("SELECT count(*) FROM chunks WHERE run_id = :r AND embedding IS NULL"),
            {"r": args.run_id},
        ).scalar()
    print(f"cần nhúng: {remaining} chunk", file=sys.stderr)

    done = 0
    while True:
        with engine.connect() as conn:
            batch: list[Any] = conn.execute(
                text(
                    "SELECT id, text FROM chunks WHERE run_id = :r AND embedding IS NULL "
                    "ORDER BY id LIMIT :n"
                ),
                {"r": args.run_id, "n": s.embedding_batch_size},
            ).all()
        if not batch:
            break
        vecs = embed_batch(client, model, [row.text for row in batch])
        with engine.begin() as conn:
            for row, v in zip(batch, vecs, strict=True):
                conn.execute(
                    text("UPDATE chunks SET embedding = :v WHERE id = :i"),
                    {"v": str(v), "i": row.id},
                )
        done += len(batch)
        print(f"  {done}/{remaining}", file=sys.stderr)
        if args.limit and done >= args.limit:
            break

    build_index(dims)
    print(f"xong {done} chunk", file=sys.stderr)


HNSW_MAX_VECTOR = 2000
HNSW_MAX_HALFVEC = 4000


def build_index(dims: int) -> None:
    """Dựng index vector nếu số chiều cho phép; không dựng được cũng không chặn.

    pgvector chỉ index được `vector` tới 2000 chiều. Trên mức đó vẫn quét tuần tự
    được — architecture §8 nói thêm index khi dataset đủ lớn chứ không dựng sẵn,
    nên vài nghìn dòng không có index vẫn đúng chủ trương.
    """
    if dims <= HNSW_MAX_VECTOR:
        sql = (
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding ON chunks "
            "USING hnsw (embedding vector_cosine_ops)"
        )
        label = "HNSW trên vector"
    elif dims <= HNSW_MAX_HALFVEC:
        # halfvec index được tới 4000 chiều. Truy vấn muốn dùng index này phải ép
        # kiểu y hệt biểu thức, nếu không Postgres sẽ bỏ qua nó và quét tuần tự.
        sql = (
            f"CREATE INDEX IF NOT EXISTS ix_chunks_embedding_half ON chunks "
            f"USING hnsw ((embedding::halfvec({dims})) halfvec_cosine_ops)"
        )
        label = f"HNSW trên halfvec({dims})"
    else:
        print(f"{dims} chiều vượt mọi giới hạn index, quét tuần tự", file=sys.stderr)
        return

    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        print(f"đã dựng index: {label}", file=sys.stderr)
    except Exception as e:
        print(f"không dựng được index ({label}): {str(e)[:160]}", file=sys.stderr)
        print("vẫn truy vấn được, chỉ là quét tuần tự", file=sys.stderr)


if __name__ == "__main__":
    main()
