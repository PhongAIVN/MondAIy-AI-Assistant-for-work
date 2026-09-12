"""Kiểm các bất biến của memory-lifecycle §3, §5, §6, §7, §9, §11."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.user import User
from src.models.user_memory import UserMemory
from src.services.memory_store import (
    CANDIDATE_DECAY_DAYS,
    PROMOTION_MIN_EVIDENCE,
    EvidenceRef,
    clear_memories,
    confirm_memory,
    expand_related_memories,
    forget_by_predicate,
    forget_memories,
    list_memories,
    recall,
    record_memory,
    reject_memory,
    to_prompt_payload,
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
def user_id(db) -> str:
    """Mỗi test một user riêng để dữ liệu test này không lọt sang test kia."""
    index = next(_counter)
    user = User(email=f"memory-{index}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return str(user.id)


def _evidence(ref: str) -> list[EvidenceRef]:
    return [EvidenceRef("conversation_message", ref)]


def _record(db, user_id, **overrides):
    payload = {
        "kind": "preference",
        "subject": "user",
        "predicate": "response_style",
        "object_value": "ngắn gọn",
        "source_authority": "inferred",
        "created_by": "rule",
        "evidence": _evidence("m1"),
    }
    payload.update(overrides)
    memory = record_memory(db, user_id, **payload)
    db.flush()
    return memory


def test_fact_suy_ra_dung_ngay_va_giu_nguon_inferred(db, user_id):
    """Auto-record 2026-08-23: inferred không còn chờ confirm mới dùng được;
    `source_authority` vẫn giữ để provenance phân biệt với khai báo tường minh."""
    memory = _record(db, user_id)

    assert memory.status == "confirmed"
    assert memory.source_authority == "inferred"


def test_graph_context_mo_rong_fact_cung_subject_nhung_khong_lay_candidate(db, user_id):
    _record(
        db,
        user_id,
        kind="project",
        subject="user",
        predicate="working_on",
        object_value="Dự án Alpha",
        source_authority="user",
        created_by="user",
    )
    goal = _record(
        db,
        user_id,
        kind="goal",
        subject="user",
        predicate="goal",
        object_value="Hoàn thành Alpha",
        source_authority="user",
        created_by="user",
    )
    candidate = _record(db, user_id, object_value="Alpha có màu xanh")
    candidate.status = "candidate"
    db.flush()

    seeds = recall(db, user_id, "working_on", include_candidates=False, limit=1)
    related = expand_related_memories(db, user_id, seeds)

    assert any(memory.id == goal.id and "shared_entity" in reason for memory, reason in related)
    assert all(memory.id != candidate.id for memory, _ in related)


def test_fact_nguoi_dung_tu_khai_vao_thang_confirmed(db, user_id):
    memory = _record(db, user_id, source_authority="user", created_by="user")

    assert memory.status == "confirmed"


def test_quan_sat_lai_cung_gia_tri_thi_cung_co_chu_khong_tao_ban_moi(db, user_id):
    first = _record(db, user_id)
    second = _record(db, user_id, evidence=_evidence("m2"))

    assert second.id == first.id
    assert second.reinforcement_count == 2
    assert len(list_memories(db, user_id)) == 1


def test_du_bang_chung_doc_lap_thi_luat_thang_cap_candidate(db, user_id):
    for index in range(PROMOTION_MIN_EVIDENCE):
        memory = _record(db, user_id, evidence=_evidence(f"m{index}"))

    assert memory.status == "confirmed"
    # Vẫn phải là `inferred` để giao diện nói "suy ra từ hoạt động" (§5).
    assert memory.source_authority == "inferred"


def test_phan_hoi_tieu_cuc_khong_can_thiet_cho_memory_moi(db, user_id):
    """Auto-record 2026-08-23: không còn cổng thăng cấp dựa trên phản hồi tiêu
    cực — memory sinh ra đã confirmed; việc sai phải do user xoá/sửa tường minh."""
    first = _record(db, user_id)
    first.negative_feedback_count = 1
    for index in range(PROMOTION_MIN_EVIDENCE):
        memory = _record(db, user_id, evidence=_evidence(f"n{index}"))

    assert memory.status == "confirmed"
    assert memory.id == first.id


def test_gia_tri_moi_tao_phien_ban_disputed_cho_user_phan_xu(db, user_id):
    """Auto-record 2026-08-23: giá trị mới trên cùng predicate không tự thắng —
    cả hai version vào `disputed`, vẫn truy hồi được để UI propose; chỉ
    confirm/edit của user mới đóng conflict."""
    old = _record(db, user_id, source_authority="user", created_by="user")
    old_id = old.id
    new = _record(
        db,
        user_id,
        object_value="chi tiết",
        source_authority="user",
        created_by="user",
        evidence=_evidence("m2"),
    )

    assert new.id != old_id
    assert new.version == 2
    assert new.memory_key == old.memory_key
    assert new.supersedes_id == old_id
    # Cả hai treo ở disputed, chưa bên nào bị đóng khoảng hiệu lực (§6 + conflict).
    assert new.status == "disputed"
    superseded = db.get(UserMemory, old_id)
    assert superseded.status == "disputed"
    assert superseded.valid_to is None
    assert superseded.object_json == {"value": "ngắn gọn"}

    # Người dùng chọn bên thì conflict khép lại đúng như proposal hứa.
    confirm_memory(db, user_id, new.memory_key, version=2)
    db.flush()
    assert db.get(UserMemory, new.id).status == "confirmed"
    assert db.get(UserMemory, old_id).status == "superseded"


def test_nguon_yeu_hon_khong_lat_duoc_fact_da_xac_nhan(db, user_id):
    strong = _record(db, user_id, source_authority="user", created_by="user")
    weak = _record(
        db,
        user_id,
        object_value="chi tiết",
        source_authority="inferred",
        evidence=_evidence("m2"),
    )

    # Thẩm quyền chưa rõ ràng thì cả hai treo ở `disputed`, không chọn bừa (§6).
    assert db.get(UserMemory, strong.id).status == "disputed"
    assert weak.status == "disputed"


def test_truy_hoi_tra_dung_phien_ban_theo_thoi_diem_hoi_ke_ca_khi_conflict(db, user_id):
    """§6 giữ nguyên sau auto-record: hỏi về quá khứ phải nhận giá trị hiệu lực
    tại mốc đó; ở hiện tại, hai version disputed cùng tồn tại trong kết quả để
    UI propose thay vì im lặng chọn một."""
    moc_cu = datetime.now(UTC) - timedelta(days=10)
    moc_moi = datetime.now(UTC) - timedelta(days=1)
    _record(db, user_id, source_authority="user", created_by="user", at=moc_cu)
    _record(
        db,
        user_id,
        object_value="chi tiết",
        source_authority="user",
        created_by="user",
        evidence=_evidence("m2"),
        at=moc_moi,
    )

    truoc = recall(db, user_id, "response style", at=moc_cu + timedelta(days=1))
    sau = recall(db, user_id, "response style")

    assert [item.memory.object_json["value"] for item in truoc] == ["ngắn gọn"]
    assert {item.memory.object_json["value"] for item in sau} == {"ngắn gọn", "chi tiết"}
    assert all(item.memory.status == "disputed" for item in sau)


def test_inferred_va_user_deu_confirmed_sau_auto_record(db, user_id):
    """Trước auto-record: confirmed xếp trên candidate theo STATUS_WEIGHT. Sau
    auto-record cả hai sinh ra đã confirmed nên trọng số bằng nhau — bất biến
    mới là inferred cũng xuất hiện trong truy hồi mặc định."""
    _record(
        db,
        user_id,
        predicate="timezone",
        object_value="Asia/Ho_Chi_Minh",
        source_authority="user",
        created_by="user",
        evidence=_evidence("m1"),
    )
    _record(
        db,
        user_id,
        kind="topic_interest",
        predicate="timezone_guess",
        object_value="Asia/Ho_Chi_Minh",
        evidence=_evidence("m2"),
    )

    ranked = recall(db, user_id, "Asia Ho Chi Minh")

    assert {item.memory.status for item in ranked[:2]} == {"confirmed"}
    assert ranked[0].status_weight == ranked[1].status_weight


def test_memory_cu_van_truy_hoi_duoc_khong_con_decay_candidate(db, user_id):
    """Auto-record 2026-08-23: decay CANDIDATE_DECAY_DAYS chỉ áp dụng cho status
    `candidate` nay đã vestigial — memory cũ confirmed không tự biến mất khỏi
    truy hồi chỉ vì lâu không nhắc lại; gỡ phải do user."""
    cu = datetime.now(UTC) - timedelta(days=CANDIDATE_DECAY_DAYS + 5)
    _record(db, user_id, at=cu)

    assert len(recall(db, user_id, "ngắn gọn")) == 1
    # Vẫn còn trong DB để người dùng xem và kiểm chứng (§9).
    assert len(list_memories(db, user_id)) == 1


def test_nguoi_dung_tu_choi_thi_fact_roi_khoi_truy_hoi(db, user_id):
    """Bất biến giữ nguyên qua auto-record: từ chối là gỡ khỏi truy hồi vĩnh
    viễn. Khác duy nhất: memory sinh ra confirmed nên đường state-machine đi
    sang `forgotten` thay vì `rejected` (chỉ candidate mới vào rejected)."""
    memory = _record(db, user_id)

    rejected = reject_memory(db, user_id, memory.memory_key)
    db.flush()

    assert rejected.status == "forgotten"
    assert recall(db, user_id, "ngắn gọn") == []


def test_nguoi_dung_xac_nhan_thi_fact_len_confirmed_va_thanh_tham_quyen_user(db, user_id):
    memory = _record(db, user_id)

    confirmed = confirm_memory(db, user_id, memory.memory_key)
    db.flush()

    assert confirmed.status == "confirmed"
    assert confirmed.source_authority == "user"


def test_xac_nhan_dong_lai_cac_ban_disputed_cung_key(db, user_id):
    strong = _record(db, user_id, source_authority="user", created_by="user")
    _record(
        db,
        user_id,
        object_value="chi tiết",
        source_authority="inferred",
        evidence=_evidence("m2"),
    )

    confirm_memory(db, user_id, strong.memory_key)
    db.flush()

    con_lai = [row.status for row in list_memories(db, user_id)]
    assert con_lai.count("disputed") == 0


def test_memory_khong_co_bang_chung_thi_bi_tu_choi(db, user_id):
    with pytest.raises(ValueError):
        record_memory(
            db,
            user_id,
            kind="preference",
            subject="user",
            predicate="response_style",
            object_value="ngắn gọn",
            evidence=[],
        )


def test_kind_ngoai_danh_sach_bi_tu_choi(db, user_id):
    with pytest.raises(ValueError):
        _record(db, user_id, kind="tam_ly_hoc")


def test_truy_hoi_khong_tra_memory_cua_user_khac(db, user_id):
    khac = User(email=f"other-{next(_counter)}@example.com", password_hash="x")
    db.add(khac)
    db.commit()
    _record(db, str(khac.id))

    assert recall(db, user_id, "ngắn gọn") == []


def test_payload_prompt_bao_gom_inferred_sau_auto_record(db, user_id):
    """Auto-record 2026-08-23: inferred được dùng trong ordinary response nên
    prompt payload phải chứa nó, kèm `source` để agent nói rõ mức tin."""
    _record(db, user_id)

    payload = to_prompt_payload(recall(db, user_id, "ngắn gọn"))

    assert len(payload) == 1
    assert payload[0]["status"] == "confirmed"
    assert payload[0]["source"] == "inferred"


def test_payload_prompt_giu_confirmed_va_disputed_cung_status(db, user_id):
    _record(
        db,
        user_id,
        predicate="timezone",
        object_value="Asia/Ho_Chi_Minh",
        source_authority="user",
        created_by="user",
        evidence=_evidence("timezone"),
    )
    strong = _record(db, user_id, source_authority="user", created_by="user")
    weak = _record(
        db,
        user_id,
        object_value="chi tiết",
        source_authority="inferred",
        evidence=_evidence("m2"),
    )

    payload = to_prompt_payload(recall(db, user_id, "thông tin cá nhân cách trả lời"))

    assert {item["status"] for item in payload} == {"confirmed", "disputed"}
    assert strong.status == "disputed"
    assert weak.status == "disputed"


def test_quen_theo_pham_vi_giu_lai_dong_de_kiem_chung(db, user_id):
    _record(db, user_id, predicate="display_name", kind="profile", object_value="An")

    assert forget_by_predicate(db, user_id, {"display_name"}) == 1
    db.flush()

    assert recall(db, user_id, "An") == []
    assert len(list_memories(db, user_id)) == 1


def test_xoa_tuong_minh_thi_du_lieu_bien_mat(db, user_id):
    memory = _record(db, user_id)

    assert forget_memories(db, user_id, [memory.memory_key]) == 1
    db.flush()

    assert list_memories(db, user_id) == []


def test_xoa_tat_ca_khong_cham_user_khac(db, user_id):
    khac = User(email=f"other-{next(_counter)}@example.com", password_hash="x")
    db.add(khac)
    db.commit()
    _record(db, user_id)
    _record(db, str(khac.id))

    clear_memories(db, user_id)
    db.flush()

    assert list_memories(db, user_id) == []
    assert len(list_memories(db, str(khac.id))) == 1


def test_bang_chung_trung_khong_bi_ghi_hai_lan(db, user_id):
    _record(db, user_id)
    _record(db, user_id)
    db.flush()

    from src.models.user_memory import UserMemoryEvidence

    rows = db.execute(select(UserMemoryEvidence)).scalars().all()
    assert len(rows) == 1
