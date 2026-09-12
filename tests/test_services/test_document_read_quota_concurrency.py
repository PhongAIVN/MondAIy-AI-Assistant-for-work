"""Test hồi quy cho ba đường lách tầng chống spam token (review chéo 2026-08-20).

Trọng tâm là bài test cạnh tranh THẬT: nhiều thread cùng xin lượt đọc một lúc,
đúng `limit` lượt được cấp, không hơn.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from src.config import get_settings
from src.db import SessionLocal
from src.models.document_read import DocumentReadQuota
from src.services.document_read_quota import consume_document_read, quota_remaining


def _new_user_id() -> str:
    return f"quota-{uuid.uuid4().hex[:16]}"


def _today_key() -> str:
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.app_timezone)).date().isoformat()


def _reads_used(user_id: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.execute(
                select(DocumentReadQuota.reads_used).where(DocumentReadQuota.user_id == user_id)
            ).scalar_one_or_none()
            or 0
        )
    finally:
        db.close()


def _claim_once(user_id: str) -> int | str:
    """Một 'request' độc lập: session riêng, đúng như mỗi request FastAPI."""
    db = SessionLocal()
    try:
        return consume_document_read(db, user_id)
    except HTTPException as exc:
        return f"http-{exc.status_code}"
    finally:
        db.close()


def test_concurrent_reads_consume_exactly_the_limit(monkeypatch):
    """Đường lách chính: SELECT rồi +1 ở Python khiến N request song song chỉ trừ 1 lượt.

    Mốc kiểm tra chặt nhất không phải "có 429" mà là các giá trị `remaining`
    trả về phải PHÂN BIỆT nhau: hai lượt cùng nhận remaining=4 nghĩa là một
    lượt đã ghi đè lượt kia (lost update) — đúng thứ bug này sinh ra để chặn.
    """
    limit = 5
    workers = 16
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(workers)))

    granted = [value for value in results if isinstance(value, int)]
    refused = [value for value in results if value == "http-429"]

    assert len(granted) == limit, f"cấp {len(granted)} lượt cho hạn mức {limit}: {results}"
    assert len(refused) == workers - limit
    assert sorted(granted) == list(range(limit))  # 0..limit-1, không trùng nhau
    assert _reads_used(user_id) == limit
    assert quota_remaining(SessionLocal(), user_id) == 0


def test_concurrent_reads_on_an_existing_row_do_not_lose_updates(monkeypatch):
    """Đường lách thuần tuý lost-update: hàng quota ĐÃ tồn tại từ trước.

    Tách khỏi test trên để không có va chạm INSERT nào lẫn vào: mọi request đều
    đi thẳng vào nhánh cộng. Bản cũ (SELECT -> +1 ở Python -> commit) cấp thừa
    lượt ở đây; bản dùng UPDATE nguyên tử thì không.
    """
    limit = 4
    workers = 20
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()

    db = SessionLocal()
    try:
        db.add(DocumentReadQuota(user_id=user_id, quota_day=_today_key(), reads_used=0))
        db.commit()
    finally:
        db.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(workers)))

    granted = [value for value in results if isinstance(value, int)]
    assert len(granted) == limit, f"cấp {len(granted)} lượt cho hạn mức {limit}: {results}"
    assert sorted(granted) == list(range(limit))
    assert _reads_used(user_id) == limit


def _seed_exhausted_yesterday(user_id: str, limit: int) -> None:
    """Hàng quota của user đang ở NGÀY HÔM QUA và đã cạn sạch lượt."""
    db = SessionLocal()
    try:
        db.add(DocumentReadQuota(user_id=user_id, quota_day="2000-01-01", reads_used=limit))
        db.commit()
    finally:
        db.close()


class _InterleavingSession:
    """Session bọc, chèn TRỌN một request khác vào ngay sau câu lệnh đầu tiên.

    Chạy N thread trên sqlite không tái hiện được va chạm giao ngày: sqlite nối
    tiếp các lệnh ghi chặt tới mức thread thứ hai luôn đọc được hàng đã sang
    ngày mới, nên nó thắng luôn ở UPDATE nguyên tử và không bao giờ rơi xuống
    nhánh SELECT. Muốn kiểm nhánh đó thì phải ép đúng thứ tự đan xen:
    B chạy UPDATE #1 khi hàng CÒN ngày hôm qua -> A rollover xong và commit ->
    B mới chạy tiếp.
    """

    def __init__(self, inner, on_first_execute) -> None:
        self._inner = inner
        self._on_first_execute = on_first_execute
        self._fired = False

    def execute(self, *args, **kwargs):
        result = self._inner.execute(*args, **kwargs)
        if not self._fired:
            self._fired = True
            # UPDATE #1 của B không đụng hàng nào; nhả giao dịch rỗng ra để A
            # commit được, đúng như hai connection riêng ngoài đời.
            self._inner.rollback()
            self._on_first_execute()
        return result

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_day_rollover_race_does_not_refuse_a_user_who_just_got_a_fresh_limit(monkeypatch):
    """Tái hiện đúng thứ tự đan xen mà Tatejo mô tả, không dựa vào may rủi của thread.

    Hàng quota còn ở ngày hôm qua và đã cạn. B đọc hàng cũ, A rollover thắng
    (quota_day -> hôm nay, reads_used=1), rồi B mới chạy tiếp: rollover trượt,
    SELECT thấy hàng của hôm nay với reads_used=1. Bản cũ kết luận "đã cạn" và
    trả 429 cho người dùng vừa được cấp lại nguyên hạn mức.
    """
    limit = 20
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()
    _seed_exhausted_yesterday(user_id, limit)

    winner: list[int | str] = []

    def run_the_other_request() -> None:
        winner.append(_claim_once(user_id))

    inner = SessionLocal()
    try:
        session = _InterleavingSession(inner, run_the_other_request)
        remaining = consume_document_read(session, user_id)
    finally:
        inner.close()

    # A rollover trước và nhận lượt 1/20; B là lượt 2/20, KHÔNG được 429.
    assert winner == [limit - 1], winner
    assert remaining == limit - 2
    assert _reads_used(user_id) == 2


def test_day_rollover_race_does_not_refuse_users_who_still_have_quota(monkeypatch):
    """Va chạm đúng lúc giao ngày không được biến thành 429 oan.

    Kịch bản: hàng của user còn mang ngày hôm qua và đã cạn. A rollover thắng
    (quota_day -> hôm nay, reads_used=1). B thấy UPDATE nguyên tử trượt (lúc B
    đọc, hàng còn ngày cũ) rồi rollover cũng trượt (A vừa đổi), và nếu kết luận
    "hàng của hôm nay tồn tại nghĩa là đã cạn" thì B bị từ chối dù còn nguyên
    limit-1 lượt. Chỉ được 429 khi reads_used thật sự đã chạm limit.
    """
    limit = 8
    workers = 6
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()
    _seed_exhausted_yesterday(user_id, limit)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(workers)))

    granted = [value for value in results if isinstance(value, int)]
    refused = [value for value in results if value == "http-429"]

    assert refused == [], f"429 oan khi hạn mức mới còn {limit} lượt: {results}"
    assert len(granted) == workers
    # Trừ đúng bằng số request thành công, không thừa không thiếu.
    assert _reads_used(user_id) == workers
    assert sorted(granted) == sorted(_remaining_after(used, limit) for used in range(1, workers + 1))


def _remaining_after(used: int, limit: int) -> int:
    return max(0, limit - used)


def test_day_rollover_race_still_stops_at_the_limit(monkeypatch):
    """Vẫn phải chặn khi hạn mức MỚI của hôm nay thật sự cạn."""
    limit = 3
    workers = 12
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()
    _seed_exhausted_yesterday(user_id, limit)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(workers)))

    granted = [value for value in results if isinstance(value, int)]
    assert len(granted) == limit, results
    assert sorted(granted) == list(range(limit))
    assert _reads_used(user_id) == limit


def test_sequential_reads_still_count_one_by_one(monkeypatch):
    limit = 3
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()

    assert [_claim_once(user_id) for _ in range(limit)] == [2, 1, 0]
    assert _claim_once(user_id) == "http-429"
    assert _reads_used(user_id) == limit


def test_quota_rolls_over_to_a_new_day(monkeypatch):
    """Sang ngày mới thì bộ đếm phải về 0 — nhánh rollover cũng phải nguyên tử."""
    limit = 2
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()

    _claim_once(user_id)
    _claim_once(user_id)
    assert _claim_once(user_id) == "http-429"

    db = SessionLocal()
    try:
        row = db.execute(select(DocumentReadQuota).where(DocumentReadQuota.user_id == user_id)).scalar_one()
        row.quota_day = "2000-01-01"
        db.commit()
    finally:
        db.close()

    assert _claim_once(user_id) == limit - 1
    assert _reads_used(user_id) == 1


def test_concurrent_first_read_creates_only_one_quota_row(monkeypatch):
    """Hai request đầu tiên của một user chạy song song không được tạo 2 hàng."""
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", 10)
    user_id = _new_user_id()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(8)))

    assert all(isinstance(value, int) for value in results), results
    assert sorted(results) == list(range(2, 10))
    db = SessionLocal()
    try:
        rows = db.execute(select(DocumentReadQuota).where(DocumentReadQuota.user_id == user_id)).scalars().all()
        assert len(rows) == 1
    finally:
        db.close()


@pytest.mark.parametrize("workers", [4, 12])
def test_concurrency_never_exceeds_the_limit_for_various_widths(monkeypatch, workers):
    limit = 3
    monkeypatch.setattr(get_settings(), "google_document_reads_per_day", limit)
    user_id = _new_user_id()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: _claim_once(user_id), range(workers)))

    granted = [value for value in results if isinstance(value, int)]
    assert len(granted) == min(limit, workers)
    assert _reads_used(user_id) <= limit
