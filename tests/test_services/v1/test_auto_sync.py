"""Scheduler nền tự tạo Run — xem src/services/auto_sync.py và ADR-011.

Ranh giới quan trọng nhất được khoá ở đây: auto-sync KHÔNG bao giờ tự chọn
nguồn mới, nó chỉ lặp lại đúng bộ nguồn người dùng đã tự tay chọn.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.run import Run
from src.models.user import User
from src.services.auto_sync import (
    _auto_idempotency_key,
    build_auto_run_request,
    enqueue_due_auto_syncs,
    find_due_users,
)

# User do file test này tạo, để teardown xoá đúng phần mình sinh ra.
_created_user_ids: set[int] = set()


@pytest.fixture(autouse=True)
def _enable_auto_sync(monkeypatch):
    """Công tắc tổng mặc định TẮT ở production; test phải bật tường minh.

    Nâng luôn trần run toàn hệ thống: DB test dùng chung và không reset giữa
    các file, nên dòng `queued` tồn dư từ test khác sẽ làm enqueue_run() trả
    "Hệ thống đang bận" và mọi khẳng định ở đây hỏng vì lý do không liên quan.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "auto_sync_enabled", True)
    monkeypatch.setattr(settings, "max_concurrent_runs", 10_000)
    _created_user_ids.clear()
    yield
    # Dọn sạch run của test này. Bỏ qua bước này thì mỗi dòng `queued` sót lại
    # cộng vào trần max_concurrent_runs toàn cục, và các file test khác bắt đầu
    # ăn 429 vì lý do không liên quan gì tới chúng.
    with SessionLocal() as db:
        if _created_user_ids:
            db.query(Run).filter(Run.user_id.in_(_created_user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(_created_user_ids)).delete(synchronize_session=False)
            db.commit()
    _created_user_ids.clear()
    get_settings.cache_clear()


def _make_user(db, *, auto_sync_enabled: bool = True, is_active: bool = True) -> User:
    user = User(
        email=f"auto-sync-{uuid.uuid4().hex[:12]}@example.com",
        password_hash="x",
        auto_sync_enabled=auto_sync_enabled,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    _created_user_ids.add(user.id)
    return user


def _make_run(
    db, user: User, *, status: str, age_minutes: int, sources: list | None = None, language: str = "vi"
) -> Run:
    created = datetime.now(UTC) - timedelta(minutes=age_minutes)
    run = Run(
        user_id=user.id,
        sources=sources if sources is not None else [{"connectionId": 1, "sourceId": "INBOX"}],
        range_from=created - timedelta(days=1),
        range_to=created,
        idempotency_key=f"manual-{uuid.uuid4().hex[:10]}",
        timezone="Asia/Ho_Chi_Minh",
        language=language,
        mode="task_extraction",
        status=status,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run.created_at = created
    db.commit()
    return run


def test_user_whose_last_run_is_older_than_interval_is_due():
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=get_settings().auto_sync_interval_minutes + 30)

        assert user.id in {due.id for due in find_due_users(db)}


def test_user_synced_recently_is_not_due():
    """Vừa sync xong mà lại bị sync tiếp là đốt quota API của người dùng."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=5)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_user_with_run_in_flight_is_not_due():
    """Không chen ngang: người dùng đang ngồi chờ một Sync thủ công chạy."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)
        _make_run(db, user, status="running", age_minutes=10_000)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_user_who_opted_out_is_never_due():
    with SessionLocal() as db:
        user = _make_user(db, auto_sync_enabled=False)
        _make_run(db, user, status="succeeded", age_minutes=10_000)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_inactive_user_is_never_due():
    with SessionLocal() as db:
        user = _make_user(db, is_active=False)
        _make_run(db, user, status="succeeded", age_minutes=10_000)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_user_who_never_synced_manually_is_not_due():
    """Chưa từng tự chọn nguồn lần nào thì hệ thống không được tự đoán hộ."""
    with SessionLocal() as db:
        user = _make_user(db)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_failed_run_still_pushes_next_attempt_out_by_a_full_interval():
    """Run lỗi không được biến thành vòng lặp thử lại liên tục."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)
        _make_run(db, user, status="failed", age_minutes=5)

        assert user.id not in {due.id for due in find_due_users(db)}


def test_auto_run_reuses_exactly_the_sources_user_picked():
    """Ranh giới privacy: không thêm, không đổi nguồn nào."""
    picked = [
        {"connectionId": 7, "sourceId": "INBOX"},
        {"connectionId": 7, "sourceId": "calendar:primary"},
    ]
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000, sources=picked)

        body = build_auto_run_request(db, user)

        assert body is not None
        assert [(s.connection_id, s.source_id) for s in body.sources] == [(7, "INBOX"), (7, "calendar:primary")]
        assert body.timezone == "Asia/Ho_Chi_Minh"


def test_auto_run_inherits_language_from_last_manual_run():
    """Auto-sync chạy nền, không có request sống để lấy ngôn ngữ app hiện tại
    — phải kế thừa ngôn ngữ user đã dùng ở lần Sync thủ công gần nhất."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000, language="en")

        body = build_auto_run_request(db, user)

        assert body is not None
        assert body.language == "en"


def test_auto_run_window_matches_configured_range_hours():
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)

        body = build_auto_run_request(db, user)

        assert body is not None
        assert body.time_to - body.time_from == timedelta(hours=get_settings().auto_sync_range_hours)


def test_auto_run_ignores_a_failed_run_when_copying_sources():
    """Nguồn phải sao từ run THÀNH CÔNG; run lỗi có thể mang nguồn đã hỏng."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000, sources=[{"connectionId": 3, "sourceId": "good"}])
        _make_run(db, user, status="failed", age_minutes=9_000, sources=[{"connectionId": 9, "sourceId": "broken"}])

        body = build_auto_run_request(db, user)

        assert body is not None
        assert [(s.connection_id, s.source_id) for s in body.sources] == [(3, "good")]


def test_source_list_is_trimmed_when_limit_was_lowered(monkeypatch):
    """Hạ MAX_SYNC_SOURCES sau đó không được làm scheduler kẹt lỗi vĩnh viễn."""
    monkeypatch.setattr(get_settings(), "max_sync_sources", 2)
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(
            db,
            user,
            status="succeeded",
            age_minutes=10_000,
            sources=[{"connectionId": 1, "sourceId": f"s{i}"} for i in range(5)],
        )

        body = build_auto_run_request(db, user)

        assert body is not None
        assert len(body.sources) == 2


def _only(monkeypatch, users: list[User]) -> None:
    """Giới hạn vòng quét vào đúng những user của test.

    DB test dùng chung giữa các file và không reset giữa các test, nên vòng
    quét thật sẽ vớ phải user tồn dư từ test khác rồi đụng trần
    max_concurrent_runs trước khi tới lượt user mình vừa tạo.
    """
    monkeypatch.setattr("src.services.auto_sync.find_due_users", lambda db, now=None: users)


def test_enqueue_creates_a_queued_run_the_worker_can_claim(monkeypatch):
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)
        _only(monkeypatch, [user])

        assert enqueue_due_auto_syncs(db) == 1

        queued = db.query(Run).filter(Run.user_id == user.id, Run.status == "queued").all()
        assert len(queued) == 1
        assert queued[0].idempotency_key.startswith(f"auto-{user.id}-")


def test_second_scan_in_same_interval_does_not_duplicate_the_run(monkeypatch):
    """Hai worker replica cùng thấy một user tới hạn -> vẫn chỉ một run."""
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)
        _only(monkeypatch, [user])

        enqueue_due_auto_syncs(db)
        enqueue_due_auto_syncs(db)

        queued = db.query(Run).filter(Run.user_id == user.id, Run.status == "queued").all()
        assert len(queued) == 1


def test_global_switch_off_means_no_run_is_ever_created(monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_sync_enabled", False)
    with SessionLocal() as db:
        user = _make_user(db)
        _make_run(db, user, status="succeeded", age_minutes=10_000)
        _only(monkeypatch, [user])

        assert enqueue_due_auto_syncs(db) == 0
        assert db.query(Run).filter(Run.user_id == user.id, Run.status == "queued").count() == 0


def test_idempotency_key_is_stable_within_an_interval_bucket():
    base = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    assert _auto_idempotency_key(42, base, 180) == _auto_idempotency_key(42, base + timedelta(minutes=30), 180)
    assert _auto_idempotency_key(42, base, 180) != _auto_idempotency_key(42, base + timedelta(hours=4), 180)


def test_tick_stops_after_max_users_per_tick(monkeypatch):
    """Sáng thứ Hai cả nghìn user tới hạn không được dồn một cục vào hàng đợi."""
    monkeypatch.setattr(get_settings(), "auto_sync_max_users_per_tick", 2)
    with SessionLocal() as db:
        users = []
        for _ in range(4):
            user = _make_user(db)
            _make_run(db, user, status="succeeded", age_minutes=10_000)
            users.append(user)
        _only(monkeypatch, users)

        assert enqueue_due_auto_syncs(db) == 2
