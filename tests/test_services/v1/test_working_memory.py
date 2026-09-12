"""Kiểm bộ nhớ ngắn hạn: cửa sổ nguyên văn, ngân sách và tóm tắt cuộn."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.conversation import Conversation, ConversationMessage
from src.services.working_memory import (
    SUMMARY_TRIGGER_TURNS,
    VERBATIM_TURNS,
    build_working_memory,
    refresh_conversation_summary,
)

_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_engine)
_SessionLocal = sessionmaker(bind=_engine)

_counter = iter(range(1, 100000))


@pytest.fixture
def db():
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def user_id() -> str:
    return f"user-{next(_counter)}"


def _conversation(db, user_id: str) -> Conversation:
    conversation = Conversation(user_id=user_id, title="Phiên test")
    db.add(conversation)
    db.commit()
    return conversation


def _them_luot(db, conversation: Conversation, so_luot: int, do_dai: int = 20) -> None:
    """Ghi xen kẽ lượt người dùng và lượt trợ lý, mốc thời gian tăng dần."""
    goc = datetime.now(UTC) - timedelta(minutes=so_luot)
    for index in range(so_luot):
        db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"{index:03d} " + "x" * do_dai,
                created_at=goc + timedelta(minutes=index),
            )
        )
    db.commit()


def test_phien_rong_tra_ve_goi_rong(db, user_id):
    conversation = _conversation(db, user_id)

    memory = build_working_memory(db, conversation)

    assert memory.turns == []
    assert memory.summary == ""


def test_chi_giu_cua_so_nguyen_van_luot_moi_nhat(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=20)

    memory = build_working_memory(db, conversation)

    assert len(memory.turns) == VERBATIM_TURNS
    assert memory.turns[-1]["content"].startswith("019")
    assert memory.turns[0]["content"].startswith("012")


def test_ngan_sach_ky_tu_cat_bot_luot_cu(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS, do_dai=100)

    memory = build_working_memory(db, conversation, char_budget=250)

    assert len(memory.turns) < VERBATIM_TURNS
    assert memory.truncated is True
    assert sum(len(turn["content"]) for turn in memory.turns) <= 250


def test_luot_moi_nhat_luon_duoc_giu_du_dai_hon_ngan_sach(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=3, do_dai=500)

    memory = build_working_memory(db, conversation, char_budget=50)

    assert len(memory.turns) == 1
    assert memory.turns[0]["content"].startswith("002")


def test_tom_tat_an_vao_ngan_sach_cua_luot_nguyen_van(db, user_id):
    conversation = _conversation(db, user_id)
    conversation.summary = "y" * 200
    db.commit()
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS, do_dai=100)

    memory = build_working_memory(db, conversation, char_budget=400)

    assert memory.summary == "y" * 200
    assert sum(len(turn["content"]) for turn in memory.turns) <= 200


@pytest.mark.asyncio
async def test_chua_du_luot_ton_dong_thi_khong_goi_model(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS + SUMMARY_TRIGGER_TURNS - 1)

    llm = AsyncMock()
    with patch("src.services.working_memory.get_llm", return_value=llm):
        assert await refresh_conversation_summary(db, conversation.id, user_id) is False

    llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_nen_ghi_tom_tat_va_doi_moc_da_nen(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS + SUMMARY_TRIGGER_TURNS)

    llm = AsyncMock()
    llm.ainvoke.return_value = AsyncMock(content="- Người dùng tên An")
    with patch("src.services.working_memory.get_llm", return_value=llm):
        assert await refresh_conversation_summary(db, conversation.id, user_id) is True

    db.refresh(conversation)
    assert conversation.summary == "- Người dùng tên An"
    assert conversation.summary_through_message_id is not None


@pytest.mark.asyncio
async def test_lan_nen_sau_chi_doc_phan_chua_nen(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS + SUMMARY_TRIGGER_TURNS)

    llm = AsyncMock()
    llm.ainvoke.return_value = AsyncMock(content="tóm tắt 1")
    with patch("src.services.working_memory.get_llm", return_value=llm):
        await refresh_conversation_summary(db, conversation.id, user_id)
        _them_luot(db, conversation, so_luot=SUMMARY_TRIGGER_TURNS)
        llm.ainvoke.return_value = AsyncMock(content="tóm tắt 2")
        await refresh_conversation_summary(db, conversation.id, user_id)

    payload = llm.ainvoke.call_args[0][0][-1][1]
    # Lượt đầu tiên đã nằm trong tóm tắt trước đó, không được gửi lại nguyên văn.
    assert "<cac_luot_moi>" in payload
    assert "000 " not in payload.split("<cac_luot_moi>")[1]


@pytest.mark.asyncio
async def test_khong_nen_hoi_thoai_cua_nguoi_khac(db, user_id):
    conversation = _conversation(db, user_id)
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS + SUMMARY_TRIGGER_TURNS)

    llm = AsyncMock()
    with patch("src.services.working_memory.get_llm", return_value=llm):
        assert await refresh_conversation_summary(db, conversation.id, "ke-khac") is False

    llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_model_hong_thi_giu_nguyen_tom_tat_cu(db, user_id):
    conversation = _conversation(db, user_id)
    conversation.summary = "tóm tắt cũ"
    db.commit()
    _them_luot(db, conversation, so_luot=VERBATIM_TURNS + SUMMARY_TRIGGER_TURNS)

    llm = AsyncMock()
    llm.ainvoke.side_effect = RuntimeError("provider chết")
    with patch("src.services.working_memory.get_llm", return_value=llm):
        assert await refresh_conversation_summary(db, conversation.id, user_id) is False

    db.refresh(conversation)
    assert conversation.summary == "tóm tắt cũ"
