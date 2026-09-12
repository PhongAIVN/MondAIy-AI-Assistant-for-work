"""Lịch chương trình cho người dùng tier A (yêu cầu Thái 2026-08-25).

Mỗi nguồn nguồn tin có mức A/B (`SourceScope.tier`, do quản trị chương trình
gán). Người dùng được grant quyền đọc một scope tier A thì khi mở lịch, hệ
thống tự "cài" lịch chương trình từ feed ICS khai ở
`settings.tier_a_calendar_feed_url`:

1. Feed ICS → dữ liệu mondaiy: parse các VEVENT, upsert vào bộ nhớ đệm
   `calendar_events` dưới lịch ảo `_FEED_CALENDAR_ID` (khoá tự nhiên
   user + lịch + UID nên resync không tạo trùng).
2. Mondaiy → Google của user: sự kiện chưa push được tạo lên lịch primary với
   `event_id` xác định từ UID (retry không nhân bản), id Google lưu ngược vào
   `payload` để lần sync sau bỏ qua. Sự kiện đã có trên Google sẽ hiển thị ở
   lưới lịch qua đường Google thường — app không nhân bản lên hai lần.

URL feed chứa access token nên CHỈ nằm trong env của backend, không bao giờ
hardcode vào repo hay trả về client. Mọi lỗi (feed chết, Google lỗi, thiếu
quyền ghi) đều nuốt ở đây kèm log — sync chạy nền sau request đọc lịch, không
được làm trang lịch đỏ.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.calendar_event import CalendarEvent
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.services.calendar_cache import upsert_event
from src.services.connections import preferred_connection

logger = logging.getLogger(__name__)

# Debounce trong bộ nhớ của process: người dùng chuyển tuần/F5 liên tục không
# sinh thêm vòng sync. Nhiều worker thì mỗi worker tự debounce — đủ mục đích
# chống bão request, không cần Redis.
_SYNC_DEBOUNCE = timedelta(minutes=15)
_last_sync_at: dict[str, datetime] = {}


def should_sync_now(user_id: str, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    last = _last_sync_at.get(user_id)
    if last is not None and now - last < _SYNC_DEBOUNCE:
        return False
    _last_sync_at[user_id] = now
    return True


# Lịch ảo trong bộ nhớ đệm mondaiy — không tồn tại trên Google, chỉ để lưới
# lịch phân biệt nguồn hiển thị với lịch cá nhân của user.
FEED_CALENDAR_ID = "tier-a-program-feed"
FEED_CALENDAR_NAME = "Lịch chương trình"
# Google cấm event_id ngoài [a-zA-Z0-9]; tiền tố + hash UID là đủ và ổn định.
_GOOGLE_EVENT_PREFIX = "mda"
_FETCH_TIMEOUT_SECONDS = 15.0
_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}


def user_has_tier_a_access(db: Session, user_id: str, *, now: datetime | None = None) -> bool:
    """User đang giữ grant HOẠT ĐỘNG tới ít nhất một scope tier A.

    Grant phải ở trạng thái `confirmed` (đúng ngữ nghĩa admin dùng khi cấp)
    và chưa hết hạn (valid_to null hoặc còn tương lai). Revoke/expired không
    tính — mất quyền là lịch chương trình biến khỏi lần sync sau.
    """
    now = now or datetime.now(UTC)
    rows = db.execute(
        select(SourceScope.tier)
        .join(SourceScopeAccess, SourceScopeAccess.scope_id == SourceScope.id)
        .where(
            SourceScopeAccess.user_id == user_id,
            SourceScopeAccess.status == "confirmed",
            (SourceScopeAccess.valid_to.is_(None)) | (SourceScopeAccess.valid_to > now),
            SourceScope.tier == "A",
        )
        .limit(1)
    ).scalar_one_or_none()
    return rows is not None


def _unfold_ics_lines(text: str) -> list[str]:
    """Nếp gấp ICS (RFC 5545 §3.1): dòng bắt đầu bằng space/tab là continuation."""
    unfolded: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += raw[1:]
        else:
            unfolded.append(raw)
    return unfolded


def _parse_ics_datetime(value: str, tzid: str | None) -> tuple[datetime, bool] | None:
    """Trả về (moment, all_day) hoặc None nếu không hiểu — không tự đoán mốc."""
    value = value.strip()
    try:
        if len(value) == 8 and value.isdigit():
            day = datetime.strptime(value, "%Y%m%d")
            return day, True
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC), False
        if "T" in value:
            moment = datetime.strptime(value, "%Y%m%dT%H%M%S")
            tz = ZoneInfo(tzid) if tzid else None
            return (moment.replace(tzinfo=tz) if tz else moment), False
    except (ValueError, ZoneInfoNotFoundError):
        return None
    return None


def _prop(block: dict[str, str], name: str) -> str | None:
    for key, value in block.items():
        if key.split(";")[0].upper() == name:
            return value
    return None


def parse_ics(text: str) -> list[dict]:
    """Trích các VEVENT đủ dữ kiện khỏi nội dung ICS.

    Thiếu UID/SUMMARY/DTSTART thì bỏ sự kiện đó thay vì bịa; DTEND thiếu với
    sự kiện cả ngày hiểu là trọn ngày đó, với sự kiện có giờ thì bỏ.
    """
    events: list[dict] = []
    block: dict[str, str] | None = None
    for line in _unfold_ics_lines(text):
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            block = {}
            continue
        if stripped == "END:VEVENT":
            if block:
                parsed = _build_event(block)
                if parsed is not None:
                    events.append(parsed)
            block = None
            continue
        if block is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            block[key] = value

    return events


def _unescape_text(value: str) -> str:
    """RFC 5545 §3.3.11: backslash trước dau phay, cham phay, n, N la escape
    trong gia tri TEXT (viết không dấu để tránh escape sequence trong docstring)."""
    result = value.replace("\\r\\n", "\n").replace("\\n", "\n")
    result = result.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    return result


def _build_event(block: dict[str, str]) -> dict | None:
    uid = (_prop(block, "UID") or "").strip()
    title = (_prop(block, "SUMMARY") or "").strip()
    raw_start = _prop(block, "DTSTART")
    if not uid or not title or not raw_start:
        return None
    start = _parse_ics_datetime(raw_start, _prop_tzid(block, "DTSTART"))
    if start is None:
        return None
    starts_at, all_day = start

    raw_end = _prop(block, "DTEND")
    if raw_end:
        end = _parse_ics_datetime(raw_end, _prop_tzid(block, "DTEND"))
        if end is None:
            return None
        ends_at = end[0]
        if ends_at <= starts_at:
            return None
    elif all_day:
        ends_at = starts_at + timedelta(days=1)
    else:
        return None

    return {
        "uid": uid,
        "title": _unescape_text(title)[:500],
        "description": _unescape_text((_prop(block, "DESCRIPTION") or "").strip())[:2000],
        "starts_at": starts_at,
        "ends_at": ends_at,
        "all_day": all_day,
    }


def _prop_tzid(block: dict[str, str], name: str) -> str | None:
    for key in block:
        if key.split(";")[0].upper() != name:
            continue
        for part in key.split(";")[1:]:
            if part.upper().startswith("TZID="):
                return part.split("=", 1)[1].strip('"')
    return None


def _google_event_id(uid: str) -> str:
    digest = hashlib.sha1(uid.encode()).hexdigest()[:24]
    return f"{_GOOGLE_EVENT_PREFIX}{digest}"


def _feed_rows(db: Session, user_id: str) -> list[CalendarEvent]:
    return list(
        db.execute(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.calendar_id == FEED_CALENDAR_ID,
            )
        )
        .scalars()
        .all()
    )


def _google_shape(event: dict) -> dict:
    """Đóng gói sự kiện ICS thành raw dict đúng shape Google để tái dùng
    trọn bộ chuẩn hoá của calendar_cache (parse_event_window, snapshot)."""
    if event["all_day"]:
        start = {"date": event["starts_at"].date().isoformat()}
        end = {"date": event["ends_at"].date().isoformat()}
    else:
        start = {"dateTime": event["starts_at"].isoformat()}
        end = {"dateTime": event["ends_at"].isoformat()}
    return {
        "id": event["uid"],
        "summary": event["title"],
        "description": event["description"],
        "start": start,
        "end": end,
        "status": "confirmed",
    }


async def _fetch_feed(url: str) -> str:
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _connection_ready_for_push(connection) -> bool:
    if connection is None:
        return False
    granted = set((connection.scopes or "").split())
    return bool(granted.intersection(_WRITE_SCOPES))


async def sync_tier_a_calendar(db: Session, user_id: str) -> dict:
    """Chạy một vòng sync feed cho user: feed → mondaiy → Google.

    Không raise với caller (chạy nền sau request); lỗi từng bước ghi log và
    trả về trong kết quả để quan sát được qua test.
    """
    settings = get_settings()
    url = (settings.tier_a_calendar_feed_url or "").strip()
    if not url:
        return {"status": "disabled", "imported": 0, "pushed": 0}
    if not user_has_tier_a_access(db, user_id):
        return {"status": "not_tier_a", "imported": 0, "pushed": 0}

    try:
        text = await _fetch_feed(url)
    except Exception as exc:  # noqa: BLE001 - feed ngoài là nguồn không tin cậy
        # Chỉ log tên lớp lỗi: str(exc) của httpx có thể mang URL đầy đủ chứa
        # token truy cập feed vào log server.
        logger.warning("Tier-A feed fetch lỗi cho %s: %s", user_id, type(exc).__name__)
        return {"status": "fetch_error", "imported": 0, "pushed": 0}

    parsed = parse_ics(text)
    # upsert_event GHI ĐÈ payload bằng snapshot mới — marker push Google phải
    # đọc trước và gắn lại sau, nếu không lần sync thứ hai sẽ re-push toàn bộ
    # (tốn quota Google + pending_feed_events trả lại sự kiện đã push).
    markers_before = {
        row.event_id: (row.payload or {}).get("tier_a_google_event_id") for row in _feed_rows(db, user_id)
    }
    imported = 0
    for event in parsed:
        row = upsert_event(
            db,
            user_id=user_id,
            calendar_id=FEED_CALENDAR_ID,
            raw_event=_google_shape(event),
        )
        marker = markers_before.get(event["uid"])
        if marker and row is not None:
            row.payload = {**(row.payload or {}), "tier_a_google_event_id": marker}
        imported += 1

    pushed = 0
    from src.connectors.calendar import CalendarAPIError, CalendarConnector

    connection = preferred_connection(db, user_id, "google")
    if not _connection_ready_for_push(connection):
        result = {"status": "imported_no_google_write", "imported": imported, "pushed": 0}
        db.commit()
        return result

    # Session dùng autoflush=False (src/db.py) — phải flush tường minh thì
    # SELECT bên dưới mới thấy các row vừa upsert trong cùng session.
    db.flush()
    connector = CalendarConnector(connection, db)
    rows = _feed_rows(db, user_id)
    for row in rows:
        if (row.payload or {}).get("tier_a_google_event_id"):
            continue
        deterministic_id = _google_event_id(row.event_id)
        try:
            created = await connector.create_event(
                calendar_id="primary",
                title=row.title,
                description=row.description or "",
                starts_at=row.starts_at,
                ends_at=row.ends_at or row.starts_at,
                all_day=row.all_day,
                event_id=deterministic_id,
            )
            row.payload = {**(row.payload or {}), "tier_a_google_event_id": str(created["id"])}
            pushed += 1
        except CalendarAPIError as exc:
            message = str(exc)
            if "409" in message or "duplicate" in message.lower() or "already exists" in message.lower():
                # Đã có trên Google từ lượt trước — đánh dấu để không retry mãi.
                row.payload = {**(row.payload or {}), "tier_a_google_event_id": deterministic_id}
                pushed += 1
            else:
                logger.warning("Tier-A push Google lỗi cho %s/%s: %s", user_id, row.event_id, exc)
    db.commit()
    return {"status": "synced", "imported": imported, "pushed": pushed}


def pending_feed_events(db: Session, user_id: str) -> list[CalendarEvent]:
    """Sự kiện feed CHƯA có trên Google — lưới lịch merge phần này để không
    nhân bản (đã push thì hiện qua đường Google của user)."""
    return [
        row
        for row in _feed_rows(db, user_id)
        if row.status == "active" and not (row.payload or {}).get("tier_a_google_event_id")
    ]
