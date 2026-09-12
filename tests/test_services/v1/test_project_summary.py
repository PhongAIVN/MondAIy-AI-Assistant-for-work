"""Tóm tắt tổng quan dự án — và quan trọng hơn: CACHE của nó.

Sinh lại mỗi lần mở trang là đốt token cho một nội dung gần như không đổi. Cache
khoá bằng dấu vân tay tập hội thoại, không phải hạn thời gian: dự án nằm im cả
tháng thì không sinh lại vô ích, còn dự án vừa thêm hội thoại thì cập nhật ngay.
"""

import asyncio
import uuid

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.conversation import Conversation, ConversationMessage
from src.models.project import Project
from src.services import project_summary


@pytest.fixture
def project_with_chats():
    user_id = f"psum-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        project = Project(user_id=user_id, name="Bài báo NCKH", description="Viết và sửa bài báo")
        db.add(project)
        db.commit()
        db.refresh(project)

        conversation_ids = []
        for title, body in (
            ("Sửa bảng benchmark", "Rà soát lại bảng số liệu benchmark theo review."),
            ("Viết phần related work", "Bổ sung phân tích các công trình liên quan."),
        ):
            conversation = Conversation(user_id=user_id, title=title, project_id=project.id)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            db.add(
                ConversationMessage(conversation_id=conversation.id, role="user", content=body)
            )
            db.commit()
            conversation_ids.append(conversation.id)

        yield project.id, user_id, conversation_ids

        db.execute(delete(ConversationMessage).where(
            ConversationMessage.conversation_id.in_(conversation_ids)
        ))
        db.execute(delete(Conversation).where(Conversation.user_id == user_id))
        db.execute(delete(Project).where(Project.user_id == user_id))
        db.commit()


def _build(project_id: int, *, force: bool = False, calls: list | None = None):
    """Chạy build_overview với LLM giả, đếm số lần thật sự gọi model."""
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        return asyncio.run(project_summary.build_overview(db, project, language="vi", force=force))


class _FakeLLM:
    def __init__(self, calls: list) -> None:
        self._calls = calls

    async def ainvoke(self, messages):
        self._calls.append(messages)

        class _Response:
            content = "Dự án xoay quanh việc sửa bài báo NCKH theo góp ý review."

        return _Response()


@pytest.fixture
def llm_calls(monkeypatch):
    calls: list = []
    monkeypatch.setattr(project_summary, "get_settings", lambda: type("S", (), {"mock_llm": False})())
    import src.services.llm as llm_module

    monkeypatch.setattr(llm_module, "get_llm", lambda: _FakeLLM(calls))
    return calls


def test_summary_is_generated_once_and_then_served_from_cache(project_with_chats, llm_calls):
    project_id, _, _ = project_with_chats

    first = _build(project_id)
    second = _build(project_id)

    assert first.regenerated is True
    assert second.regenerated is False, "mở lại trang không được gọi LLM lần nữa"
    assert len(llm_calls) == 1
    assert first.summary == second.summary
    assert first.conversation_count == 2


def test_adding_a_conversation_invalidates_the_cache(project_with_chats, llm_calls):
    """Dấu vân tay đổi thì phải sinh lại — nếu không tóm tắt sẽ mãi kể về tập
    hội thoại cũ."""
    project_id, user_id, _ = project_with_chats
    _build(project_id)

    with SessionLocal() as db:
        extra = Conversation(user_id=user_id, title="Chuẩn bị slide bảo vệ", project_id=project_id)
        db.add(extra)
        db.commit()

    after = _build(project_id)

    assert after.regenerated is True
    assert after.conversation_count == 3
    assert len(llm_calls) == 2


def test_force_regenerates_even_when_nothing_changed(project_with_chats, llm_calls):
    project_id, _, _ = project_with_chats
    _build(project_id)

    forced = _build(project_id, force=True)

    assert forced.regenerated is True
    assert len(llm_calls) == 2


def test_emptying_a_project_clears_its_summary(project_with_chats, llm_calls):
    """Tóm tắt cũ còn lại sẽ kể về những hội thoại đã bị gỡ ra khỏi dự án."""
    project_id, user_id, conversation_ids = project_with_chats
    _build(project_id)

    with SessionLocal() as db:
        db.execute(
            Conversation.__table__.update()
            .where(Conversation.id.in_(conversation_ids))
            .values(project_id=None)
        )
        db.commit()

    after = _build(project_id)

    assert after.summary == ""
    assert after.conversation_count == 0
    with SessionLocal() as db:
        assert db.get(Project, project_id).summary == ""


def test_a_broken_llm_falls_back_to_listing_titles(project_with_chats, monkeypatch):
    """Trống trơn thì người dùng tưởng tính năng hỏng; danh sách tiêu đề vẫn cho
    thấy dự án gồm những gì."""
    project_id, _, _ = project_with_chats
    monkeypatch.setattr(project_summary, "get_settings", lambda: type("S", (), {"mock_llm": False})())
    import src.services.llm as llm_module

    def boom():
        raise RuntimeError("LLM sập")

    monkeypatch.setattr(llm_module, "get_llm", boom)

    result = _build(project_id)

    assert "Sửa bảng benchmark" in result.summary
    assert "Viết phần related work" in result.summary
