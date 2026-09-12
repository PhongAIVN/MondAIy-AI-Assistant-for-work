"""Kiểm tra logic hạn mức ghi âm: mốc ngày theo giờ Việt Nam và chống tính đôi."""

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.models.recording_quota import RecordingQuotaSlot
from src.models.user import User
from src.services.recording_quota import (
    QuotaStatus,
    consume_slot,
    daily_limit_ms,
    get_status,
    quota_day,
    slot_offset_ms,
)


def _make_user(db: Session, role: str = "user") -> User:
    """Tạo User thật trong DB vì hạn mức truy vấn theo id do DB cấp."""
    user = User(
        email=f"quota-{uuid.uuid4().hex[:12]}@example.com",
        password_hash="x",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def db() -> Iterator[Session]:
    """Session dùng chung cho một test, dọn sạch slot đã tạo khi kết thúc."""
    with SessionLocal() as session:
        yield session


def test_quota_day_dung_moc_nua_dem_gio_viet_nam() -> None:
    """23:30 UTC đã là ngày hôm sau ở Việt Nam (UTC+7), hạn mức phải reset theo đó.

    Đây là chỗ dễ sai nhất: dùng UTC thì hạn mức reset lúc 7 giờ sáng giờ Việt
    Nam, tức giữa buổi làm việc, và một cuộc họp chiều bị cắt đôi hạn mức.
    """
    assert quota_day(datetime(2026, 8, 12, 23, 30, tzinfo=UTC)) == date(2026, 8, 13)
    assert quota_day(datetime(2026, 8, 12, 16, 59, tzinfo=UTC)) == date(2026, 8, 12)
    # 17:00 UTC = 0:00 hôm sau ở Việt Nam, đúng ranh giới.
    assert quota_day(datetime(2026, 8, 12, 17, 0, tzinfo=UTC)) == date(2026, 8, 13)


def test_quota_day_nhan_datetime_o_mui_gio_khac() -> None:
    """Thời điểm ở múi giờ bất kỳ vẫn phải quy về đúng ngày Việt Nam."""
    tokyo = datetime(2026, 8, 13, 1, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert quota_day(tokyo) == date(2026, 8, 12)


def test_quota_day_tu_choi_datetime_khong_co_mui_gio() -> None:
    """Thiếu múi giờ là lỗi lập trình, phải nổ chứ không ngầm coi là UTC."""
    with pytest.raises(ValueError):
        quota_day(datetime(2026, 8, 12, 10, 0))


def test_admin_khong_bi_gioi_han_va_khong_sinh_dong_nao(db: Session) -> None:
    admin = _make_user(db, role="admin")

    status = get_status(db, admin)
    assert status.unlimited is True
    assert status.exhausted is False
    assert status.remaining_ms == daily_limit_ms()

    assert consume_slot(db, admin, note_id=1, offset_ms=0, duration_ms=20_000) is False
    count = db.query(RecordingQuotaSlot).filter_by(user_id=str(admin.id)).count()
    assert count == 0


def test_offset_lech_vai_mili_giay_roi_vao_cung_mot_lat() -> None:
    """Hai kênh cắt chunk lệch nhau vài ms phải quy về cùng mốc đầu lát."""
    assert slot_offset_ms(5_003, 5_000) == 5_000
    assert slot_offset_ms(5_047, 5_000) == 5_000
    assert slot_offset_ms(4_999, 5_000) == 0
    assert slot_offset_ms(10_000, 5_000) == 10_000


def test_slot_offset_khong_no_khi_buoc_luoi_vo_nghia() -> None:
    """Cấu hình sai không được làm sập một cuộc họp đang ghi."""
    assert slot_offset_ms(7_000, 0) == 7_000
    assert slot_offset_ms(-1, 5_000) == 0


def test_hai_kenh_cung_lat_chi_tinh_mot_lan(db: Session) -> None:
    """Mic và tab gửi cùng offset_ms là cùng một lát thời gian họp.

    Tính cả hai sẽ khiến người dùng mất một nửa hạn mức oan.
    """
    user = _make_user(db)

    assert consume_slot(db, user, note_id=3, offset_ms=20_000, duration_ms=20_000) is True
    assert consume_slot(db, user, note_id=3, offset_ms=20_000, duration_ms=20_000) is False

    assert get_status(db, user).used_ms == 20_000


def test_gui_lai_chunk_sau_loi_mang_khong_tinh_them(db: Session) -> None:
    user = _make_user(db)

    for _ in range(3):
        consume_slot(db, user, note_id=4, offset_ms=40_000, duration_ms=20_000)

    assert get_status(db, user).used_ms == 20_000


def test_cac_lat_khac_nhau_cong_don_ke_ca_khac_cuoc_hop(db: Session) -> None:
    user = _make_user(db)

    for offset in (0, 20_000, 40_000):
        consume_slot(db, user, note_id=5, offset_ms=offset, duration_ms=20_000)
    # Cuộc họp khác vẫn cộng vào cùng hạn mức của ngày.
    consume_slot(db, user, note_id=6, offset_ms=0, duration_ms=20_000)

    assert get_status(db, user).used_ms == 80_000


def test_han_muc_ngay_khac_khong_tinh_vao_hom_nay(db: Session) -> None:
    user = _make_user(db)
    hom_qua = date(2026, 8, 12)
    hom_nay = date(2026, 8, 13)

    consume_slot(db, user, note_id=7, offset_ms=0, duration_ms=20_000, day=hom_qua)
    consume_slot(db, user, note_id=7, offset_ms=20_000, duration_ms=20_000, day=hom_nay)

    assert get_status(db, user, day=hom_nay).used_ms == 20_000
    assert get_status(db, user, day=hom_qua).used_ms == 20_000


def test_nguoi_dung_moi_chua_dung_gi(db: Session) -> None:
    user = _make_user(db)
    status = get_status(db, user)

    assert status.used_ms == 0
    assert status.exhausted is False
    assert status.remaining_ms == daily_limit_ms()


def test_quota_status_kep_remaining_ve_khong_khi_vuot_han_muc() -> None:
    """Dùng lố hạn mức không được trả số âm ra cho tầng hiển thị."""
    status = QuotaStatus(limit_ms=900_000, used_ms=1_000_000, unlimited=False)

    assert status.remaining_ms == 0
    assert status.exhausted is True
