import uuid
from datetime import UTC, datetime

import pytest

from src.db import SessionLocal
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User
from src.services.scope import apply_search_scope, reset_agent_scope


def test_apply_search_scope_only_sets_active_grants(monkeypatch):
    db = SessionLocal()
    captured: dict[str, object] = {}
    try:
        suffix = uuid.uuid4().hex
        user = User(
            email=f"scope-{suffix}@example.com",
            password_hash="test",
            program_cohort_slug="cohort-assigned",
        )
        db.add(user)
        db.flush()
        user_id = str(user.id)
        allowed = SourceScope(provider="discord", external_id=f"allowed-{suffix}")
        revoked = SourceScope(provider="discord", external_id=f"revoked-{uuid.uuid4().hex}")
        non_discord = SourceScope(provider="google", external_id=f"google-{uuid.uuid4().hex}")
        db.add_all([allowed, revoked, non_discord])
        db.flush()
        now = datetime.now(UTC)
        db.add_all(
            [
                Connection(
                    user_id=user_id,
                    provider="discord",
                    provider_user_id=f"discord-user-{suffix}",
                ),
                SourceScopeAccess(user_id=user_id, scope_id=allowed.id, granted_at=now),
                SourceScopeAccess(
                    user_id=user_id,
                    scope_id=revoked.id,
                    status="revoked",
                    granted_at=now,
                    valid_to=now,
                ),
                SourceScopeAccess(user_id=user_id, scope_id=non_discord.id, granted_at=now),
            ]
        )
        db.commit()

        monkeypatch.setattr(
            "src.services.scope.set_search_scope",
            lambda scope_ids, author_external_id=None: (
                captured.setdefault("scope_ids", scope_ids),
                captured.setdefault("author_external_id", author_external_id),
            ),
        )
        monkeypatch.setattr("src.services.scope.reconcile_program_access", lambda *_: "A")
        monkeypatch.setattr(
            "src.services.scope.set_task_scope",
            lambda scoped_user_id: captured.setdefault("task_user_id", scoped_user_id),
        )
        monkeypatch.setattr(
            "src.services.scope.set_calendar_scope",
            lambda scoped_user_id: captured.setdefault("calendar_user_id", scoped_user_id),
        )
        monkeypatch.setattr(
            "src.services.scope.set_program_calendar_scope",
            lambda level, cohort: captured.setdefault("program_calendar_scope", (level, cohort)),
        )
        monkeypatch.setattr(
            "src.services.scope.set_program_information_scope",
            lambda level, cohort: captured.setdefault("program_information_scope", (level, cohort)),
        )
        apply_search_scope(user_id, db)
        assert captured["scope_ids"] == [allowed.id]
        assert captured["author_external_id"] == f"discord-user-{suffix}"
        assert captured["task_user_id"] == user_id
        assert captured["calendar_user_id"] == user_id
        assert captured["program_calendar_scope"] == ("A", "cohort-assigned")
        assert captured["program_information_scope"] == ("A", "cohort-assigned")
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize(
    ("program_level", "assigned_cohort", "expected_cohort"),
    [
        ("A", "cohort-assigned", "cohort-assigned"),
        ("A", None, "cohort-pilot"),
        ("B", None, "cohort-pilot"),
        ("C", None, "cohort-pilot"),
    ],
)
def test_apply_search_scope_uses_one_effective_cohort_for_all_access_levels(
    monkeypatch,
    program_level,
    assigned_cohort,
    expected_cohort,
):
    db = SessionLocal()
    captured: dict[str, tuple[str, str]] = {}
    try:
        user = User(
            email=f"program-scope-{uuid.uuid4().hex}@example.com",
            password_hash="test",
            program_cohort_slug=assigned_cohort,
        )
        db.add(user)
        db.commit()

        monkeypatch.setattr("src.services.scope.reconcile_program_access", lambda *_: program_level)
        monkeypatch.setattr(
            "src.services.program_cohorts.configured_program_cohort_slug",
            lambda: "cohort-pilot",
        )
        monkeypatch.setattr(
            "src.services.scope.set_program_calendar_scope",
            lambda level, cohort: captured.setdefault("calendar", (level, cohort)),
        )
        monkeypatch.setattr(
            "src.services.scope.set_program_information_scope",
            lambda level, cohort: captured.setdefault("information", (level, cohort)),
        )

        apply_search_scope(str(user.id), db)

        assert captured == {
            "calendar": (program_level, expected_cohort),
            "information": (program_level, expected_cohort),
        }
    finally:
        reset_agent_scope()
        db.close()


def test_apply_search_scope_rejects_invalid_assigned_cohort(monkeypatch):
    db = SessionLocal()
    try:
        user = User(
            email=f"invalid-program-scope-{uuid.uuid4().hex}@example.com",
            password_hash="test",
            program_cohort_slug="cohort/invalid",
        )
        db.add(user)
        db.commit()
        monkeypatch.setattr("src.services.scope.reconcile_program_access", lambda *_: "A")
        monkeypatch.setattr(
            "src.services.program_cohorts.configured_program_cohort_slug",
            lambda: "cohort-pilot",
        )

        with pytest.raises(ValueError, match="cohortSlug"):
            apply_search_scope(str(user.id), db)
    finally:
        reset_agent_scope()
        db.close()


def test_reset_agent_scope_clears_all_tool_scopes(monkeypatch):
    cleared: list[str] = []
    monkeypatch.setattr("src.services.scope.reset_search_scope", lambda: cleared.append("search"))
    monkeypatch.setattr("src.services.scope.reset_task_scope", lambda: cleared.append("task"))
    monkeypatch.setattr("src.services.scope.reset_calendar_scope", lambda: cleared.append("calendar"))

    reset_agent_scope()

    assert cleared == ["search", "task", "calendar"]
