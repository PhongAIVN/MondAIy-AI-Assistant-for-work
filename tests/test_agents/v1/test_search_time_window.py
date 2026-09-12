"""Cửa sổ thời gian của discord_search_program (UC-01).

Điểm dễ hỏng nhất không phải parse sai, mà là parse hỏng rồi âm thầm bỏ bộ lọc:
truy hồi trả về cả kho, model tưởng đó là kết quả của đúng tuần nó hỏi và trả
lời rất tự tin. Các test dưới đây chốt là hỏng thì phải từ chối.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.agents.tools.core_tools import (
    discord_search_program,
    reset_search_scope,
    set_search_scope,
)

_TZ = timezone(timedelta(hours=7))


@pytest.fixture(autouse=True)
def _clean_scope():
    set_search_scope(None)
    yield
    reset_search_scope()


@pytest.fixture
def captured_filters(monkeypatch):
    """Chặn truy hồi thật, giữ lại Filters mà công cụ dựng ra."""
    box = {}

    def _fake_retrieve(engine, question, filters=None, k=10, db=None):
        box["filters"] = filters
        box["question"] = question
        return []

    monkeypatch.setattr("src.services.retrieval.retrieve", _fake_retrieve)
    return box


def test_khong_truyen_moc_thi_khong_gioi_han(captured_filters):
    discord_search_program.invoke({"query": "hạn nộp"})

    assert captured_filters["filters"].since is None
    assert captured_filters["filters"].until is None


def test_truyen_moc_thi_dung_lam_bo_loc(captured_filters):
    discord_search_program.invoke({"query": "hạn nộp", "since": "03/08/2026", "until": "09/08/2026"})

    filters = captured_filters["filters"]
    assert filters.since == datetime(2026, 8, 3, 0, 0, tzinfo=_TZ)
    assert filters.until == datetime(2026, 8, 9, 0, 0, tzinfo=_TZ)


def test_moc_iso_khong_bi_doc_nguoc(captured_filters):
    """2026-08-06 là 6 tháng 8, không phải 8 tháng 6."""
    discord_search_program.invoke({"query": "hạn nộp", "since": "2026-08-06T00:00:00+07:00"})

    assert captured_filters["filters"].since.month == 8
    assert captured_filters["filters"].since.day == 6


def test_moc_hong_thi_tu_choi_chu_khong_bo_bo_loc(captured_filters):
    ket_qua = discord_search_program.invoke({"query": "hạn nộp", "since": "tuần rồi"})

    assert "Không hiểu được mốc thời gian" in ket_qua
    # Quan trọng hơn cả thông báo: không được đi truy hồi với bộ lọc rỗng.
    assert "filters" not in captured_filters


def test_khoang_nguoc_thi_tu_choi(captured_filters):
    ket_qua = discord_search_program.invoke({"query": "hạn nộp", "since": "09/08/2026", "until": "03/08/2026"})

    assert "ngược" in ket_qua
    assert "filters" not in captured_filters


def test_rong_trong_khoang_thi_noi_ro_la_trong_khoang(captured_filters):
    ket_qua = discord_search_program.invoke({"query": "hạn nộp", "since": "03/08/2026"})

    assert "trong khoảng thời gian đó" in ket_qua


def test_pham_vi_quyen_van_chan_truoc_bo_loc_thoi_gian(captured_filters):
    """Chưa đặt phạm vi thì từ chối ngay, không đụng tới tham số thời gian."""
    reset_search_scope()

    ket_qua = discord_search_program.invoke({"query": "hạn nộp", "since": "03/08/2026"})

    assert "Chưa xác định được phạm vi" in ket_qua
    assert "filters" not in captured_filters
