"""1 vòng lặp worker lỗi không được phép giết cả process — xem src/worker.py."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import worker


async def _sleep_none(_seconds):
    """Bỏ qua thời gian chờ để test không ngủ thật."""
    return None


@pytest.mark.asyncio
async def test_worker_loop_survives_exception_from_claim_next_run(monkeypatch):
    """claim_next_run() ném lỗi (vd DB hiccup) -> loop bắt lỗi, ngủ rồi thử lại,
    KHÔNG để exception văng ra ngoài (nếu văng ra, asyncio.gather() ở
    run_worker() sẽ kéo sập toàn bộ worker process)."""
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(worker_poll_seconds=0))
    monkeypatch.setattr(worker, "SessionLocal", MagicMock)
    monkeypatch.setattr(worker, "recover_stale_runs", lambda db: None)

    call_count = {"n": 0}

    def _boom(db):
        call_count["n"] += 1
        if call_count["n"] >= 3:
            raise asyncio.CancelledError  # thoát vòng lặp vô hạn để test kết thúc được
        raise RuntimeError("DB hiccup giả lập")

    monkeypatch.setattr(worker, "claim_next_run", _boom)

    with pytest.raises(asyncio.CancelledError):
        await worker._worker_loop()

    # Loop phải sống sót qua đúng 2 lần RuntimeError trước khi tự thoát ở lần 3
    # — chứng minh except Exception bắt được lỗi và vòng lặp tiếp tục.
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_worker_loop_does_not_catch_cancelled_error(monkeypatch):
    """CancelledError (dùng để dừng worker khi shutdown) KHÔNG được nuốt bởi
    except Exception — asyncio.CancelledError không kế thừa Exception nên
    tự động đi qua, nhưng test rõ ràng để tránh regression nếu ai đổi thành
    `except BaseException`."""
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(worker_poll_seconds=0))
    monkeypatch.setattr(worker, "SessionLocal", MagicMock)
    monkeypatch.setattr(worker, "recover_stale_runs", lambda db: None)

    def _cancel(db):
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "claim_next_run", _cancel)

    with pytest.raises(asyncio.CancelledError):
        await worker._worker_loop()


@pytest.mark.asyncio
async def test_vong_nhap_lich_tat_theo_mac_dinh(monkeypatch):
    """Chưa bật cờ thì vòng thoát ngay, không gọi ra ngoài mạng lần nào."""
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            program_calendar_auto_import_enabled=False,
            phoenix_ics_feed_url="https://feed.test/a.ics",
        ),
    )

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Cờ tắt mà vẫn gọi feed.")

    monkeypatch.setattr("src.services.program_calendar.refresh_from_feed", fail_if_called)

    await worker._program_calendar_loop()


@pytest.mark.asyncio
async def test_vong_nhap_lich_bat_co_nhung_thieu_url_thi_dung_lai(monkeypatch):
    """Bật cờ mà quên URL là lỗi cấu hình — dừng và ghi log, không quét rỗng mãi."""
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            program_calendar_auto_import_enabled=True,
            phoenix_ics_feed_url="",
        ),
    )

    await worker._program_calendar_loop()


@pytest.mark.asyncio
async def test_vong_nhap_lich_song_sot_khi_feed_hong(monkeypatch):
    """Feed lỗi (mạng rớt, 500) không được kéo sập worker; vòng sau vẫn phải tới."""
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(
            program_calendar_auto_import_enabled=True,
            phoenix_ics_feed_url="https://feed.test/a.ics",
            program_cohort_slug="cohort-III",
            program_calendar_import_interval_minutes=5,
        ),
    )
    monkeypatch.setattr(worker, "SessionLocal", MagicMock)
    monkeypatch.setattr(worker.asyncio, "sleep", _sleep_none)

    so_lan = {"n": 0}

    async def _boom(db, **kwargs):
        so_lan["n"] += 1
        if so_lan["n"] >= 3:
            raise asyncio.CancelledError
        raise RuntimeError("Feed trả 500")

    monkeypatch.setattr("src.services.program_calendar.refresh_from_feed", _boom)

    with pytest.raises(asyncio.CancelledError):
        await worker._program_calendar_loop()

    assert so_lan["n"] == 3


@pytest.mark.asyncio
async def test_vong_web_push_khong_gui_khi_co_tat(monkeypatch):
    """Cờ tắt thì vòng vẫn quay (để còn ghi nhịp) nhưng không giao gì.

    Khác _program_calendar_loop ở chỗ vòng này KHÔNG return khi cờ tắt: bật kênh
    lên phải có hiệu lực ngay ở nhịp sau, không cần khởi động lại container.
    """
    so_nhip = {"n": 0}

    async def _ngu(_seconds):
        so_nhip["n"] += 1
        if so_nhip["n"] >= 2:
            raise asyncio.CancelledError
        return None

    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(web_push_enabled=False, web_push_poll_seconds=0),
    )
    monkeypatch.setattr(worker.asyncio, "sleep", _ngu)

    def _fail_if_called(db, **kwargs):
        raise AssertionError("Cờ tắt mà vẫn gửi Web Push.")

    monkeypatch.setattr(worker, "deliver_due_web_push", _fail_if_called)

    with pytest.raises(asyncio.CancelledError):
        await worker._web_push_delivery_loop()

    assert so_nhip["n"] == 2


@pytest.mark.asyncio
async def test_vong_web_push_song_sot_khi_push_service_hong(monkeypatch):
    """Push service lỗi không được kéo sập worker; vòng sau vẫn phải tới."""
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(web_push_enabled=True, web_push_poll_seconds=0),
    )
    monkeypatch.setattr(worker, "SessionLocal", MagicMock)
    monkeypatch.setattr(worker.asyncio, "sleep", _sleep_none)

    so_lan = {"n": 0}

    def _boom(db, **kwargs):
        so_lan["n"] += 1
        if so_lan["n"] >= 3:
            raise asyncio.CancelledError
        raise RuntimeError("Push service trả 500")

    monkeypatch.setattr(worker, "deliver_due_web_push", _boom)

    with pytest.raises(asyncio.CancelledError):
        await worker._web_push_delivery_loop()

    assert so_lan["n"] == 3
