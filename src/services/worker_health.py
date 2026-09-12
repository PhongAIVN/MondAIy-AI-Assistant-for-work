"""Ghi và đọc nhịp đập của các vòng nền trong `src/worker.py`.

Đặt riêng khỏi `telemetry.py` có chủ đích: telemetry là dữ liệu sản phẩm (người
dùng làm gì), còn đây là dữ liệu vận hành (máy còn chạy không). Hai thứ khác
vòng đời, khác người đọc, và telemetry có allowlist thuộc tính theo PRD §13 mà
số liệu vận hành không cần đi qua.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.worker_heartbeat import WorkerHeartbeat

logger = logging.getLogger(__name__)


def record_tick(
    db: Session,
    loop: str,
    *,
    processed: int = 0,
    error: BaseException | None = None,
    now: datetime | None = None,
) -> WorkerHeartbeat:
    """Ghi một nhịp của vòng `loop`, tạo dòng nếu đây là nhịp đầu tiên.

    Cơ chế: đọc-hoặc-tạo theo tên vòng rồi cộng dồn tại chỗ. Chỉ có worker ghi
    bảng này và mỗi vòng ghi đúng dòng của mình, nên không cần khoá — hai
    replica cùng vòng ghi đè nhau vẫn cho ra `last_tick_at` đúng nghĩa "lần
    cuối có ai đó còn quay", là chính thứ cần theo dõi.

    `error` chỉ được lấy tên class, không lấy message: message của lỗi connector
    có thể chứa nội dung thật của người dùng (PRD §13).
    """
    now = now or datetime.now(UTC)
    row = db.execute(select(WorkerHeartbeat).where(WorkerHeartbeat.loop == loop)).scalar_one_or_none()
    if row is None:
        row = WorkerHeartbeat(loop=loop, tick_count=0, error_count=0, processed_count=0)
        db.add(row)

    row.last_tick_at = now
    row.tick_count = (row.tick_count or 0) + 1
    row.processed_count = (row.processed_count or 0) + max(0, processed)
    if error is None:
        row.last_success_at = now
    else:
        row.error_count = (row.error_count or 0) + 1
        row.last_error_class = type(error).__name__
    db.commit()
    return row


def record_tick_safely(
    db: Session,
    loop: str,
    *,
    processed: int = 0,
    error: BaseException | None = None,
) -> None:
    """Bọc `record_tick` sao cho việc đo lường không bao giờ giết vòng lặp.

    Nghịch lý cần tránh: thêm giám sát vào rồi chính nó làm sập thứ nó giám
    sát. DB hiccup lúc ghi nhịp chỉ được phép mất một điểm dữ liệu.
    """
    try:
        record_tick(db, loop, processed=processed, error=error)
    except Exception:  # noqa: BLE001 - xem docstring
        db.rollback()
        logger.warning("Không ghi được nhịp cho vòng %s", loop, exc_info=True)


def read_heartbeats(db: Session) -> list[WorkerHeartbeat]:
    """Toàn bộ nhịp đã ghi, cho tầng metrics và trang quản trị đọc chung."""
    return list(db.execute(select(WorkerHeartbeat).order_by(WorkerHeartbeat.loop)).scalars().all())
