from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.connectors.base import Source
from src.connectors.calendar import (
    CalendarConnector,
    CalendarSyncTokenExpiredError,
    parse_event_window,
)
from src.models.calendar_event import CalendarEvent
from src.models.sync_cursor import SyncCursor

logger = logging.getLogger(__name__)

# Con trỏ đồng bộ của mỗi lịch được lưu dưới một key riêng trong `sync_cursors`.
# Prefix để không đụng key của pipeline ingest dùng chung bảng này.
_CURSOR_PREFIX = "calendar_sync_token:"


def _cursor_key(calendar_id: str) -> str:
    """Khoá con trỏ đồng bộ của một lịch cụ thể."""
    return f"{_CURSOR_PREFIX}{calendar_id}"


def read_sync_token(db: Session, user_id: str, calendar_id: str) -> str | None:
    """Đọc syncToken đã lưu; chưa có nghĩa là lần đồng bộ đầu tiên."""
    row = db.execute(
        select(SyncCursor).where(
            SyncCursor.user_id == user_id,
            SyncCursor.key == _cursor_key(calendar_id),
        )
    ).scalar_one_or_none()
    return row.value if row else None


def write_sync_token(db: Session, user_id: str, calendar_id: str, token: str | None) -> None:
    """Ghi lại syncToken sau một lần đồng bộ thành công.

    Token rỗng thì xoá con trỏ thay vì lưu chuỗi rỗng, để lần sau rơi đúng vào
    nhánh đọc lại toàn bộ chứ không gửi một token vô nghĩa lên Google.
    """
    key = _cursor_key(calendar_id)
    row = db.execute(
        select(SyncCursor).where(SyncCursor.user_id == user_id, SyncCursor.key == key)
    ).scalar_one_or_none()
    if token is None:
        if row is not None:
            db.delete(row)
        return
    if row is None:
        db.add(SyncCursor(user_id=user_id, key=key, value=token))
    else:
        row.value = token


def upsert_event(
    db: Session,
    *,
    user_id: str,
    calendar_id: str,
    raw_event: dict,
) -> CalendarEvent:
    """Ghi hoặc cập nhật một sự kiện vào bộ nhớ đệm theo khoá (user, lịch, sự kiện).

    Sự kiện Google báo `cancelled` không bị xoá khỏi bảng mà chuyển sang
    `stale`. Xoá hẳn thì lần mở lịch sau nó im lặng biến mất và người dùng
    không hiểu vì sao; giữ lại kèm trạng thái mới nói được là nguồn đã bỏ nó
    (FR-104).
    """
    event_id = str(raw_event["id"])
    row = db.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.event_id == event_id,
        )
    ).scalar_one_or_none()

    cancelled = raw_event.get("status") == "cancelled"
    if cancelled and row is None:
        # Sự kiện bị xoá trước cả khi mondaiy từng thấy nó — không có gì để lưu.
        return None  # type: ignore[return-value]

    if cancelled:
        # Báo TRƯỚC khi đổi trạng thái: sau khi ghi đè thì không còn biết buổi
        # này lẽ ra diễn ra lúc nào, mà đó là thông tin người dùng cần nhất.
        _notify_change(db, user_id=user_id, row=row, change="cancelled", starts_at=row.starts_at)
        row.status = "stale"
        row.synced_at = datetime.now(UTC)
        return row

    starts_at, ends_at, all_day = parse_event_window(raw_event)
    if row is not None and row.starts_at is not None and _lech_gio(row.starts_at, starts_at):
        _notify_change(
            db,
            user_id=user_id,
            row=row,
            change="time_changed",
            starts_at=starts_at,
            previous_starts_at=row.starts_at,
        )
    source_updated_at = _parse_source_updated_at(raw_event.get("updated"))
    values = {
        "title": raw_event.get("summary") or "(không có tiêu đề)",
        "description": raw_event.get("description") or "",
        "starts_at": starts_at,
        "ends_at": ends_at,
        "all_day": all_day,
        "status": "active",
        "deep_link": raw_event.get("htmlLink"),
        "source_updated_at": source_updated_at,
        "payload": _snapshot(raw_event),
        "synced_at": datetime.now(UTC),
    }
    if row is None:
        row = CalendarEvent(user_id=user_id, calendar_id=calendar_id, event_id=event_id, **values)
        db.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)
    return row


def _lech_gio(truoc: datetime, sau: datetime) -> bool:
    """Hai mốc bắt đầu có thật sự khác nhau không, sau khi chuẩn hoá múi giờ.

    SQLite trả lại datetime naive nên so sánh thẳng với mốc aware vừa parse từ
    Google sẽ ném TypeError. So sánh sai kiểu ở đây không chỉ là lỗi kỹ thuật:
    nó làm mọi lần đồng bộ ném lỗi và người dùng mất luôn tin lịch bị dời.
    """
    truoc_utc = truoc if truoc.tzinfo else truoc.replace(tzinfo=UTC)
    sau_utc = sau if sau.tzinfo else sau.replace(tzinfo=UTC)
    return truoc_utc != sau_utc


def _notify_change(
    db: Session,
    *,
    user_id: str,
    row: CalendarEvent,
    change: str,
    starts_at: datetime,
    previous_starts_at: datetime | None = None,
) -> None:
    """Sinh thông báo `calendar_changed` mà không cho phép nó phá đồng bộ.

    Import tại chỗ để cắt vòng phụ thuộc: reminders.py đã import từ tầng model
    và service khác, còn đây là tầng đệm nguồn. Nuốt lỗi vì đồng bộ lịch là
    việc chính, thông báo là việc phụ — mất một thông báo còn hơn hỏng cả lượt
    đồng bộ của mọi sự kiện phía sau.
    """
    from src.services.reminders import generate_calendar_change_notice

    try:
        generate_calendar_change_notice(
            db,
            user_id=user_id,
            event_id=row.event_id,
            title=row.title or "(không có tiêu đề)",
            change=change,
            starts_at=starts_at,
            previous_starts_at=previous_starts_at,
            deep_link=row.deep_link,
        )
    except Exception:  # noqa: BLE001 - xem docstring
        logger.warning("Không sinh được thông báo đổi lịch cho sự kiện %s", row.event_id, exc_info=True)


def _snapshot(raw_event: dict) -> dict:
    """Bản chụp tối thiểu đủ để dựng lại sự kiện khi hoàn tác một lần xoá.

    Chỉ giữ những trường mondaiy thật sự ghi được. Sao chép nguyên payload của
    Google vào cột JSON sẽ kéo theo email người tham dự và dữ liệu tổ chức —
    thứ P0 không xử lý và không nên lưu thêm một bản nữa.
    """
    return {
        "summary": raw_event.get("summary"),
        "description": raw_event.get("description"),
        "start": raw_event.get("start"),
        "end": raw_event.get("end"),
    }


def _parse_source_updated_at(value: str | None) -> datetime | None:
    """Đổi mốc `updated` của Google sang datetime có múi giờ."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def mark_stale(db: Session, *, user_id: str, calendar_id: str, event_id: str) -> None:
    """Đánh dấu sự kiện không còn ở nguồn, không tạo lại (FR-104)."""
    row = db.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.calendar_id == calendar_id,
            CalendarEvent.event_id == event_id,
        )
    ).scalar_one_or_none()
    if row is not None:
        row.status = "stale"
        row.synced_at = datetime.now(UTC)


def read_window(
    db: Session,
    *,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
    calendar_ids: list[str] | None = None,
) -> list[CalendarEvent]:
    """Đọc sự kiện đã lưu trong một khoảng, luôn giới hạn trong phạm vi 1 user.

    Điều kiện `user_id` nằm ngay trong truy vấn chứ không lọc sau khi lấy về:
    một lần quên lọc ở tầng Python là một lần người dùng đọc được lịch của
    người khác, và ngưỡng cho lỗi đó là 0 (FR-105).
    """
    stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status == "active",
        CalendarEvent.starts_at < time_to,
    )
    # Sự kiện không có giờ kết thúc vẫn phải lọt vào cửa sổ nếu nó bắt đầu
    # trong khoảng đang xem.
    stmt = stmt.where(
        (CalendarEvent.ends_at.is_(None) & (CalendarEvent.starts_at >= time_from)) | (CalendarEvent.ends_at > time_from)
    )
    if calendar_ids:
        stmt = stmt.where(CalendarEvent.calendar_id.in_(calendar_ids))
    stmt = stmt.order_by(CalendarEvent.starts_at)
    return list(db.execute(stmt).scalars().all())


def last_synced_at(db: Session, *, user_id: str) -> datetime | None:
    """Mốc đồng bộ gần nhất để giao diện nói rõ dữ liệu cũ tới mức nào."""
    stmt = select(CalendarEvent.synced_at).where(CalendarEvent.user_id == user_id)
    stmt = stmt.order_by(CalendarEvent.synced_at.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


async def refresh_window(
    db: Session,
    *,
    user_id: str,
    connection,
    time_from: datetime,
    time_to: datetime,
) -> dict:
    """Làm mới bộ nhớ đệm cho một khoảng thời gian trên mọi lịch nhìn thấy được.

    Cơ chế: mỗi lịch thử đồng bộ tăng dần trước bằng syncToken đã lưu; token
    hết hiệu lực hoặc chưa có thì đọc lại toàn bộ khoảng. Sau mỗi lịch mới ghi
    lại token, nên một lịch lỗi không làm mất tiến độ của các lịch còn lại —
    đúng yêu cầu một connector lỗi không chặn phần còn lại (FR-024).
    """
    connector = CalendarConnector(connection, db)
    sources = await connector.list_sources()
    if not sources:
        sources = [Source(id="primary", name="Lịch chính")]

    calendars: list[dict[str, object]] = []
    failed: list[str] = []
    upserted = 0
    for source in sources:
        calendars.append({"id": source.id, "name": source.name, "writable": source.writable})
        try:
            raw_events, next_token = await _fetch_for_refresh(connector, source, db, user_id, time_from, time_to)
        except Exception:  # noqa: BLE001 - một lịch lỗi không được chặn các lịch còn lại
            failed.append(source.id)
            continue
        for raw_event in raw_events:
            if upsert_event(db, user_id=user_id, calendar_id=source.id, raw_event=raw_event) is not None:
                upserted += 1
        write_sync_token(db, user_id, source.id, next_token)
    db.commit()
    return {"calendars": calendars, "failed_calendars": failed, "synced_count": upserted}


async def _fetch_for_refresh(
    connector: CalendarConnector,
    source: Source,
    db: Session,
    user_id: str,
    time_from: datetime,
    time_to: datetime,
) -> tuple[list[dict], str | None]:
    """Chọn giữa đồng bộ tăng dần và đọc lại toàn bộ cho một lịch."""
    sync_token = read_sync_token(db, user_id, source.id)
    if sync_token:
        try:
            return await connector.fetch_incremental(source, sync_token)
        except CalendarSyncTokenExpiredError:
            # Token hết hạn là chuyện bình thường sau vài ngày. Xoá con trỏ rồi
            # rơi xuống nhánh đọc lại toàn bộ thay vì trả lỗi cho người dùng.
            write_sync_token(db, user_id, source.id, None)
    events = await connector.fetch_range(source, time_from, time_to)
    return events, None
