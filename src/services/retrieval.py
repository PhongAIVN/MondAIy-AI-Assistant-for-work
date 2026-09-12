"""Truy hồi lai theo memory-lifecycle §7: lọc, FTS + vector, hợp nhất RRF, xếp lại.

Thứ tự các bước bám đúng tài liệu, không tự đổi. Ba thừa số của công thức xếp
hạng chưa có dữ liệu — `status`, `reinforcement`, `negative_feedback` thuộc lớp
memory mà lớp đó chưa dựng — nên tạm để 1.0 và ghi rõ ở `ScoreBreakdown`.

Bộ lọc quyền không nằm ở đây và không được để LLM sinh ra. Hàm `retrieve` nhận
`scope_ids` đã lọc sẵn từ tầng gọi; truyền None nghĩa là không giới hạn, chỉ dùng
wait công cụ nội bộ.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.config import get_settings
from src.services.openrouter_keys import build_openrouter_key_pool
from src.services.telemetry import timed

# Hằng số RRF của bài báo gốc. Đổi thì phải đo lại, đừng chỉnh theo cảm tính.
RRF_K = 60

# Số ứng viên lấy từ mỗi nhánh trước khi hợp nhất. Rộng hơn k cuối để RRF có chỗ
# xoay, hẹp đủ để không kéo cả bảng về.
CANDIDATE_LIMIT = 60

# Mức A là nguồn chính thức theo Program Frame §6. Trọng số chỉ để xếp hạng —
# nó không được thay thẩm quyền của nguồn, xem QT-04.
TIER_WEIGHT = {"A": 1.3, "B": 1.0}

# Nửa đời của độ mới, tính bằng ngày. Chương trình chạy 6 tuần nên tin tháng
# trước vẫn còn giá trị, không hạ quá nhanh.
HALF_LIFE_DAYS = 21.0


@dataclass
class Filters:
    """Ràng buộc áp trước khi tính điểm, bước 1 của §7."""

    scope_ids: list[int] | None = None
    since: datetime | None = None
    until: datetime | None = None
    roles: list[str] | None = None
    tier: list[str] | None = None


@dataclass
class ScoreBreakdown:
    """Tách từng thừa số để giải thích được vì sao một chunk lên đầu."""

    rrf: float
    fts_rank: int | None
    vector_rank: int | None
    tier_weight: float
    recency_weight: float
    total: float
    unused_factors: tuple[str, ...] = ("status", "reinforcement", "negative_feedback")


@dataclass
class Result:
    chunk_id: int
    chunk_key: str
    channel: str
    tier: str
    mode: str
    message_count: int
    deep_link: str | None
    occurred_at: datetime
    roles: list[str] = field(default_factory=list)
    text: str = ""
    score: ScoreBreakdown | None = None


def _sanitize_query(q: str) -> str:
    """Đổi câu hỏi thành to_tsquery an toàn; bỏ ký tự có nghĩa với parser."""
    tu = [t for t in re.split(r"\W+", q, flags=re.UNICODE) if t]
    return " | ".join(tu) if tu else ""


_FPT_RETRY = 3
_LOI_TAM = {408, 409, 429, 500, 502, 503, 504}


def active_embedding_model(settings=None) -> str:
    """Tên model nhúng đang thật sự dùng, theo provider đã cấu hình.

    Nguồn duy nhất cho câu hỏi này. Trước đây `memory_store` so và ghi nhãn bằng
    `settings.embedding_model` — tên model của OpenRouter — kể cả khi vector do
    FPT sinh ra. Hệ quả: nhãn nói dối về không gian nhúng, và lần đổi model sau
    `backfill_memory_embeddings` nhìn nhãn tưởng đã đúng rồi bỏ qua hàng đó.
    """
    s = settings or get_settings()
    return s.fpt_embedding_model if s.embedding_provider == "fpt" else s.embedding_model


def _embed_qua_fpt(texts: list[str], s) -> list[list[float]]:
    """Nhúng qua FPT Cloud marketplace — cùng cổng đang dùng cho STT.

    Không có key pool vì đây là một key duy nhất, khác OpenRouter. Thiếu key thì
    NỔ chứ không âm thầm trả rỗng: embedding rỗng làm truy hồi trả kết quả sai
    mà không ai biết vì sao.
    """
    if not s.fpt_api_key:
        raise RuntimeError("EMBEDDING_PROVIDER=fpt nhưng FPT_API_KEY chưa được đặt.")
    # Chỉ một key nên không có key pool như OpenRouter, nhưng vẫn phải thử lại:
    # 429/5xx là lỗi TẠM. Ném thẳng lên thì `embed_query` hỏng, và ở
    # `retrieval` một exception làm mất luôn kết quả FTS đã lấy được.
    last: httpx.HTTPStatusError | None = None
    for lan in range(_FPT_RETRY):
        r = httpx.post(
            f"{s.fpt_base_url.rstrip('/')}/v1/embeddings",
            headers={"Authorization": f"Bearer {s.fpt_api_key}"},
            json={"model": s.fpt_embedding_model, "input": texts},
            timeout=s.embedding_timeout_seconds,
        )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as error:
            if r.status_code not in _LOI_TAM:
                raise
            last = error
            if lan < _FPT_RETRY - 1:
                time.sleep(min(2**lan, 8))
            continue
        data = sorted(enumerate(r.json()["data"]), key=lambda item: item[1].get("index", item[0]))
        return [item[1]["embedding"] for item in data]
    assert last is not None
    raise last


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Nhúng câu hỏi bằng đúng model đã nhúng chunk, nếu lệch thì vô nghĩa.

    Hàm đồng bộ và có chặn. Công cụ `discord_search_messages` cũng khai báo
    đồng bộ nên LangChain tự đẩy nó sang worker thread, event loop không bị giữ.
    Nhưng thread pool đó có trần: mỗi lượt tra nguồn chậm chiếm một thread, đủ
    người hỏi cùng lúc là cạn pool và tool bắt đầu xếp hàng. Vì vậy trần thời
    gian phải hữu hạn và đọc từ config, không để 60s cứng như trước.
    """
    if not texts:
        return []
    s = get_settings()
    if s.embedding_provider == "fpt":
        return _embed_qua_fpt(texts, s)
    pool = build_openrouter_key_pool()
    last_error: httpx.HTTPStatusError | None = None
    for _ in range(max(1, pool.size)):
        key = pool.next_key()
        r = httpx.post(
            f"{s.openrouter_base_url}/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": s.embedding_model, "input": texts},
            timeout=s.embedding_timeout_seconds,
        )
        try:
            r.raise_for_status()
            data = sorted(enumerate(r.json()["data"]), key=lambda item: item[1].get("index", item[0]))
            return [item[1]["embedding"] for item in data]
        except httpx.HTTPStatusError as error:
            last_error = error
            if r.status_code not in {401, 402, 403, 408, 409, 429, 500, 502, 503, 504}:
                raise
            pool.mark_unavailable(key)
    assert last_error is not None
    raise last_error


def embed_query(sql: str) -> list[float]:
    """Embed one query through the same provider/model used by RAG."""
    return embed_queries([sql])[0]


def _filter_clause(filters: Filters) -> tuple[str, dict]:
    clauses, params = [], {}
    if filters.scope_ids is not None:
        clauses.append("c.scope_id = ANY(:scope_ids)")
        params["scope_ids"] = filters.scope_ids
    if filters.since:
        clauses.append("c.last_timestamp >= :since")
        params["since"] = filters.since
    if filters.until:
        clauses.append("c.first_timestamp <= :until")
        params["until"] = filters.until
    if filters.roles:
        clauses.append("c.author_roles ?| :roles")
        params["roles"] = filters.roles
    if filters.tier:
        clauses.append("s.tier = ANY(:tier)")
        params["tier"] = filters.tier
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def retrieve(
    engine: Engine,
    question: str,
    filters: Filters | None = None,
    k: int = 10,
    db: Session | None = None,
) -> list[Result]:
    """Chạy đủ bước 1, 3, 4, 5 của §7 và trả về danh sách đã xếp hạng.

    `db` chỉ để ghi telemetry; truyền None thì sự kiện chỉ vào log chứ không vào
    bảng, dùng cho công cụ dòng lệnh.
    """
    filters = filters or Filters()
    dk, params = _filter_clause(filters)
    tsq = _sanitize_query(question)
    # Chỉ ghi tên trường đã lọc, không ghi giá trị — giá trị có thể là id người dùng.
    filter_keys = sorted(params)

    with timed(db, "retrieval_ran", filtered_by=filter_keys) as stats, engine.connect() as conn:
        fts_rank: dict[int, int] = {}
        if tsq:
            rows = conn.execute(
                text(
                    f"""
                    SELECT c.id
                    FROM chunks c JOIN source_scopes s ON s.id = c.scope_id
                    WHERE c.fts @@ to_tsquery('simple', unaccent(:tsq)) {dk}
                    ORDER BY ts_rank(c.fts, to_tsquery('simple', unaccent(:tsq))) DESC
                    LIMIT :n
                    """
                ),
                {**params, "tsq": tsq, "n": CANDIDATE_LIMIT},
            ).all()
            fts_rank = {r.id: i + 1 for i, r in enumerate(rows)}

        vec = str(embed_query(question))
        rows = conn.execute(
            text(
                f"""
                SELECT c.id
                FROM chunks c JOIN source_scopes s ON s.id = c.scope_id
                WHERE c.embedding IS NOT NULL {dk}
                ORDER BY c.embedding <=> CAST(:vec AS vector)
                LIMIT :n
                """
            ),
            {**params, "vec": vec, "n": CANDIDATE_LIMIT},
        ).all()
        vector_rank = {r.id: i + 1 for i, r in enumerate(rows)}

        # Hợp nhất bằng reciprocal rank fusion, bước 4.
        rrf: dict[int, float] = {}
        for table in (fts_rank, vector_rank):
            for cid, hang in table.items():
                rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (RRF_K + hang)
        stats.update(
            fts_hits=len(fts_rank),
            vector_hits=len(vector_rank),
            merged_hits=len(rrf),
            returned=min(k, len(rrf)),
        )
        if not rrf:
            return []

        details = conn.execute(
            text(
                """
                SELECT c.id, c.chunk_key, c.mode, c.message_count, c.deep_link,
                       c.last_timestamp, c.author_roles, c.text, s.name AS channel, s.tier
                FROM chunks c JOIN source_scopes s ON s.id = c.scope_id
                WHERE c.id = ANY(:ids)
                """
            ),
            {"ids": list(rrf)},
        ).all()

    now = datetime.now(UTC)
    results: list[Result] = []
    for r in details:
        ts_muc = TIER_WEIGHT.get(r.tier, 1.0)
        age_days = max((now - r.last_timestamp).total_seconds() / 86400.0, 0.0)
        ts_moi = math.pow(0.5, age_days / HALF_LIFE_DAYS)
        total = rrf[r.id] * ts_muc * ts_moi
        results.append(
            Result(
                chunk_id=r.id,
                chunk_key=r.chunk_key,
                channel=r.channel or "?",
                tier=r.tier,
                mode=r.mode,
                message_count=r.message_count,
                deep_link=r.deep_link,
                occurred_at=r.last_timestamp,
                roles=r.author_roles or [],
                text=r.text,
                score=ScoreBreakdown(
                    rrf=rrf[r.id],
                    fts_rank=fts_rank.get(r.id),
                    vector_rank=vector_rank.get(r.id),
                    tier_weight=ts_muc,
                    recency_weight=ts_moi,
                    total=total,
                ),
            )
        )

    results.sort(key=lambda x: x.score.total, reverse=True)
    return results[:k]
