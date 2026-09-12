from datetime import datetime, timedelta, timezone

import pytest

from src.agents.tools import time_tool

_TZ = timezone(timedelta(hours=7))
# Thứ Bảy, để khẳng định được tên thứ trong kết quả.
_FROZEN_NOW = datetime(2026, 8, 8, 21, 30, tzinfo=_TZ)


@pytest.fixture
def frozen_now(monkeypatch):
    """Đóng băng hiện tại, nếu không test sẽ đổi kết quả theo ngày chạy."""
    monkeypatch.setattr(time_tool, "now", lambda: _FROZEN_NOW)


def test_current_datetime_tra_ngay_gio_hien_tai(frozen_now):
    ket_qua = time_tool.current_datetime.invoke({})

    assert ket_qua == "Hiện tại: 2026-08-08T21:30+07:00 (Thứ Bảy, Asia/Ho_Chi_Minh)."
    assert "Hôm qua" not in ket_qua
    assert "Ngày mai" not in ket_qua
    assert "Tuần ISO" not in ket_qua


def test_relative_time_moc_qua_khu(frozen_now):
    ket_qua = time_tool.relative_time.invoke({"timestamp": "2026-08-06T14:30:00+07:00"})

    assert "Thứ Năm, 06/08/2026" in ket_qua
    assert "2 ngày 7 giờ trước" in ket_qua


def test_relative_time_moc_tuong_lai(frozen_now):
    ket_qua = time_tool.relative_time.invoke({"timestamp": "2026-08-11T21:30:00+07:00"})

    assert "3 ngày nữa" in ket_qua


def test_relative_time_ngay_kieu_viet_doc_la_ngay_truoc_thang(frozen_now):
    """06/08 phải hiểu là 6 tháng 8, không phải 8 tháng 6."""
    ket_qua = time_tool.relative_time.invoke({"timestamp": "06/08/2026"})

    assert "06/08/2026" in ket_qua
    assert "Thứ Năm" in ket_qua


def test_relative_time_thieu_mui_gio_thi_noi_ro_dang_gia_dinh(frozen_now):
    ket_qua = time_tool.relative_time.invoke({"timestamp": "06/08/2026 14:30"})

    assert "không ghi múi giờ" in ket_qua


def test_relative_time_khong_doan_khi_khong_parse_duoc(frozen_now):
    ket_qua = time_tool.relative_time.invoke({"timestamp": "hôm bữa nào đó"})

    assert "Không hiểu được mốc thời gian" in ket_qua


def test_relative_time_chuoi_rong(frozen_now):
    assert "Chưa có mốc thời gian" in time_tool.relative_time.invoke({"timestamp": "  "})


def test_app_timezone_sai_cau_hinh_van_chay_duoc(monkeypatch):
    """Cấu hình sai không được làm chết lượt chat, chỉ rơi về giờ VN."""
    import src.agents.tools.time_tool as module

    class _Settings:
        app_timezone = "Sao/Hoa"

    monkeypatch.setattr(module, "get_settings", lambda: _Settings())
    assert module.app_timezone().key == "Asia/Ho_Chi_Minh"
