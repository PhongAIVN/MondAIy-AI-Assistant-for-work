"""Kiểm thử phần đọc ICS và nhập lịch chương trình (ADR-008)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.db import SessionLocal
from src.models.program_event import ProgramEvent
from src.services.program_calendar import (
    import_program_calendar,
    list_program_events,
    parse_ics,
    refresh_from_feed,
)

SAMPLE = (Path(__file__).resolve().parents[2] / "fixtures" / "v1" / "program_calendar_sample.ics").read_text(
    encoding="utf-8"
)


def _as_utc(moment: datetime) -> datetime:
    """Chuẩn hóa mốc đọc lại từ DB về UTC.

    Postgres trả về mốc có múi giờ, sqlite của test thì cắt mất tzinfo và trả về
    naive. Không chuẩn hóa thì assert so sánh chạy đúng trên CI Postgres nhưng
    lệch đúng bằng offset máy khi chạy sqlite ở local.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


@pytest.fixture
def cohort():
    """Mỗi test dùng một cohort riêng để không đọc dữ liệu của test khác."""
    slug = f"test-{uuid.uuid4().hex[:8]}"
    yield slug
    with SessionLocal() as db:
        db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == slug))
        db.commit()


def test_doc_ics_gop_dong_gap_va_bo_khoi_thieu_uid():
    events = parse_ics(SAMPLE)

    # 5 VEVENT trong fixture nhưng một khối không có UID nên phải bị loại.
    assert len(events) == 4
    workshop = next(event for event in events if event.external_id.startswith("event:"))
    # Dòng DESCRIPTION bị gấp giữa chừng: gộp sai là mất chữ "Ban to chuc".
    assert workshop.host == "Ban to chuc"
    assert "Chủ trì" not in workshop.description
    assert "Dien gia: Nguoi A, cong ty B" in workshop.description
    assert workshop.starts_at == datetime(2026, 7, 1, 13, 0, tzinfo=UTC)
    assert workshop.ends_at == datetime(2026, 7, 1, 15, 0, tzinfo=UTC)
    assert workshop.location_url == "https://example.test/room/1"


def test_loai_moc_suy_tu_tien_to_uid_va_han_nop_khong_co_moc_ket_thuc():
    by_id = {event.external_id: event for event in parse_ics(SAMPLE)}

    assert by_id["daily:2026-07-02@example.test"].event_type == "daily_deadline"
    assert by_id["gate:2026-07-10@example.test"].event_type == "gate_deadline"
    assert by_id["duty:10:1:2@example.test"].event_type == "mentor_duty"
    # DTSTART == DTEND là cách BTC ghi hạn chót, không phải sự kiện dài 0 phút.
    assert by_id["daily:2026-07-02@example.test"].ends_at is None


def test_mentor_duty_bi_danh_dau_rieng_nhom_va_khong_ra_lich_chung(cohort):
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=cohort)

        duty = next(
            event
            for event in db.query(ProgramEvent).filter(ProgramEvent.cohort_slug == cohort)
            if event.event_type == "mentor_duty"
        )
        assert duty.visibility == "team"

        chung = list_program_events(db, cohort_slug=cohort, limit=50)
        assert all(event.event_type != "mentor_duty" for event in chung)
        assert len(chung) == 3

        ca_nhom = list_program_events(db, cohort_slug=cohort, include_team_scoped=True, limit=50)
        assert len(ca_nhom) == 4


def test_nhap_lai_cung_feed_khong_nhan_ban_va_khong_bao_cap_nhat(cohort):
    with SessionLocal() as db:
        first = import_program_calendar(db, SAMPLE, cohort_slug=cohort)
        second = import_program_calendar(db, SAMPLE, cohort_slug=cohort)

        assert (first.created, first.updated, first.unchanged) == (4, 0, 0)
        # DTSTAMP giống nhau hay khác nhau không quan trọng: băm chỉ tính phần
        # nội dung, nên lần nhập thứ hai phải im lặng.
        assert (second.created, second.updated, second.unchanged) == (0, 0, 4)
        assert db.query(ProgramEvent).filter(ProgramEvent.cohort_slug == cohort).count() == 4


def test_btc_sua_gio_thi_cap_nhat_dung_dong_cu(cohort):
    doi_gio = SAMPLE.replace("DTSTART:20260701T130000Z", "DTSTART:20260701T140000Z")

    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=cohort)
        result = import_program_calendar(db, doi_gio, cohort_slug=cohort)

        assert (result.created, result.updated) == (0, 1)
        workshop = (
            db.query(ProgramEvent)
            .filter(
                ProgramEvent.cohort_slug == cohort,
                ProgramEvent.external_id == "event:101@example.test",
            )
            .one()
        )
        assert _as_utc(workshop.starts_at) == datetime(2026, 7, 1, 14, 0, tzinfo=UTC)


def test_khong_doc_lich_cua_cohort_khac(cohort):
    khac = f"{cohort}-khac"
    try:
        with SessionLocal() as db:
            import_program_calendar(db, SAMPLE, cohort_slug=khac)
            assert list_program_events(db, cohort_slug=cohort, limit=50) == []
    finally:
        with SessionLocal() as db:
            db.execute(delete(ProgramEvent).where(ProgramEvent.cohort_slug == khac))
            db.commit()


def test_loc_theo_khoang_thoi_gian_va_tu_khoa(cohort):
    with SessionLocal() as db:
        import_program_calendar(db, SAMPLE, cohort_slug=cohort)

        trong_khoang = list_program_events(
            db,
            cohort_slug=cohort,
            since=datetime(2026, 7, 5, tzinfo=UTC),
            until=datetime(2026, 7, 31, tzinfo=UTC),
            limit=50,
        )
        assert [event.external_id for event in trong_khoang] == ["gate:2026-07-10@example.test"]

        theo_tu_khoa = list_program_events(db, cohort_slug=cohort, query="MVP", limit=50)
        assert [event.external_id for event in theo_tu_khoa] == ["gate:2026-07-10@example.test"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_url", ["file:///etc/passwd", "gopher://127.0.0.1:6379/", "ftp://internal/feed.ics"])
async def test_refresh_from_feed_tu_choi_scheme_ngoai_http(bad_url):
    """feed_url không phải http/https phải bị chặn trước khi gọi mạng, để hàm
    này không thành đường đọc file cục bộ hay SSRF scheme lạ."""
    with SessionLocal() as db:
        with pytest.raises(ValueError, match="http/https"):
            await refresh_from_feed(db, feed_url=bad_url, cohort_slug="cohort-scheme-test")
