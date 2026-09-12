"""Durable PostgreSQL run worker.

The API only enqueues `Run` rows. This process claims one row at a time with
SKIP LOCKED, making the queue safe to run as a separate container or replicas.
"""

from __future__ import annotations

import asyncio
import logging

from src.api.runs import _run_payload, claim_next_run, execute_run, recover_stale_runs
from src.config import get_settings
from src.db import SessionLocal
from src.langsmith_tracing import configure_langsmith_client
from src.services.auto_sync import enqueue_due_auto_syncs
from src.services.calendar_auto_refresh import refresh_due_calendars
from src.services.reminders import enqueue_due_daily_briefs
from src.services.routines import enqueue_due_routines
from src.services.task_trash import purge_expired_trash
from src.services.telegram_channel import deliver_due_notifications
from src.services.web_push import deliver_due_web_push
from src.services.worker_health import record_tick_safely

logger = logging.getLogger(__name__)


async def _worker_loop() -> None:
    settings = get_settings()
    while True:
        loi: BaseException | None = None
        try:
            with SessionLocal() as db:
                recover_stale_runs(db)
                run = claim_next_run(db)
                if run is None:
                    record_tick_safely(db, "worker")
                else:
                    payload = _run_payload(run)
                    run_id, user_id = run.id, run.user_id
                    # The execution function opens its own session; release claim session first.
                    db.expunge(run)
                    record_tick_safely(db, "worker", processed=1)
                    await execute_run(run_id, user_id, payload)
                    continue
        except Exception as exc:  # noqa: BLE001 - 1 vòng lặp lỗi (DB hiccup, deadlock,
            # row hỏng...) không được phép giết cả worker process. asyncio.gather()
            # trong run_worker() không return_exceptions=True -> 1 loop văng lỗi
            # sẽ kéo sập TẤT CẢ replica cùng lúc, container restart rồi đâm
            # đúng lỗi cũ -> crash loop im lặng, mọi Run kẹt "queued" mãi mãi
            # (đúng nguyên nhân gây "Bạn đã có một Sync đang chờ" bất tận).
            loi = exc
            logger.exception("Worker loop lỗi ngoài dự kiến - tiếp tục vòng sau, không crash process")
        if loi is not None:
            # Phiên bên trên đã đóng hoặc hỏng nên mở phiên riêng để ghi nhịp
            # lỗi — đây đúng là lúc nhịp đáng giá nhất, không được bỏ trống.
            with SessionLocal() as db:
                record_tick_safely(db, "worker", error=loi)
        await asyncio.sleep(settings.worker_poll_seconds)


async def _auto_sync_loop() -> None:
    """Vòng quét nền tạo Run cho user tới hạn — nguồn sinh việc duy nhất không
    đến từ thao tác người dùng.

    Chạy song song với các consumer loop chứ không nằm trong chúng: consumer
    có thể bận cả chục phút với một run LLM dài, mà nhịp quét phải đều đặn thì
    người dùng mới thấy dữ liệu tự mới. Cùng lý do với _worker_loop(), mọi
    Exception đều bị nuốt để một vòng hỏng không kéo sập cả process.

    Cờ bật/tắt đọc lại MỖI nhịp thay vì một lần lúc khởi động. Trước đây vòng
    này `return` khi cờ tắt, kéo theo hai hệ quả: bật auto-sync lên phải khởi
    động lại container, và suốt lúc tắt không có nhịp nào chứng minh vòng còn
    sống — không phân biệt được "đang tắt" với "đã chết".
    """
    settings = get_settings()
    while True:
        if settings.auto_sync_enabled:
            try:
                with SessionLocal() as db:
                    created = enqueue_due_auto_syncs(db)
                    record_tick_safely(db, "auto_sync", processed=created)
                if created:
                    logger.info("Auto-sync: đã xếp %s run trong vòng quét này", created)
            except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
                logger.exception("Auto-sync loop lỗi ngoài dự kiến - tiếp tục vòng sau, không crash process")
                with SessionLocal() as db:
                    record_tick_safely(db, "auto_sync", error=exc)
        await asyncio.sleep(settings.auto_sync_poll_seconds)


async def _task_trash_purge_loop() -> None:
    """Xoá vĩnh viễn task đã quá hạn nằm trong thùng rác (7 ngày, Thái chốt 27/08).

    Đây là đường DUY NHẤT trong hệ tự xoá dữ liệu người dùng mà không ai bấm nút,
    nên nó có cờ tắt riêng `task_trash_purge_enabled`: gặp nghi ngờ thì tắt job,
    thùng rác phình ra vẫn hơn mất dữ liệu.

    Đọc `get_settings()` mỗi vòng chứ không cache ngoài vòng lặp, để tắt cờ có
    hiệu lực mà không phải khởi động lại container — với một job xoá thì khoảng
    thời gian giữa "quyết định dừng" và "thật sự dừng" phải ngắn nhất có thể.
    """
    while True:
        settings = get_settings()
        if settings.task_trash_purge_enabled:
            try:
                with SessionLocal() as db:
                    deleted = purge_expired_trash(db)
                    record_tick_safely(db, "task_trash_purge", processed=deleted)
            except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
                logger.exception("Task trash purge loop lỗi ngoài dự kiến - tiếp tục vòng sau, không crash process")
                with SessionLocal() as db:
                    record_tick_safely(db, "task_trash_purge", error=exc)
        await asyncio.sleep(get_settings().task_trash_purge_poll_seconds)


async def _calendar_refresh_loop() -> None:
    """Làm mới bộ nhớ đệm lịch ở nền để phát hiện lịch bị đổi (FR-102).

    Trước vòng này, `calendar_cache.refresh_window()` chỉ có đúng một nơi gọi
    là endpoint FE — ban tổ chức dời một mốc thì không ai biết cho tới khi
    người dùng tự mở trang lịch. Vòng này gọi cùng hàm đó theo nhịp và dùng lại
    `syncToken` đã lưu, nên mỗi lượt chỉ hỏi Google phần đã thay đổi.

    Không tự thêm nguồn: chỉ chạm đúng kết nối Google người dùng đã tự nối,
    cùng ranh giới ADR-011 đặt cho auto-sync.
    """
    settings = get_settings()
    while True:
        if settings.calendar_auto_refresh_enabled:
            try:
                with SessionLocal() as db:
                    refreshed = await refresh_due_calendars(db)
                    record_tick_safely(db, "calendar_refresh", processed=refreshed)
                if refreshed:
                    logger.info("Làm mới lịch nền: đã cập nhật %s người dùng", refreshed)
            except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
                logger.exception("Vòng làm mới lịch lỗi - tiếp tục vòng sau, không crash process")
                with SessionLocal() as db:
                    record_tick_safely(db, "calendar_refresh", error=exc)
        await asyncio.sleep(settings.calendar_auto_refresh_poll_seconds)


async def _daily_brief_loop() -> None:
    """Vòng quét tổng hợp cuối ngày — không có công tắc tổng như auto_sync,
    opt-in nằm ở từng user (NotificationPreference.daily_brief_hour). Luôn
    chạy; không làm gì nếu chưa ai bật, giống lý do 2 vòng còn lại nuốt lỗi."""
    settings = get_settings()
    while True:
        try:
            with SessionLocal() as db:
                created = enqueue_due_daily_briefs(db)
                record_tick_safely(db, "daily_brief", processed=created)
            if created:
                logger.info("Daily brief: đã sinh %s thông báo trong vòng quét này", created)
        except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
            logger.exception("Daily brief loop lỗi ngoài dự kiến - tiếp tục vòng sau, không crash process")
            with SessionLocal() as db:
                record_tick_safely(db, "daily_brief", error=exc)
        await asyncio.sleep(settings.daily_brief_poll_seconds)


async def _routines_loop() -> None:
    """Vòng quét routine tới hạn (2026-08-14) — cùng khuôn `_daily_brief_loop`.

    Khác daily_brief, mỗi tick ở đây có thể gọi LLM thật (chạy agent cho routine
    tới giờ) nên có thể chậm hơn — chấp nhận cho quy mô hiện tại, xem chú thích
    ở `enqueue_due_routines` (src/services/routines.py)."""
    settings = get_settings()
    while True:
        try:
            with SessionLocal() as db:
                ran = await enqueue_due_routines(db)
                record_tick_safely(db, "routines", processed=ran)
            if ran:
                logger.info("Routines: đã chạy %s routine trong vòng quét này", ran)
        except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
            logger.exception("Routines loop lỗi ngoài dự kiến - tiếp tục vòng sau, không crash process")
            with SessionLocal() as db:
                record_tick_safely(db, "routines", error=exc)
        await asyncio.sleep(settings.routines_poll_seconds)


async def _program_calendar_loop() -> None:
    """Vòng nhập lịch chương trình từ feed ICS của ban tổ chức (ADR-008).

    Hai điều kiện phải cùng đúng mới chạy: cờ bật, và có URL feed. Thiếu một
    trong hai thì thoát ngay và ghi log lý do — im lặng không chạy là kiểu hỏng
    mà vài tuần sau mới có người phát hiện lịch đứng yên.

    Nuốt Exception giống hai vòng trên: feed hỏng hoặc mạng rớt không được phép
    kéo sập worker, và lần quét sau vẫn phải tới.
    """
    settings = get_settings()
    if not settings.program_calendar_auto_import_enabled:
        logger.info(
            "Nhập lịch chương trình tự động đang TẮT "
            "(PROGRAM_CALENDAR_AUTO_IMPORT_ENABLED=false) - nhập tay bằng "
            "scripts/import_program_calendar.py"
        )
        return
    if not settings.phoenix_ics_feed_url:
        logger.warning("Đã bật nhập lịch tự động nhưng PHOENIX_ICS_FEED_URL còn trống - không có gì để nhập")
        return

    from src.services.program_calendar import refresh_from_feed

    interval = settings.program_calendar_import_interval_minutes * 60
    while True:
        try:
            with SessionLocal() as db:
                ket_qua = await refresh_from_feed(
                    db,
                    feed_url=settings.phoenix_ics_feed_url,
                    cohort_slug=settings.program_cohort_slug,
                )
                record_tick_safely(db, "program_calendar", processed=ket_qua.created + ket_qua.updated)
            if ket_qua.created or ket_qua.updated or ket_qua.conflicts:
                logger.info(
                    "Nhập lịch %s: %d mới, %d cập nhật, %d xung đột cần người xử",
                    settings.program_cohort_slug,
                    ket_qua.created,
                    ket_qua.updated,
                    ket_qua.conflicts,
                )
        except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
            logger.exception("Vòng nhập lịch chương trình lỗi - tiếp tục vòng sau, không crash process")
            with SessionLocal() as db:
                record_tick_safely(db, "program_calendar", error=exc)
        await asyncio.sleep(interval)


async def _telegram_delivery_loop() -> None:
    """Push brief/reminder cho user đã link; flag mặc định tắt để rollback."""
    settings = get_settings()
    if not settings.telegram_delivery_enabled:
        logger.info("Telegram delivery đang TẮT (TELEGRAM_DELIVERY_ENABLED=false)")
        return
    if not settings.telegram_bot_token or not settings.telegram_webhook_secret:
        logger.error("Telegram delivery đã bật nhưng thiếu bot token hoặc webhook secret")
        return
    while True:
        try:
            with SessionLocal() as db:
                delivered = await deliver_due_notifications(db)
                record_tick_safely(db, "telegram_delivery", processed=delivered)
            if delivered:
                logger.info("Telegram delivery: đã giao %s reminder", delivered)
        except Exception as exc:  # noqa: BLE001 - một lỗi provider không kéo sập worker
            logger.exception("Telegram delivery lỗi - tiếp tục vòng sau")
            with SessionLocal() as db:
                record_tick_safely(db, "telegram_delivery", error=exc)
        await asyncio.sleep(settings.telegram_delivery_poll_seconds)


async def _web_push_delivery_loop() -> None:
    """Giao thông báo tới hạn qua Web Push cho thiết bị đã đăng ký.

    Cờ đọc lại MỖI nhịp chứ không một lần lúc khởi động, cùng lý do với
    _auto_sync_loop(): bật kênh lên không phải khởi động lại container, và lúc
    tắt vẫn có nhịp chứng minh vòng còn sống thay vì im lặng như đã chết.

    Việc gửi thật là I/O đồng bộ (pywebpush dựng trên requests) nên chạy trong
    thread riêng — gọi thẳng ở đây sẽ chặn cả event loop, kéo theo mọi vòng nền
    khác đứng chờ push service của Google/Mozilla trả lời.
    """
    settings = get_settings()
    while True:
        if settings.web_push_enabled:
            try:
                with SessionLocal() as db:
                    delivered = await asyncio.to_thread(deliver_due_web_push, db)
                    record_tick_safely(db, "web_push_delivery", processed=delivered)
                if delivered:
                    logger.info("Web Push: đã giao %s reminder", delivered)
            except Exception as exc:  # noqa: BLE001 - xem chú thích ở _worker_loop
                logger.exception("Web Push delivery lỗi - tiếp tục vòng sau")
                with SessionLocal() as db:
                    record_tick_safely(db, "web_push_delivery", error=exc)
        await asyncio.sleep(settings.web_push_poll_seconds)


async def run_worker() -> None:
    """Run bounded consumers; total active runs is also enforced at enqueue time."""
    configure_langsmith_client()
    settings = get_settings()
    await asyncio.gather(
        *(_worker_loop() for _ in range(settings.max_concurrent_runs)),
        _auto_sync_loop(),
        _task_trash_purge_loop(),
        _calendar_refresh_loop(),
        _daily_brief_loop(),
        _routines_loop(),
        _program_calendar_loop(),
        _telegram_delivery_loop(),
        _web_push_delivery_loop(),
    )


def main() -> None:
    # Format khop voi src/main.py de log 2 tien trinh (API + worker rieng)
    # doc duoc nhat quan khi debug demo.
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
