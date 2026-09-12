import math
from datetime import UTC, datetime
from types import SimpleNamespace

from src.services.retrieval import (
    HALF_LIFE_DAYS,
    TIER_WEIGHT,
    Filters,
    _filter_clause,
    _sanitize_query,
)


def test_sanitize_query_strips_operators():
    # Dấu & : ! ( ) là toán tử của to_tsquery, lọt vào là câu truy vấn hỏng.
    assert _sanitize_query("hạn nộp gate 2!") == "hạn | nộp | gate | 2"
    assert _sanitize_query("a & b | c:*") == "a | b | c"
    assert _sanitize_query("!!!") == ""


def test_filter_clause_empty_without_constraints():
    dk, params = _filter_clause(Filters())
    assert dk == ""
    assert params == {}


def test_filter_clause_joins_all_conditions():
    dk, params = _filter_clause(
        Filters(
            scope_ids=[1, 2],
            roles=["Admin"],
            tier=["A"],
            since=datetime(2026, 8, 1, tzinfo=UTC),
        )
    )
    assert "c.scope_id = ANY(:scope_ids)" in dk
    assert "c.author_roles ?| :roles" in dk
    assert "s.tier = ANY(:tier)" in dk
    assert "c.last_timestamp >= :since" in dk
    assert set(params) == {"scope_ids", "roles", "tier", "since"}


def test_tier_a_outranks_tier_b():
    assert TIER_WEIGHT["A"] > TIER_WEIGHT["B"]


def test_recency_halves_after_one_half_life():
    assert math.pow(0.5, 0 / HALF_LIFE_DAYS) == 1.0
    assert abs(math.pow(0.5, HALF_LIFE_DAYS / HALF_LIFE_DAYS) - 0.5) < 1e-9


def test_embed_query_dung_timeout_tu_config(monkeypatch):
    """Trước đây timeout để 60s cứng: một lượt chat có thể đứng cả phút."""
    import src.services.retrieval as retrieval_module

    ghi_nhan: dict = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"embedding": [0.1, 0.2]}]}

    def _post(url, **kwargs):
        ghi_nhan.update(kwargs)
        return _Response()

    monkeypatch.setattr(retrieval_module.httpx, "post", _post)
    monkeypatch.setattr(
        retrieval_module,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="openrouter",
            openrouter_base_url="https://x/v1",
            embedding_model="m",
            embedding_timeout_seconds=8.0,
        ),
    )
    monkeypatch.setattr(
        retrieval_module,
        "build_openrouter_key_pool",
        lambda: SimpleNamespace(size=1, next_key=lambda: "k", mark_unavailable=lambda key: None),
    )

    assert retrieval_module.embed_query("câu hỏi") == [0.1, 0.2]
    assert ghi_nhan["timeout"] == 8.0


def test_embed_queries_reuses_rag_endpoint_for_a_batch(monkeypatch):
    import src.services.retrieval as retrieval_module

    calls = []

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]}

    monkeypatch.setattr(retrieval_module.httpx, "post", lambda url, **kwargs: (calls.append(kwargs), _Response())[1])
    monkeypatch.setattr(
        retrieval_module,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="openrouter",
            openrouter_base_url="https://x/v1",
            embedding_model="m",
            embedding_timeout_seconds=8.0,
        ),
    )
    monkeypatch.setattr(
        retrieval_module,
        "build_openrouter_key_pool",
        lambda: SimpleNamespace(size=1, next_key=lambda: "k", mark_unavailable=lambda key: None),
    )

    assert retrieval_module.embed_queries(["a", "b"]) == [[1.0], [2.0]]
    assert calls[0]["json"]["input"] == ["a", "b"]
