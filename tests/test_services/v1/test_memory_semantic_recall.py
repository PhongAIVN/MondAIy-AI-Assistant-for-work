"""Kiểm truy hồi lai của ADR-006: hợp nhất RRF, đường lùi và cách ly người dùng.

Phần chạy trên sqlite kiểm logic hợp nhất và các đường lùi. Phần chạy thật trên
PostgreSQL kiểm nhánh vector — toán tử `<=>` không tồn tại trên sqlite nên nếu
chỉ giả lập thì đúng cái nguy hiểm nhất, câu SQL lọc quyền, lại không được kiểm.
"""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.db import Base
from src.models.evidence import VECTOR_DIMS
from src.models.user import User
from src.models.user_memory import UserMemory
from src.services.memory_store import (
    RRF_K,
    EvidenceRef,
    _keyword_ranks,
    _rrf_relevance,
    _semantic_enabled,
    _tokens,
    arecall,
    backfill_memory_embeddings,
    embed_memory_text,
    recall,
    record_memory,
)

_sqlite_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=_sqlite_engine)
_SqliteSession = sessionmaker(bind=_sqlite_engine)

_counter = iter(range(1, 100000))


def _vector(seed: float) -> list[float]:
    """Vector 2048 chiều cắm một giá trị vào đúng một trục.

    Hai vector khác trục thì trực giao, nên khoảng cách cosine giữa chúng là cố
    định và thứ tự KNN không phụ thuộc số dấu phẩy động.
    """
    values = [0.0] * VECTOR_DIMS
    values[int(seed) % VECTOR_DIMS] = 1.0
    return values


@pytest.fixture
def db():
    session = _SqliteSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def user_id(db) -> str:
    user = User(email=f"semantic-{next(_counter)}@example.com", password_hash="x")
    db.add(user)
    db.commit()
    return str(user.id)


def _record(db, user_id, predicate: str, value: str, kind: str = "project") -> UserMemory:
    memory = record_memory(
        db,
        user_id,
        kind=kind,
        subject="user",
        predicate=predicate,
        object_value=value,
        source_authority="user",
        created_by="user",
        evidence=[EvidenceRef("conversation_message", f"{predicate}-{value}")],
    )
    db.flush()
    return memory


def test_rrf_chuan_hoa_ve_khoang_0_1():
    ca_hai_nhanh_hang_nhat = _rrf_relevance(1, 1)
    mot_nhanh_hang_nhat = _rrf_relevance(1, None)

    assert ca_hai_nhanh_hang_nhat == pytest.approx(1.0)
    assert 0.0 < mot_nhanh_hang_nhat < ca_hai_nhanh_hang_nhat
    assert mot_nhanh_hang_nhat == pytest.approx(0.5)


def test_rrf_hang_thap_van_duong_chu_khong_bang_khong():
    assert _rrf_relevance(None, 50) > 0.0
    assert _rrf_relevance(None, 50) < _rrf_relevance(None, 2)
    # Hằng số phải dùng chung với truy hồi chunk, không được đặt riêng một giá trị.
    assert _rrf_relevance(None, 1) == pytest.approx((1.0 / (RRF_K + 1)) / (2.0 / (RRF_K + 1)))


def test_thu_hang_tu_khoa_phu_kin_moi_ung_vien(db, user_id):
    trung = _record(db, user_id, "working_on", "mondaiy")
    khong_trung = _record(db, user_id, "goal", "ra mắt sản phẩm", kind="goal")

    ranks = _keyword_ranks([trung, khong_trung], _tokens("mondaiy"), trung.last_reinforced_at)

    # Mọi fact đều có hạng, nên chế độ lai không cần sàn BASELINE_RELEVANCE nữa.
    assert set(ranks) == {trung.id, khong_trung.id}
    assert ranks[trung.id] < ranks[khong_trung.id]


def test_sqlite_khong_bat_nhanh_vector(db):
    assert _semantic_enabled(db) is False


def test_co_tat_thi_khong_nhung(monkeypatch):
    from src.services import memory_store

    settings = memory_store.get_settings()
    monkeypatch.setattr(
        memory_store,
        "get_settings",
        lambda: type("S", (), {**vars(settings), "memory_semantic_recall_enabled": False})(),
    )
    assert embed_memory_text("dự án tới đâu rồi") is None


def test_provider_nhung_hong_thi_tra_none_chu_khong_nem():
    with patch("src.services.retrieval.embed_query", side_effect=RuntimeError("provider chết")):
        assert embed_memory_text("dự án tới đâu rồi") is None


def test_nhung_hong_thi_truy_hoi_van_chay_bang_tu_khoa(db, user_id):
    _record(db, user_id, "working_on", "mondaiy")

    with patch("src.services.retrieval.embed_query", side_effect=RuntimeError("provider chết")):
        ket_qua = recall(db, user_id, "mondaiy", query_embedding=embed_memory_text("mondaiy"))

    assert [item.memory.object_json["value"] for item in ket_qua] == ["mondaiy"]
    assert ket_qua[0].vector_rank is None


def test_khong_co_vector_thi_giu_nguyen_che_do_tu_khoa(db, user_id):
    _record(db, user_id, "working_on", "mondaiy")

    ket_qua = recall(db, user_id, "mondaiy")

    # Chế độ từ khoá vẫn tính relevance bằng tỉ lệ token, không đi qua RRF.
    assert ket_qua[0].relevance == pytest.approx(1.0)
    assert ket_qua[0].vector_rank is None


def test_nhanh_vector_keo_len_fact_khong_trung_chu_nao(db, user_id):
    trung_chu = _record(db, user_id, "topic_interest", "mondaiy", kind="topic_interest")
    khong_trung_chu = _record(db, user_id, "working_on", "atlas", kind="project")

    # Giả lập nhánh vector xếp fact không trùng chữ lên hạng nhất, đúng tình
    # huống mà chế độ từ khoá thuần bỏ sót.
    with patch(
        "src.services.memory_store._vector_ranks",
        return_value={khong_trung_chu.id: 1, trung_chu.id: 2},
    ):
        ket_qua = recall(db, user_id, "mondaiy", query_embedding=_vector(1))

    assert ket_qua[0].memory.id == khong_trung_chu.id
    assert ket_qua[0].vector_rank == 1
    assert ket_qua[0].keyword_rank is not None


def test_nhanh_vector_chi_nhan_ung_vien_da_loc_quyen(db, user_id):
    """Câu SQL vector chỉ được nhìn thấy id đã qua bộ lọc user của bước 1."""
    khac = User(email=f"other-{next(_counter)}@example.com", password_hash="x")
    db.add(khac)
    db.commit()
    cua_toi = _record(db, user_id, "working_on", "mondaiy")
    cua_nguoi_khac = _record(db, str(khac.id), "working_on", "bí mật")

    ghi_lai: dict = {}

    def _spy(session, candidate_ids, embedding):
        ghi_lai["ids"] = list(candidate_ids)
        return {}

    with patch("src.services.memory_store._vector_ranks", side_effect=_spy):
        recall(db, user_id, "dự án", query_embedding=_vector(1))

    assert ghi_lai["ids"] == [cua_toi.id]
    assert cua_nguoi_khac.id not in ghi_lai["ids"]


def test_arecall_nhung_ngoai_event_loop(db, user_id):
    import asyncio

    _record(db, user_id, "working_on", "mondaiy")
    goi = {}

    def _fake_embed(value):
        goi["text"] = value
        return _vector(1)

    async def _chay():
        with patch("src.services.memory_store.embed_memory_text", _fake_embed):
            return await arecall(db, user_id, "dự án tới đâu rồi")

    ket_qua = asyncio.run(_chay())

    assert goi["text"] == "dự án tới đâu rồi"
    assert len(ket_qua) == 1


def test_backfill_khong_chay_khi_khong_phai_postgres(db, user_id):
    _record(db, user_id, "working_on", "mondaiy")

    assert backfill_memory_embeddings(db, user_id) == 0


_POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "postgresql://app:app@localhost:5433/ai20k")
_TEST_DB = "mondaiy_memory_vector_test"


def _test_database_url() -> str:
    """Dựng một database riêng cho test rồi trả URL của nó.

    Cách ly bằng database chứ không bằng schema. Dùng schema thì `search_path`
    buộc phải nhìn thấy `public` để giải được kiểu `vector`, mà thấy `public` là
    `create_all` coi bảng đã tồn tại và test ghi thẳng vào DB dev. Đã dính đúng
    lỗi đó một lần rồi, đừng lặp lại.
    """
    try:
        admin = create_engine(_POSTGRES_URL, connect_args={"connect_timeout": 3}, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{_TEST_DB}"'))
            connection.execute(text(f'CREATE DATABASE "{_TEST_DB}"'))
        admin.dispose()
    except Exception as error:  # pragma: no cover - phụ thuộc môi trường
        pytest.skip(f"Không dựng được database test cho nhánh vector: {error}")

    url = _POSTGRES_URL.rsplit("/", 1)[0] + f"/{_TEST_DB}"
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine.dispose()
    return url


def _drop_test_database() -> None:
    admin = create_engine(_POSTGRES_URL, connect_args={"connect_timeout": 3}, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{_TEST_DB}"'))
    admin.dispose()


@pytest.fixture
def pg_db():
    url = _test_database_url()
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        _drop_test_database()


@pytest.fixture
def pg_user_id(pg_db) -> str:
    user = User(email="pg-owner@example.com", password_hash="x")
    pg_db.add(user)
    pg_db.commit()
    return str(user.id)


def test_postgres_bat_nhanh_vector(pg_db):
    assert _semantic_enabled(pg_db) is True


def test_postgres_vector_xep_theo_khoang_cach_cosine(pg_db, pg_user_id):
    """Vector gần nhất đứng trên, kể cả khi nhánh từ khoá xếp nó thấp hơn.

    Đây đúng là trường hợp chế độ từ khoá thuần bỏ sót: fact đã nhúng không
    trùng chữ nào với câu hỏi, còn fact chưa nhúng thì trùng một chữ.
    """
    da_nhung = _record(pg_db, pg_user_id, "working_on", "atlas")
    da_nhung.embedding = _vector(7)
    chua_nhung = _record(pg_db, pg_user_id, "goal", "ra mắt chuyện lớn", kind="goal")
    pg_db.commit()

    ket_qua = recall(pg_db, pg_user_id, "chuyện đó tới đâu rồi", query_embedding=_vector(7))

    assert ket_qua[0].memory.id == da_nhung.id
    assert ket_qua[0].vector_rank == 1
    assert ket_qua[0].keyword_rank == 2
    # Dòng chưa có vector vẫn tìm được bằng từ khoá, chỉ xếp sau.
    thap_hon = next(item for item in ket_qua if item.memory.id == chua_nhung.id)
    assert thap_hon.vector_rank is None
    assert thap_hon.keyword_rank == 1


def test_postgres_khong_tra_memory_cua_user_khac(pg_db, pg_user_id):
    khac = User(email="pg-other@example.com", password_hash="x")
    pg_db.add(khac)
    pg_db.commit()

    cua_nguoi_khac = _record(pg_db, str(khac.id), "working_on", "bí mật của người khác")
    cua_nguoi_khac.embedding = _vector(7)
    cua_toi = _record(pg_db, pg_user_id, "goal", "việc của tôi", kind="goal")
    cua_toi.embedding = _vector(500)
    pg_db.commit()

    # Vector câu hỏi trùng khít memory của người khác: nếu bộ lọc user nằm sau
    # KNN thay vì trong câu SQL thì đúng dòng này sẽ lọt ra.
    ket_qua = recall(pg_db, pg_user_id, "bí mật", query_embedding=_vector(7))

    ids = [item.memory.id for item in ket_qua]
    assert cua_nguoi_khac.id not in ids
    assert ids == [cua_toi.id]


def test_postgres_backfill_nhung_va_ghi_ten_model(pg_db, pg_user_id):
    memory = _record(pg_db, pg_user_id, "working_on", "atlas")
    assert memory.embedding is None

    with patch("src.services.memory_store.embed_memory_text", return_value=_vector(3)):
        assert backfill_memory_embeddings(pg_db, pg_user_id) == 1

    pg_db.refresh(memory)
    assert memory.embedding is not None
    assert memory.embedding_model


def test_postgres_backfill_dung_khi_provider_hong(pg_db, pg_user_id):
    _record(pg_db, pg_user_id, "working_on", "atlas")
    _record(pg_db, pg_user_id, "goal", "ra mắt", kind="goal")
    pg_db.commit()

    with patch("src.services.memory_store.embed_memory_text", return_value=None):
        assert backfill_memory_embeddings(pg_db, pg_user_id) == 0
