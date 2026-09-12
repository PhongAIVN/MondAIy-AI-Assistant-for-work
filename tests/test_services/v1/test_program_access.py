import uuid
from datetime import UTC, datetime

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceItem, SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User
from src.services.auth import hash_password
from src.services.program_access import (
    reconcile_all_discord_connections,
    reconcile_program_access,
)


def _user(db, suffix: str) -> User:
    user = User(
        email=f"program-access-{suffix}@example.com",
        password_hash=hash_password("correct-horse-1"),
    )
    db.add(user)
    db.flush()
    return user


def _message(db, scope: SourceScope, author_id: str, suffix: str) -> SourceItem:
    now = datetime.now(UTC)
    item = SourceItem(
        provider="discord",
        external_id=f"message-{suffix}",
        scope_id=scope.id,
        author_external_id=author_id,
        author_name="Test member",
        content="Nội dung Discord đã crawl",
        content_hash=f"hash-{suffix}",
        source_updated_at=now,
        observed_at=now,
        run_id="test",
    )
    db.add(item)
    db.flush()
    return item


def test_reconcile_enforces_c_without_discord_b_unmatched_and_a_matched():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        discord_scope = SourceScope(provider="discord", external_id=f"discord-{suffix}")
        non_discord_scope = SourceScope(provider="google", external_id=f"google-{suffix}")
        db.add_all([discord_scope, non_discord_scope])
        db.flush()

        no_connection = _user(db, f"c-{suffix}")
        unmatched = _user(db, f"b-{suffix}")
        matched = _user(db, f"a-{suffix}")
        db.add_all(
            [
                Connection(
                    user_id=str(unmatched.id),
                    provider="discord",
                    provider_user_id=f"unmatched-{suffix}",
                ),
                Connection(
                    user_id=str(matched.id),
                    provider="discord",
                    provider_user_id=f"matched-{suffix}",
                ),
            ]
        )
        _message(db, discord_scope, f"matched-{suffix}", suffix)
        db.commit()

        assert reconcile_program_access(db, str(no_connection.id)) == "C"
        assert reconcile_program_access(db, str(unmatched.id)) == "B"
        assert reconcile_program_access(db, str(matched.id)) == "A"

        active = db.query(SourceScopeAccess).filter_by(user_id=str(matched.id), status="confirmed").all()
        expected_discord_scope_ids = {scope.id for scope in db.query(SourceScope).filter_by(provider="discord").all()}
        assert {grant.scope_id for grant in active} == expected_discord_scope_ids
        assert non_discord_scope.id not in {grant.scope_id for grant in active}
        assert matched.program_access_level == "A"


def test_reconcile_repairs_stale_c_and_grants_new_crawled_scopes():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        first = SourceScope(provider="discord", external_id=f"first-{suffix}")
        db.add(first)
        db.flush()
        user = _user(db, suffix)
        discord_id = f"member-{suffix}"
        db.add(
            Connection(
                user_id=str(user.id),
                provider="discord",
                provider_user_id=discord_id,
            )
        )
        _message(db, first, discord_id, f"first-{suffix}")
        db.commit()
        assert user.program_access_level == "C"

        assert reconcile_program_access(db, str(user.id)) == "A"
        second = SourceScope(provider="discord", external_id=f"second-{suffix}")
        db.add(second)
        db.commit()
        assert reconcile_program_access(db, str(user.id)) == "A"

        active_scope_ids = {
            row.scope_id
            for row in db.query(SourceScopeAccess).filter_by(user_id=str(user.id), status="confirmed")
            if row.valid_to is None
        }
        assert {first.id, second.id}.issubset(active_scope_ids)


def test_connection_rac_khong_lam_hong_ca_buoc_phan_loai():
    """Một dòng connection có user_id không phải số không được giết cả lần nạp crawl.

    Gặp thật khi chạy `load_to_db.py`: DB dev còn dòng của test với user_id dạng
    chuỗi, `int(user_id)` bắn ValueError và bước cuối của nạp crawl chết, dù item
    và chunk đã ghi xong. Bước này còn chạy cả lúc khởi động backend.
    """
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        scope = SourceScope(provider="discord", external_id=f"junk-{suffix}")
        db.add(scope)
        db.flush()
        user = _user(db, suffix)
        discord_id = f"member-{suffix}"
        db.add(Connection(user_id=str(user.id), provider="discord", provider_user_id=discord_id))
        db.add(
            Connection(
                user_id=f"scope-test-user-{suffix}",
                provider="discord",
                provider_user_id=f"ghost-{suffix}",
            )
        )
        _message(db, scope, discord_id, f"junk-{suffix}")
        db.commit()

        counts = reconcile_all_discord_connections(db)

    assert counts["skipped"] >= 1
    assert counts["A"] >= 1


def test_user_id_khong_phai_so_bao_loi_ro_rang():
    with SessionLocal() as db:
        try:
            reconcile_program_access(db, "scope-test-user-abc")
        except ValueError as e:
            assert "không tồn tại" in str(e)
        else:
            raise AssertionError("phải báo user không tồn tại")
