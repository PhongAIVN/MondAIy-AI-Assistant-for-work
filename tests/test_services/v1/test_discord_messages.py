import uuid
from datetime import UTC, datetime, timedelta

from src.db import SessionLocal, engine
from src.models.evidence import SourceItem, SourceScope
from src.services.discord_messages import get_my_discord_activity, search_my_discord_messages


def _add_message(db, scope, *, author, content, offset, suffix):
    occurred_at = datetime.now(UTC) + timedelta(minutes=offset)
    db.add(
        SourceItem(
            provider="discord",
            external_id=f"exact-{suffix}-{offset}-{author}",
            scope_id=scope.id,
            author_external_id=author,
            content=content,
            content_hash=f"hash-{suffix}-{offset}-{author}",
            source_updated_at=occurred_at,
            observed_at=occurred_at,
            run_id="test",
        )
    )


def test_personal_discord_search_never_returns_other_author_or_scope():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        allowed = SourceScope(provider="discord", external_id=f"allowed-{suffix}", name="Lab")
        forbidden = SourceScope(provider="discord", external_id=f"forbidden-{suffix}", name="Private")
        db.add_all([allowed, forbidden])
        db.flush()
        _add_message(db, allowed, author="me", content="Tôi đã setup Jira cho nhóm", offset=1, suffix=suffix)
        _add_message(db, allowed, author="other", content="Người khác setup Jira", offset=2, suffix=suffix)
        _add_message(db, forbidden, author="me", content="Tin của tôi nhưng ngoài scope", offset=3, suffix=suffix)
        db.commit()
        allowed_id = allowed.id

    results = search_my_discord_messages(
        engine,
        scope_ids=[allowed_id],
        author_external_id="me",
        query="setup Jira",
    )

    assert [row.content for row in results] == ["Tôi đã setup Jira cho nhóm"]


def test_personal_discord_activity_counts_exact_author_by_channel():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        scope = SourceScope(provider="discord", external_id=f"activity-{suffix}", name="Discussion")
        db.add(scope)
        db.flush()
        _add_message(db, scope, author="me-activity", content="Một", offset=1, suffix=suffix)
        _add_message(db, scope, author="me-activity", content="Hai", offset=2, suffix=suffix)
        _add_message(db, scope, author="other-activity", content="Không tính", offset=3, suffix=suffix)
        db.commit()
        scope_id = scope.id

    activity = get_my_discord_activity(
        engine,
        scope_ids=[scope_id],
        author_external_id="me-activity",
    )

    assert len(activity) == 1
    assert activity[0].channel == "Discussion"
    assert activity[0].message_count == 2
