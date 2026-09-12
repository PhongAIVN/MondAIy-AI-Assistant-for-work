"""Kiểm lớp trích xuất: cái gì được vào bộ nhớ dài hạn và vào ở trạng thái nào."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.user import User
from src.services.memory_capture import capture_long_term_memory, extract_inferred_facts
from src.services.memory_store import confirm_memory, list_memories, recall

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
def user_id(db) -> str:
    user = User(email=f"capture-{next(_counter)}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return str(user.id)


def _capture(db, user_id: str, text: str):
    result = capture_long_term_memory(db, user_id, text, source_message_id=1)
    db.flush()
    return result


def test_fact_nguoi_dung_tu_khai_vao_confirmed(db, user_id):
    _capture(db, user_id, "Tôi tên là An, hãy trả lời ngắn gọn.")

    rows = {row.predicate: row for row in list_memories(db, user_id)}
    assert rows["display_name"].status == "confirmed"
    assert rows["display_name"].source_authority == "user"
    assert rows["response_style"].object_json == {"value": "ngắn gọn"}


def test_muc_tieu_va_du_an_dung_ngay_va_giu_nguon_inferred(db, user_id):
    """Auto-record 2026-08-23: fact suy ra được dùng ngay (confirmed), nguồn vẫn
    là `inferred` để giao diện nói rõ "suy ra từ hoạt động" thay vì giả vờ là
    user đã khai."""
    _capture(db, user_id, "Tôi đang làm dự án mondaiy và mục tiêu của tôi là ra mắt trong tháng này.")

    rows = {row.predicate: row for row in list_memories(db, user_id)}
    assert rows["working_on"].status == "confirmed"
    assert rows["working_on"].source_authority == "inferred"
    assert rows["goal"].status == "confirmed"
    assert rows["goal"].source_authority == "inferred"


def test_noi_dung_cong_viec_khong_tao_bo_nho_dai_han(db, user_id):
    _capture(db, user_id, "Deadline dự án là thứ Sáu và Jira đang có ba issue chưa đóng.")

    assert list_memories(db, user_id) == []


def test_moi_bo_nho_deu_co_bang_chung(db, user_id):
    from src.models.user_memory import UserMemoryEvidence

    _capture(db, user_id, "Tôi tên là An.")

    memory = list_memories(db, user_id)[0]
    rows = db.query(UserMemoryEvidence).filter_by(memory_id=memory.id).all()
    assert [(row.evidence_type, row.evidence_ref) for row in rows] == [("conversation_message", "1")]


def test_phat_bieu_moi_thay_the_phat_bieu_cu(db, user_id):
    """Auto-record 2026-08-23: hai giá trị cùng predicate không tự chọn bên thắng
    — cả hai vào `disputed` cho UI propose; xác nhận của user đóng conflict."""
    _capture(db, user_id, "Tôi tên là An.")
    _capture(db, user_id, "Thật ra tôi tên là Bình.")

    ban = {
        item.memory.object_json["value"]: item.memory
        for item in recall(db, user_id, "display_name")
        if item.memory.predicate == "display_name"
    }
    assert set(ban) == {"An", "Bình"}
    assert all(row.status == "disputed" for row in ban.values())

    memory_key = next(iter(ban.values())).memory_key
    confirm_memory(db, user_id, memory_key, version=2)
    db.flush()

    ten = [
        item.memory.object_json["value"]
        for item in recall(db, user_id, "display_name")
        if item.memory.predicate == "display_name"
    ]
    assert ten == ["Bình"]


def test_lenh_quen_ten_go_ca_lop_dai_han(db, user_id):
    _capture(db, user_id, "Tôi tên là An.")
    _capture(db, user_id, "Đừng nhớ tên tôi nữa.")

    assert recall(db, user_id, "An") == []


def test_lenh_quen_chu_de_quan_tam_go_memory_inferred(db, user_id):
    _capture(db, user_id, "Tôi rất quan tâm đến agent memory.")
    memory = next(row for row in list_memories(db, user_id) if row.predicate == "interested_in")
    memory.status = "confirmed"
    db.flush()

    _capture(db, user_id, "Đừng nhớ chủ đề quan tâm của tôi nữa.")

    assert recall(db, user_id, "agent memory") == []


def test_lenh_xoa_bo_nho_xoa_sach_lop_dai_han(db, user_id):
    _capture(db, user_id, "Tôi tên là An.")
    result = _capture(db, user_id, "Hãy xóa bộ nhớ profile của tôi.")

    assert result.cleared_all is True
    assert list_memories(db, user_id) == []


def test_mau_suy_luan_khong_bat_cau_noi_ve_nguoi_khac():
    assert extract_inferred_facts("Phong đang làm dự án khác.") == []
    assert extract_inferred_facts("") == []
