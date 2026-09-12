"""Dọn thùng rác task: xoá vĩnh viễn những gì đã quá thời hạn lưu giữ.

Hợp đồng Thái chốt (27/08): huỷ task là đưa vào thùng rác, giữ 7 ngày để lục
lại, quá hạn thì xoá hẳn.

Đây là đường DUY NHẤT trong hệ tự xoá dữ liệu người dùng mà không ai bấm nút,
nên mọi điều kiện ở đây viết tường minh, không dựa vào mặc định của tầng nào
khác. Ba ràng buộc cố ý:

- **`cancelled_at IS NULL` thì không bao giờ xoá.** Task bị huỷ trước khi có cột
  này đều mang NULL. Đoán một mốc cho chúng — lấy `updated_at` chẳng hạn — là
  xoá dữ liệu cũ của người dùng dựa trên một con số ta tự bịa ra.
- **Chỉ xoá đúng `status == "cancelled"`.** Task đã được khôi phục có
  `cancelled_at` bị xoá về NULL ở `_transition`, nhưng kiểm cả hai vẫn rẻ, và
  nó chặn được trường hợp một đường code tương lai quên xoá mốc đó.
- **Có trần mỗi vòng.** Một lần dọn dồn không được khoá bảng `tasks` quá lâu.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.task import Task

logger = logging.getLogger(__name__)


def trash_cutoff(now: datetime | None = None) -> datetime:
    """Mốc thời gian mà task huỷ trước đó là đã quá hạn lưu giữ."""
    settings = get_settings()
    current = now or datetime.now(UTC)
    return current - timedelta(days=settings.task_trash_retention_days)


def purge_expired_trash(db: Session, now: datetime | None = None) -> int:
    """Xoá vĩnh viễn task quá hạn trong thùng rác. Trả về số dòng đã xoá.

    Caller kiểm cờ `task_trash_purge_enabled` TRƯỚC khi gọi, để tắt cờ vẫn có
    hiệu lực kể cả khi hàm này bị mock trong test.
    """
    settings = get_settings()
    cutoff = trash_cutoff(now)

    rows = (
        db.execute(
            select(Task)
            .where(
                Task.status == "cancelled",
                Task.cancelled_at.is_not(None),
                Task.cancelled_at < cutoff,
            )
            .order_by(Task.cancelled_at.asc())
            .limit(settings.task_trash_purge_batch_limit)
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0

    # Ghi lại TRƯỚC khi xoá. Sau khi commit thì không còn gì để truy, nên nếu
    # ngưỡng lưu giữ từng bị đặt sai, log này là dấu vết duy nhất còn lại.
    logger.info(
        "Thùng rác task: xoá vĩnh viễn %s task huỷ trước %s (giữ %s ngày). id=%s",
        len(rows),
        cutoff.isoformat(),
        settings.task_trash_retention_days,
        [row.id for row in rows],
    )

    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)
