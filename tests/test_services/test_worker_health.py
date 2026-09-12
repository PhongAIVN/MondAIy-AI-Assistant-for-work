"""Nhịp đập của vòng nền — xem src/services/worker_health.py.

Điều đáng test không phải chuyện ghi được một dòng, mà là ba tính chất giữ cho
giám sát còn dùng được: nhịp ghi cả khi vòng KHÔNG làm gì (phân biệt "đang rảnh"
với "đã chết"), lỗi không nuốt mất nhịp, và bản thân việc đo lường không bao giờ
giết vòng lặp nó đang đo.
"""

from datetime import UTC, datetime, timedelta

from src.db import SessionLocal
from src.models.worker_heartbeat import WorkerHeartbeat
from src.services.worker_health import read_heartbeats, record_tick, record_tick_safely


def _clear(db) -> None:
    """Bảng heartbeat dùng chung một dòng cho mỗi vòng nên phải dọn giữa các test."""
    db.query(WorkerHeartbeat).delete()
    db.commit()


def test_nhip_dau_tien_tao_dong_moi():
    with SessionLocal() as db:
        _clear(db)
        row = record_tick(db, "auto_sync")

        assert row.tick_count == 1
        assert row.error_count == 0
        assert row.processed_count == 0
        # Vòng chạy trót lọt nhưng không có việc vẫn phải tính là thành công.
        assert row.last_success_at is not None


def test_nhip_cong_don_qua_nhieu_lan_goi():
    with SessionLocal() as db:
        _clear(db)
        record_tick(db, "auto_sync", processed=2)
        record_tick(db, "auto_sync", processed=3)
        row = record_tick(db, "auto_sync")

        assert row.tick_count == 3
        # processed tách khỏi tick_count: 3 vòng quét mà chỉ 5 việc được tạo.
        assert row.processed_count == 5


def test_moi_vong_giu_dong_rieng():
    with SessionLocal() as db:
        _clear(db)
        record_tick(db, "auto_sync")
        record_tick(db, "calendar_refresh")
        record_tick(db, "calendar_refresh")

        theo_ten = {row.loop: row for row in read_heartbeats(db)}
        assert theo_ten["auto_sync"].tick_count == 1
        assert theo_ten["calendar_refresh"].tick_count == 2


def test_loi_van_ghi_nhip_va_giu_moc_thanh_cong_cu():
    with SessionLocal() as db:
        _clear(db)
        record_tick(db, "auto_sync")
        thanh_cong_cu = record_tick(db, "auto_sync").last_success_at

        row = record_tick(db, "auto_sync", error=ValueError("bể rồi"))

        assert row.error_count == 1
        assert row.last_error_class == "ValueError"
        # Mốc thành công KHÔNG được nhích lên khi vòng vừa hỏng — khoảng cách
        # giữa last_tick_at và last_success_at chính là tín hiệu "quay mà hỏng".
        assert row.last_success_at == thanh_cong_cu
        assert row.last_tick_at >= row.last_success_at


def test_khong_luu_noi_dung_loi_chi_luu_ten_class():
    """PRD §13: message của lỗi connector có thể chứa email hay nội dung thật."""
    with SessionLocal() as db:
        _clear(db)
        row = record_tick(db, "auto_sync", error=RuntimeError("mail của nguyen.van.a@example.com hỏng"))

        assert row.last_error_class == "RuntimeError"
        assert "example.com" not in str(row.last_error_class)


def test_ghi_nhip_hong_khong_lam_vang_loi_ra_vong_lap(monkeypatch):
    """Giám sát không được phép giết chính thứ nó giám sát."""

    def no_bung(*args, **kwargs):
        raise RuntimeError("DB đang hiccup")

    monkeypatch.setattr("src.services.worker_health.record_tick", no_bung)
    with SessionLocal() as db:
        # Không có assert nào ngoài "không ném ra ngoài" — đó chính là hợp đồng.
        record_tick_safely(db, "auto_sync")


def test_moc_nhip_du_de_tinh_tuoi_cho_alert():
    with SessionLocal() as db:
        _clear(db)
        row = record_tick(db, "auto_sync", now=datetime.now(UTC) - timedelta(minutes=30))

        last_tick = row.last_tick_at if row.last_tick_at.tzinfo else row.last_tick_at.replace(tzinfo=UTC)
        tuoi = (datetime.now(UTC) - last_tick).total_seconds()
        assert tuoi > 60 * 25
