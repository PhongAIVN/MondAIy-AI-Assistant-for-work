"""Regression cho 2 bug production 22/08 + lớp intent LLM mới.

Bug gốc:
1. "mentor của tôi tên là Phạm Minh Hiếu" bị regex bắt thành display_name của
   chính user (sở hữu cách bị đọc làm chủ ngữ).
2. Không có đường nào lưu relationship/affiliation nên sang session khác agent
   không nhớ gì về mentor/team.

Quyết định của Thái: intent xác định bằng LLM nhỏ (gpt-4o-mini), regex chỉ còn
là fallback an toàn đã vá. Destructive command (quên/xoá) vẫn luật deterministic.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.user import User
from src.services.memory_capture import (
    acapture_long_term_memory,
    capture_long_term_memory,
)

_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)

_counter = iter(range(200000, 300000))

MENTOR_SENTENCE = (
    "Tôi thuộc G10 Team 004 trong chương trình AI thực chiến, "
    "ngoài ra mentor của tôi tên là Phạm Minh Hiếu"
)


@pytest.fixture
def db():
    session = _SessionLocal()
    try:
        yield session
        session.rollback()
        session.close()
    finally:
        pass


@pytest.fixture
def user_id(db) -> str:
    user = User(email=f"intent-{next(_counter)}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return str(user.id)


def _profile_rows(db, numeric_user_id: int):
    from src.models.user_memory import UserProfileMemory

    return {
        row.key: row.value
        for row in db.execute(
            select(UserProfileMemory).where(UserProfileMemory.user_id == numeric_user_id)
        ).scalars()
    }


def _memories_by_predicate(db, uid: str):
    from src.services.memory_store import list_memories

    return {row.predicate: row for row in list_memories(db, uid)}


from sqlalchemy import select  # noqa: E402

# ---------------------------------------------------------------- Bug 2: regex


def test_possessive_mentor_sentence_never_touches_identity_sync_fallback(db, user_id):
    """Câu mentor KHÔNG được vào display_name ở cả đường fallback đã vá."""
    result = capture_long_term_memory(db, user_id, MENTOR_SENTENCE)
    db.flush()

    assert "display_name" not in result.profile.updates
    rows = _profile_rows(db, int(user_id))
    assert "display_name" not in rows

    user = db.get(User, int(user_id))
    assert not user.display_name, "users.display_name bị đè bởi tên người thứ ba"


def test_own_name_still_works_after_guard(db, user_id):
    """Hai cách tự khai tên hợp lệ phải vẫn hoạt động sau khi vá sở hữu cách."""
    capture_long_term_memory(db, user_id, "Tôi tên là An")
    capture_long_term_memory(db, user_id, "Tên của tôi là Bình")
    db.flush()

    rows = _profile_rows(db, int(user_id))
    assert rows.get("display_name") in ("An", "Bình")

    user = db.get(User, int(user_id))
    assert user.display_name in ("An", "Bình")


# ------------------------------------------------- LLM intent path (async)


@pytest.fixture
def fake_intents(monkeypatch):
    """Chèn kết quả LLM giả ở ranh giới model thô — validation thật vẫn chạy."""

    def _install(facts):
        from src.config import get_settings
        from src.services import memory_intent

        # Test khép kín: không phụ thuộc OPENAI_API_KEY của máy chạy test.
        monkeypatch.setattr(get_settings(), "openai_api_key", "test-key", raising=False)

        async def _raw(text):
            return memory_intent.IntentExtraction(facts=list(facts))

        monkeypatch.setattr(memory_intent, "_extract_raw", _raw)

    return _install


@pytest.mark.asyncio
async def test_mentor_sentence_stores_relationship_not_identity(db, user_id, fake_intents):
    """Luồng LLM: mentor đi vào mentor_name (confirmed/user), danh tính nguyên vẹn."""
    from src.services.memory_intent import FactCategory

    fake_intents(
        [
            FactCategory(category="affiliation", value="G10 Team 004", entity="team", is_self=True),
            FactCategory(category="relationship", value="Phạm Minh Hiếu", entity="mentor", is_self=True),
        ]
    )

    result = await acapture_long_term_memory(db, user_id, MENTOR_SENTENCE, source_message_id=1)
    db.flush()

    rows = _memories_by_predicate(db, user_id)
    assert "display_name" not in rows
    mentor = rows["mentor_name"]
    assert mentor.status == "confirmed"
    assert mentor.source_authority == "user"
    assert mentor.object_json["value"] == "Phạm Minh Hiếu"
    assert "team_name" in rows
    assert result.profile.updates == {}

    profile = _profile_rows(db, int(user_id))
    assert "display_name" not in profile
    user = db.get(User, int(user_id))
    assert not user.display_name


@pytest.mark.asyncio
async def test_recall_finds_mentor_in_new_session(db, user_id, fake_intents):
    """Chữa bug 1: hỏi lại ở 'session khác' phải truy ra được fact mentor."""
    from src.services.memory_intent import FactCategory

    fake_intents(
        [
            FactCategory(category="relationship", value="Phạm Minh Hiếu", entity="mentor", is_self=True),
        ]
    )
    await acapture_long_term_memory(db, user_id, MENTOR_SENTENCE, source_message_id=1)
    db.commit()

    from src.services.memory_store import recall

    hits = recall(db, user_id, "Mentor của tôi tên gì")
    predicates = {row.memory.predicate for row in hits}
    assert "mentor_name" in predicates


@pytest.mark.asyncio
async def test_self_identity_via_llm_writes_profile(db, user_id, fake_intents):
    """Tự khai tên qua LLM vẫn ghi profile như kỳ vọng và đè đúng users.display_name."""
    from src.services.memory_intent import FactCategory

    fake_intents(
        [
            FactCategory(category="identity", value="An Hoài Thái", entity=None, is_self=True),
        ]
    )
    await acapture_long_term_memory(db, user_id, "Tôi là An Hoài Thái nhé", source_message_id=1)
    db.flush()

    profile = _profile_rows(db, int(user_id))
    assert profile.get("display_name") == "An Hoài Thái"

    user = db.get(User, int(user_id))
    assert user.display_name == "An Hoài Thái"


@pytest.mark.asyncio
async def test_identity_with_is_self_false_is_rejected(db, user_id, fake_intents):
    """LLM trả identity nhưng is_self=False → tuyệt đối không chạm danh tính."""
    from src.services.memory_intent import FactCategory

    fake_intents(
        [
            FactCategory(category="identity", value="Ai Đó", entity=None, is_self=False),
        ]
    )
    await acapture_long_term_memory(db, user_id, "sếp của tôi tên là Ai Đó", source_message_id=1)
    db.flush()

    rows = _memories_by_predicate(db, user_id)
    assert "display_name" not in rows
    profile = _profile_rows(db, int(user_id))
    assert "display_name" not in profile


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_regex(db, user_id, monkeypatch):
    """Model lỗi/timeout → fallback regex đã vá, đường chat không crash."""
    from src.services import memory_intent

    async def _boom(text):
        raise RuntimeError("timeout mô phỏng")

    monkeypatch.setattr(memory_intent, "_extract_raw", _boom)

    result = await acapture_long_term_memory(db, user_id, "Tôi tên là An", source_message_id=1)
    db.flush()

    assert result.profile.updates.get("display_name") == "An"
    rows = _memories_by_predicate(db, user_id)
    assert rows["display_name"].status == "confirmed"


@pytest.mark.asyncio
async def test_disabled_flag_skips_llm(db, user_id, monkeypatch):
    """Cờ global tắt → không gọi LLM, hành vi = regex đã vá."""
    from src.config import get_settings
    from src.services import memory_intent

    called = {"n": 0}

    async def _spy(text):
        called["n"] += 1
        return memory_intent.IntentExtraction(facts=[])

    monkeypatch.setattr(memory_intent, "_extract_raw", _spy)
    monkeypatch.setattr(get_settings(), "memory_intent_enabled", False)

    await acapture_long_term_memory(db, user_id, "Tôi tên là An", source_message_id=1)
    assert called["n"] == 0


def test_intent_client_retries_transient_timeouts():
    """Trace prod 24/08 (p004-production): ReadTimeout một phát với
    max_retries=0 khiến enrichment rơi regex ngay cả khi provider chỉ chậm một
    nhịp. Client phải tự thử lại lỗi thoáng qua thay vì bỏ cuộc ngay."""
    from src.services.memory_intent import _intent_client

    client = _intent_client("gpt-4o-mini", "test-key", 6.0)
    assert client.max_retries >= 1
