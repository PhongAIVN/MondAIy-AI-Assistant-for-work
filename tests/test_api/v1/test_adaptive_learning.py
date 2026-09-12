"""Slice 1 adaptive learning: consent, inbox candidate, reset, audit.

Gate của slice theo execution plan P1: success + cross-user denial, revoke
loại khỏi lần học kế tiếp, và bất biến "không raw text trong bảng phái sinh".
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.config import get_settings
from src.db import SessionLocal
from src.models.learning import (
    LEARNING_CAPABILITIES,
    AssistantContextRef,
    LearningAuditEvent,
    LearningCandidate,
    LearningConsent,
    LearningEvidence,
    LearningReviewCursor,
    LearningSignal,
)
from src.services.learning import is_learning_enabled


def _unique_email() -> str:
    return f"test-adaptive-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client) -> tuple[int, str]:
    email = _unique_email()
    response = await client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert response.status_code == 201
    data = response.json()
    return int(data["userId"]), data["accessToken"]


def _seed_candidate(user_id: int, *, key: str, candidate_type: str, **overrides) -> LearningCandidate:
    db = SessionLocal()
    try:
        row = LearningCandidate(
            user_id=user_id,
            candidate_key=key,
            version=1,
            candidate_type=candidate_type,
            status="pending_review",
            payload_json={"dimension": "verbosity", "value": "concise"},
            confidence=0.8,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        for field, value in overrides.items():
            setattr(row, field, value)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


@pytest.mark.asyncio
async def test_requires_authentication(client):
    response = await client.get("/api/v1/adaptive-learning/consent")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_default_consents_are_all_disabled(client):
    _, token = await _register(client)
    response = await client.get("/api/v1/adaptive-learning/consent", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    consents = {row["capability"]: row["enabled"] for row in response.json()["consents"]}
    assert set(consents.keys()) == set(LEARNING_CAPABILITIES)
    assert not any(consents.values()), "Mặc định phải tắt toàn bộ theo ADR-017"


@pytest.mark.asyncio
async def test_cannot_enable_when_global_flag_is_off(client):
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert get_settings().adaptive_learning_enabled is False

    response = await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "chat_learning", "enabled": True},
        headers=headers,
    )
    assert response.status_code == 403

    # Tắt thì luôn được phép — user có quyền rút lại dữ liệu bất kể cờ tổng.
    revoke = await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "chat_learning", "enabled": False},
        headers=headers,
    )
    assert revoke.status_code == 200


@pytest.mark.asyncio
async def test_enable_persists_and_writes_audit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "adaptive_learning_enabled", True)
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}

    enabled = await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "chat_learning", "enabled": True},
        headers=headers,
    )
    assert enabled.status_code == 200
    row = next(c for c in enabled.json()["consents"] if c["capability"] == "chat_learning")
    assert row["enabled"] is True
    assert row["consentedAt"] is not None
    assert row["revokedAt"] is None

    audit = await client.get("/api/v1/adaptive-learning/audit", headers=headers)
    actions = [event["action"] for event in audit.json()["events"]]
    assert "consent_enabled" in actions


@pytest.mark.asyncio
async def test_invalid_capability_rejected(client):
    _, token = await _register(client)
    response = await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "mind_reading", "enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_revoke_stamps_revoked_at_and_audits(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "adaptive_learning_enabled", True)
    _, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"capability": "adaptive_style", "enabled": True}
    await client.patch("/api/v1/adaptive-learning/consent", json=payload, headers=headers)

    revoked = await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "adaptive_style", "enabled": False},
        headers=headers,
    )
    assert revoked.status_code == 200
    row = next(c for c in revoked.json()["consents"] if c["capability"] == "adaptive_style")
    assert row["enabled"] is False
    assert row["revokedAt"] is not None

    audit = await client.get("/api/v1/adaptive-learning/audit", headers=headers)
    actions = [event["action"] for event in audit.json()["events"]]
    assert "consent_revoked" in actions


@pytest.mark.asyncio
async def test_consent_is_user_scoped(client, monkeypatch):
    """Bật của A không được lộ sang B — denial path bắt buộc của gate Slice 1."""
    monkeypatch.setattr(get_settings(), "adaptive_learning_enabled", True)
    _, token_a = await _register(client)
    _, token_b = await _register(client)

    await client.patch(
        "/api/v1/adaptive-learning/consent",
        json={"capability": "chat_learning", "enabled": True},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    seen_by_b = await client.get(
        "/api/v1/adaptive-learning/consent", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert seen_by_b.status_code == 200
    assert not any(row["enabled"] for row in seen_by_b.json()["consents"])


@pytest.mark.asyncio
async def test_candidates_are_user_scoped_and_reject_is_denied_cross_user(client):
    user_a, token_a = await _register(client)
    _, token_b = await _register(client)
    seeded = _seed_candidate(user_a, key=f"style-verbosity-{uuid.uuid4().hex[:8]}", candidate_type="style_preference")

    listed_b = await client.get(
        "/api/v1/adaptive-learning/candidates", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert listed_b.status_code == 200
    assert listed_b.json()["candidates"] == []

    denied = await client.post(
        f"/api/v1/adaptive-learning/candidates/{seeded.id}/reject",
        json={},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404

    listed_a = await client.get(
        "/api/v1/adaptive-learning/candidates", headers={"Authorization": f"Bearer {token_a}"}
    )
    keys = [row["candidateKey"] for row in listed_a.json()["candidates"]]
    assert seeded.candidate_key in keys


@pytest.mark.asyncio
async def test_owner_reject_marks_terminal_and_audits(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    seeded = _seed_candidate(user_id, key=f"style-tone-{uuid.uuid4().hex[:8]}", candidate_type="style_preference")

    rejected = await client.post(
        f"/api/v1/adaptive-learning/candidates/{seeded.id}/reject",
        json={"reasonCodes": ["not_correct"]},
        headers=headers,
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["status"] == "rejected"

    # Candidate đã kết thúc: không nằm trong inbox nữa và reject lần hai là 404.
    inbox = await client.get("/api/v1/adaptive-learning/candidates", headers=headers)
    assert all(row["id"] != seeded.id for row in inbox.json()["candidates"])

    again = await client.post(
        f"/api/v1/adaptive-learning/candidates/{seeded.id}/reject", json={}, headers=headers
    )
    assert again.status_code == 404

    audit = await client.get("/api/v1/adaptive-learning/audit", headers=headers)
    assert any(event["action"] == "candidate_rejected" for event in audit.json()["events"])


@pytest.mark.asyncio
async def test_expired_candidates_leave_inbox_without_user_action(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    _seed_candidate(
        user_id,
        key=f"stale-{uuid.uuid4().hex[:8]}",
        candidate_type="skill",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    inbox = await client.get("/api/v1/adaptive-learning/candidates", headers=headers)
    assert inbox.json()["candidates"] == []


@pytest.mark.asyncio
async def test_reset_scope_forgets_only_that_scope(client):
    user_id, token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    style_one = _seed_candidate(user_id, key=f"s1-{uuid.uuid4().hex[:8]}", candidate_type="style_preference")
    skill_one = _seed_candidate(user_id, key=f"k1-{uuid.uuid4().hex[:8]}", candidate_type="skill")

    invalid = await client.delete("/api/v1/adaptive-learning?scope=everything", headers=headers)
    assert invalid.status_code == 422

    reset = await client.delete("/api/v1/adaptive-learning?scope=style", headers=headers)
    assert reset.status_code == 200
    assert reset.json() == {"scope": "style", "forgotten": 1}

    inbox = await client.get("/api/v1/adaptive-learning/candidates", headers=headers)
    remaining_ids = [row["id"] for row in inbox.json()["candidates"]]
    assert style_one.id not in remaining_ids
    assert skill_one.id in remaining_ids

    reset_all = await client.delete("/api/v1/adaptive-learning?scope=all", headers=headers)
    assert reset_all.status_code == 200
    assert reset_all.json()["forgotten"] == 1

    audit = await client.get("/api/v1/adaptive-learning/audit", headers=headers)
    assert any(event["action"] == "learning_reset" for event in audit.json()["events"])


def test_no_free_text_columns_in_learning_tables():
    """Bất biến riêng tư của ADR-017: bảng phái sinh không có cột văn bản tự do.

    Text/LargeBinary là chỗ raw transcript hay trốn; nếu sau này cần thêm cột
    kiểu này thì phải sửa test này kèm lý do ghi trong ADR, không phải lách qua.
    """
    from sqlalchemy import LargeBinary, Text

    for model in (
        LearningSignal,
        LearningCandidate,
        LearningConsent,
        LearningReviewCursor,
        LearningEvidence,
        AssistantContextRef,
        LearningAuditEvent,
    ):
        for column in model.__table__.columns:
            assert not isinstance(column.type, Text | LargeBinary), (
                f"{model.__tablename__}.{column.name} đang dùng kiểu văn bản tự do — "
                "vi phạm ranh giới 'no raw content' của ADR-017"
            )


def test_unique_constraints_block_duplicate_rows():
    """Retry worker không được sinh trùng: chặn ở DB chứ không chỉ ở logic."""
    from sqlalchemy import delete
    from sqlalchemy.exc import IntegrityError

    # Id sentinel ngoài dải autoincrement của user thật trong cùng session —
    # các test API đăng ký user liên tiếp nên id nhỏ đã bị chiếm.
    sentinel = 9_000_001

    db = SessionLocal()
    try:
        db.execute(delete(LearningConsent).where(LearningConsent.user_id == sentinel))
        db.execute(delete(LearningCandidate).where(LearningCandidate.user_id == sentinel))
        db.commit()

        # Consent: một dòng duy nhất cho (user, capability).
        db.add(LearningConsent(user_id=sentinel, capability="chat_learning", enabled=True))
        db.commit()
        db.add(LearningConsent(user_id=sentinel, capability="chat_learning", enabled=False))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            LearningCandidate(
                user_id=sentinel,
                candidate_key="style-verbosity",
                version=1,
                candidate_type="style_preference",
                status="pending_review",
                payload_json={},
            )
        )
        db.commit()
        db.add(
            LearningCandidate(
                user_id=sentinel,
                candidate_key="style-verbosity",
                version=1,
                candidate_type="style_preference",
                status="pending_review",
                payload_json={},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.execute(delete(LearningConsent).where(LearningConsent.user_id == sentinel))
        db.execute(delete(LearningCandidate).where(LearningCandidate.user_id == sentinel))
        db.commit()
        db.close()


def test_fk_cascade_contract_is_declared():
    """Drill xoá nguồn phải chạy CASCADE ở tầng DB.

    SQLite trong suite này không bật PRAGMA foreign_keys nên không mô phỏng
    được cascade lúc chạy thật — test đây là hợp đồng DDL; drill xoá runtime
    trên PostgreSQL là việc của gate pilot (execution plan P1).
    """
    checks = {
        (LearningSignal.__tablename__, "source_message_id"): "CASCADE",
        (LearningEvidence.__tablename__, "source_message_id"): "CASCADE",
        (AssistantContextRef.__tablename__, "assistant_message_id"): "CASCADE",
    }
    for model in (LearningSignal, LearningEvidence, AssistantContextRef):
        for column in model.__table__.columns:
            if (model.__tablename__, column.name) not in checks:
                continue
            for fk in column.foreign_keys:
                assert fk.constraint.ondelete == checks[(model.__tablename__, column.name)], (
                    f"{model.__tablename__}.{column.name} phải CASCADE theo ADR-017"
                )
                # Chat message thật là conversation_messages — bảng messages
                # là email ingest từ connector (finding review 22/08).
                assert fk.column.table.name == "conversation_messages"


def test_is_learning_enabled_respects_global_kill_switch(monkeypatch):
    """Cờ tổng tắt thì worker phải dừng ngay cả khi consent của user còn True."""
    from sqlalchemy import delete

    sentinel = 9_000_002
    monkeypatch.setattr(get_settings(), "adaptive_learning_enabled", False)
    db = SessionLocal()
    try:
        db.execute(delete(LearningConsent).where(LearningConsent.user_id == sentinel))
        db.commit()
        db.add(
            LearningConsent(user_id=sentinel, capability="chat_learning", enabled=True, consented_at=datetime.now(UTC))
        )
        db.commit()
        assert is_learning_enabled(db, sentinel, "chat_learning") is False

        monkeypatch.setattr(get_settings(), "adaptive_learning_enabled", True)
        assert is_learning_enabled(db, sentinel, "chat_learning") is True
    finally:
        db.execute(delete(LearningConsent).where(LearningConsent.user_id == sentinel))
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_audit_and_reset_are_user_scoped(client):
    """B không xem được audit của A và reset của B không đụng candidate của A."""
    user_a, token_a = await _register(client)
    _, token_b = await _register(client)
    seeded = _seed_candidate(user_a, key=f"scope-{uuid.uuid4().hex[:8]}", candidate_type="routine")

    await client.post(
        f"/api/v1/adaptive-learning/candidates/{seeded.id}/reject",
        json={"reasonCodes": ["not_correct"]},
        headers={"Authorization": f"Bearer {token_a}"},
    )

    audit_b = await client.get("/api/v1/adaptive-learning/audit", headers={"Authorization": f"Bearer {token_b}"})
    assert audit_b.status_code == 200
    assert audit_b.json()["events"] == []

    reset_b = await client.delete("/api/v1/adaptive-learning?scope=all", headers={"Authorization": f"Bearer {token_b}"})
    assert reset_b.status_code == 200
    assert reset_b.json()["forgotten"] == 0

    audit_a = await client.get("/api/v1/adaptive-learning/audit", headers={"Authorization": f"Bearer {token_a}"})
    actions = [event["action"] for event in audit_a.json()["events"]]
    assert "candidate_rejected" in actions
