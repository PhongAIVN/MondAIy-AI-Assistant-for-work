"""Kiểm thử ranh giới quyền của tool lịch chương trình (ADR-008).

Trọng tâm không phải định dạng chuỗi trả về mà là: mức B/C không đọc được lịch,
và lịch trực riêng của một nhóm không lọt vào câu trả lời chung.
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.agents.tools.program_calendar_tool import (
    program_schedule,
    reset_program_calendar_scope,
    set_program_calendar_scope,
)
from src.db import SessionLocal
from src.models.program_event import ProgramEvent
from src.services.program_calendar import import_program_calendar

SAMPLE = (Path(__file__).resolve().parents[2] / "fixtures" / "v1" / "program_calendar_sample.ics").read_text(
    encoding="utf-8"
)


@pytest.fixture
def cohort():
    """Nhập fixture vào một cohort riêng rồi dọn sạch sau test."""
    slug = f"tool-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=slug)
    yield slug
    reset_program_calendar_scope()
    with SessionLocal() as db:
        db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == slug))
        db.commit()


def test_chua_dat_pham_vi_thi_tu_choi_doc():
    reset_program_calendar_scope()
    ket_qua = program_schedule.invoke({})
    assert "phạm vi" in ket_qua.lower()


@pytest.mark.parametrize("muc", ["B", "C"])
def test_muc_b_va_c_nhan_dung_ly_do_chu_khong_phai_lich_rong(muc, cohort):
    """Trả danh sách rỗng cho mức B/C là nói sai rằng khóa không có buổi nào."""
    set_program_calendar_scope(muc, cohort)
    try:
        ket_qua = program_schedule.invoke({})
    finally:
        reset_program_calendar_scope()

    assert "chưa khớp danh tính chương trình" in ket_qua
    assert "WORKSHOP 01" not in ket_qua


def test_muc_a_doc_duoc_lich_chung(cohort):
    set_program_calendar_scope("A", cohort)
    try:
        ket_qua = program_schedule.invoke({})
    finally:
        reset_program_calendar_scope()

    assert "WORKSHOP 01: Mo dau" in ket_qua
    assert "Han nop MVP" in ket_qua
    assert "chủ trì: Ban to chuc" in ket_qua


def test_lich_truc_cua_mot_nhom_khong_lot_vao_cau_tra_loi_chung(cohort):
    set_program_calendar_scope("A", cohort)
    try:
        ket_qua = program_schedule.invoke({"query": "Nhom 10"})
        ca_khoang = program_schedule.invoke({})
    finally:
        reset_program_calendar_scope()

    assert "Nhom 10" not in ca_khoang
    assert "Mentor cua nhom 10" not in ca_khoang
    # Hỏi thẳng tên nhóm cũng không mở được: bộ lọc nằm ở truy vấn, không ở
    # cách người dùng đặt câu hỏi.
    assert "Mentor cua nhom 10" not in ket_qua


def test_khong_doc_duoc_lich_cua_cohort_khac(cohort):
    set_program_calendar_scope("A", f"{cohort}-khong-ton-tai")
    try:
        ket_qua = program_schedule.invoke({})
    finally:
        reset_program_calendar_scope()

    assert "WORKSHOP 01" not in ket_qua
    assert "Chưa có mốc nào" in ket_qua


def test_moc_thoi_gian_hong_thi_bao_loi_thay_vi_tim_khong_gioi_han(cohort):
    set_program_calendar_scope("A", cohort)
    try:
        ket_qua = program_schedule.invoke({"since": "hôm nào đó"})
    finally:
        reset_program_calendar_scope()

    assert "mốc thời gian" in ket_qua
