"""Làm mới bộ nhớ đệm lịch ở nền cho những user tới hạn (FR-102).

Trước module này, `calendar_cache.refresh_window()` chỉ được gọi từ endpoint
`GET /calendar/events?refresh=true`. Hệ quả: lịch chỉ được đối chiếu với Google
đúng lúc người dùng mở trang lịch. Ban tổ chức dời một buổi workshop lúc 2 giờ
chiều thì tới sáng hôm sau, khi người dùng tình cờ mở lịch, họ mới biết.

Ranh giới privacy giống hệt auto_sync.py (ADR-011): module này KHÔNG tự thêm
nguồn. Nó chỉ chạm đúng những kết nối Google mà người dùng đã tự tay nối và
chưa gỡ. Không có kết nối sống thì không có gì xảy ra.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.connection import Connection
from src.services import calendar_cache

logger = logging.getLogger(__name__)

# Trạng thái kết nối coi như không dùng được — chép đúng bộ đang dùng ở
# src/api/calendar.py để hai nơi không lệch nhau khi thêm trạng thái mới.
_DEAD_STATUSES = ("disconnected", "error", "expired", "revoked")


def _refresh_window_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Cửa sổ mà vòng nền sẽ đối chiếu với Google.

    Lùi lại một chút chứ không bắt đầu từ `now`: một buổi đang diễn ra bị huỷ
    giữa chừng vẫn phải được ghi nhận. Nhìn tới hai tuần vì đó là tầm mà việc
    đổi lịch còn kịp có ích cho người dùng — xa hơn nữa thì tốn hạn mức API cho
    thông tin họ chưa cần tới.
    """
    return now - timedelta(hours=6), now + timedelta(days=14)


def find_due_connections(db: Session, now: datetime | None = None) -> list[Connection]:
    """Kết nối Google tới hạn làm mới, người lâu chưa đồng bộ nhất xếp trước.

    Cơ chế: không cần cột trạng thái mới nào — `calendar_cache.last_synced_at()`
    đã trả về mốc đồng bộ gần nhất của user, và đó chính là thứ để so với hạn.
    User chưa từng có sự kiện nào trong đệm (mốc NULL) được coi là tới hạn ngay,
    vì đó đúng là lần nạp đầu tiên.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.calendar_auto_refresh_interval_minutes)

    connections = (
        db.execute(
            select(Connection).where(
                Connection.provider == "google",
                Connection.status.notin_(_DEAD_STATUSES),
            )
        )
        .scalars()
        .all()
    )

    due: list[tuple[datetime, Connection]] = []
    for connection in connections:
        last = calendar_cache.last_synced_at(db, user_id=str(connection.user_id))
        if last is None:
            # datetime.min để nhóm chưa từng đồng bộ luôn đứng đầu hàng.
            due.append((datetime.min.replace(tzinfo=UTC), connection))
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last > cutoff:
            continue
        due.append((last, connection))

    due.sort(key=lambda pair: pair[0])
    return [connection for _, connection in due]


async def refresh_due_calendars(db: Session, now: datetime | None = None) -> int:
    """Một vòng quét: làm mới lịch cho user tới hạn, trả về số user đã xử lý.

    Một user hỏng (token hết hạn, Google 5xx) chỉ bị bỏ qua và ghi log — vòng
    sau thử lại. Để nó ném ra ngoài thì những người xếp sau trong cùng lượt sẽ
    không bao giờ tới lượt, và lỗi của một người thành lỗi của cả hệ thống.
    """
    settings = get_settings()
    if not settings.calendar_auto_refresh_enabled:
        return 0

    now = now or datetime.now(UTC)
    time_from, time_to = _refresh_window_bounds(now)

    refreshed = 0
    for connection in find_due_connections(db, now)[: settings.calendar_auto_refresh_max_users_per_tick]:
        try:
            await calendar_cache.refresh_window(
                db,
                user_id=str(connection.user_id),
                connection=connection,
                time_from=time_from,
                time_to=time_to,
            )
        except Exception as exc:  # noqa: BLE001 - xem docstring
            db.rollback()
            logger.warning(
                "Làm mới lịch nền thất bại cho user %s (%s)",
                connection.user_id,
                type(exc).__name__,
                exc_info=True,
            )
            continue
        refreshed += 1

    return refreshed
