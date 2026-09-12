from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, date, datetime, time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.services.connections import google

logger = logging.getLogger(__name__)
API_BASE = "https://www.googleapis.com/calendar/v3"
MAX_EVENTS = 2500
MAX_RATE_LIMIT_RETRIES = 5
# Google trả 400 cho CẢ request nếu một attendee không đúng định dạng email.
# Caller nên lọc trước, nhưng lọc lại ở đây để mọi caller của connector này
# đều an toàn, không riêng agent tool.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def build_authuser_link(url: str | None, google_email: str | None) -> str | None:
    """Ép link Google Calendar mở đúng tài khoản đã kết nối.

    Không có `authuser`, Google mở link bằng tài khoản đang active trong
    trình duyệt — sai tài khoản ngay khi người dùng đăng nhập nhiều Google
    account cùng lúc và tài khoản mặc định không phải tài khoản đã kết nối
    Mondaiy. Dùng chung cho mọi nơi trả link Calendar về người dùng (connector,
    API layer đọc bộ nhớ đệm, luồng sync task -> calendar).
    """
    if not url or not google_email:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}authuser={quote(google_email)}"


class CalendarAPIError(ConnectorAPIError):
    """Sanitized Google Calendar API error safe for API/SSE output."""


class CalendarEventNotFoundError(CalendarAPIError):
    """Sự kiện không còn ở phía Google — bên gọi đánh dấu `stale`, không tạo lại."""


class CalendarSyncTokenExpiredError(CalendarAPIError):
    """syncToken hết hạn; bên gọi phải đọc lại toàn bộ khoảng thời gian."""


#: Thông điệp nói đúng việc người dùng cần làm: lịch ngày lễ hay lịch được chia
#: sẻ dạng chỉ xem thì phải sửa ở nơi phát hành, Mondaiy không có quyền.
_LOI_CHI_DOC = (
    "Lịch này chỉ đọc (lịch ngày lễ hoặc lịch người khác chia sẻ dạng chỉ xem) "
    "nên không {hanh_dong} nó được. Hãy bỏ đăng ký lịch đó trong Google Calendar "
    "nếu không muốn thấy các sự kiện này."
)


class CalendarReadOnlyError(CalendarAPIError):
    """Google từ chối ghi (403) vì lịch đó chỉ đọc với người dùng này.

    Tách khỏi `CalendarAPIError` vì đây không phải sự cố phía Google: thử lại
    bao nhiêu lần cũng hỏng. Bên gọi phải trả 409 kèm lời giải thích, không
    phải 502.
    """


class CalendarConnector(BaseConnector):
    """Bounded Google Calendar connector.

    Event list responses already contain the fields needed for normalization;
    no unbounded mailbox-style crawl or LLM call happens here. Writes are only
    exposed through ``create_event`` and are guarded by explicit confirmation
    in the API layer.
    """

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await google.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise CalendarAPIError(f"Không lấy được access token Calendar: {exc}") from exc

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.get(f"{API_BASE}{path}", params=params)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                raise CalendarAPIError(f"Google Calendar API lỗi {response.status_code} tại {path}")
            return response.json()
        raise CalendarAPIError(f"Google Calendar API vẫn lỗi sau {MAX_RATE_LIMIT_RETRIES} lần thử")

    async def list_sources(self) -> list[Source]:
        token = await self._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            body = await self._get(client, "/users/me/calendarList", {"maxResults": 250})
        return [
            Source(
                id=str(item["id"]),
                name=item.get("summary") or item.get("summaryOverride") or str(item["id"]),
                # accessRole của Google: owner/writer ghi được, reader và
                # freeBusyReader thì không. Bỏ trường này đi chính là lý do giao
                # diện từng hiện nút Xoá trên lịch ngày lễ rồi ăn 403.
                writable=item.get("accessRole") in ("owner", "writer"),
            )
            for item in body.get("items", [])
            if item.get("id")
        ]

    async def fetch_range(
        self,
        source: Source,
        time_from: datetime,
        time_to: datetime,
        on_item: OnItemCallback | None = None,
        *,
        max_events: int | None = None,
    ) -> list[dict]:
        token = await self._access_token()
        events: list[dict] = []
        page_token: str | None = None
        event_limit = min(MAX_EVENTS, max(1, max_events or MAX_EVENTS))
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while len(events) < event_limit:
                params = {
                    "timeMin": time_from.isoformat(),
                    "timeMax": time_to.isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": min(250, event_limit - len(events)),
                }
                if page_token:
                    params["pageToken"] = page_token
                calendar_path = quote(source.id, safe="")
                body = await self._get(client, f"/calendars/{calendar_path}/events", params)
                for event in body.get("items", []):
                    if event.get("status") == "cancelled":
                        continue
                    events.append(event)
                    if on_item:
                        on_item(event, event.get("summary") or "(không có tiêu đề)")
                    if len(events) >= event_limit:
                        break
                page_token = body.get("nextPageToken")
                if not page_token or not body.get("items"):
                    break
        return events

    async def create_event(
        self,
        *,
        calendar_id: str,
        title: str,
        description: str,
        starts_at: datetime,
        ends_at: datetime,
        all_day: bool = False,
        event_id: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict:
        """Create one explicitly confirmed event in the selected calendar.

        ``event_id`` is client-generated for agent writes so retrying the same
        conversation turn cannot create a duplicate external event.
        """
        token = await self._access_token()
        calendar_path = quote(calendar_id, safe="")
        start_payload = {"date": starts_at.date().isoformat()} if all_day else {"dateTime": starts_at.isoformat()}
        end_payload = {"date": ends_at.date().isoformat()} if all_day else {"dateTime": ends_at.isoformat()}
        payload = {
            "summary": title,
            "description": description,
            "start": start_payload,
            "end": end_payload,
        }
        if event_id:
            payload["id"] = event_id
        valid_attendees = [email for email in (attendees or []) if _EMAIL_RE.match(email)]
        if valid_attendees:
            payload["attendees"] = [{"email": email} for email in valid_attendees]
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ) as client:
            response = await client.post(
                f"{API_BASE}/calendars/{calendar_path}/events",
                json=payload,
            )
            if response.status_code == 409 and event_id:
                # Google returns 409 when the client-generated ID already
                # exists. Read it back and treat the retry as success.
                return await self._get(
                    client,
                    f"/calendars/{calendar_path}/events/{quote(event_id, safe='')}",
                )
        if response.status_code == 403:
            raise CalendarReadOnlyError(_LOI_CHI_DOC.format(hanh_dong="tạo sự kiện trên"))
        if response.status_code not in (200, 201):
            raise CalendarAPIError(f"Google Calendar API lỗi {response.status_code} khi tạo sự kiện")
        body = response.json()
        if not body.get("id"):
            raise CalendarAPIError("Google Calendar không trả về mã sự kiện.")
        return body

    async def get_event(self, *, calendar_id: str, event_id: str) -> dict:
        """Đọc lại một sự kiện để xác nhận nó tồn tại trước khi sửa hoặc xoá."""
        token = await self._access_token()
        calendar_path = quote(calendar_id, safe="")
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            return await self._get(client, f"/calendars/{calendar_path}/events/{quote(event_id, safe='')}")

    async def update_event(
        self,
        *,
        calendar_id: str,
        event_id: str,
        title: str | None = None,
        description: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        all_day: bool | None = None,
    ) -> dict:
        """Sửa một sự kiện do người dùng thao tác trực tiếp (FR-069).

        Dùng PATCH chứ không PUT: người dùng kéo đổi giờ thì chỉ gửi trường
        thời gian, những trường khác của sự kiện gốc giữ nguyên. Nếu ghi đè cả
        bản ghi thì mọi thứ mondaiy chưa hiểu — nhắc nhở, màu, người tham dự —
        sẽ bị xoá sạch, và đó là mất dữ liệu thật của người dùng.

        Hàm này không tự suy ra giờ kết thúc. Caller phải truyền vào giá trị đã
        chuẩn hoá; thiếu thì trường đó không nằm trong payload.
        """
        token = await self._access_token()
        calendar_path = quote(calendar_id, safe="")
        payload: dict = {}
        if title is not None:
            payload["summary"] = title
        if description is not None:
            payload["description"] = description
        if starts_at is not None:
            payload["start"] = (
                {"date": starts_at.date().isoformat()} if all_day else {"dateTime": starts_at.isoformat()}
            )
        if ends_at is not None:
            payload["end"] = {"date": ends_at.date().isoformat()} if all_day else {"dateTime": ends_at.isoformat()}
        if not payload:
            raise CalendarAPIError("Không có trường nào để cập nhật cho sự kiện.")

        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            response = await client.patch(
                f"{API_BASE}/calendars/{calendar_path}/events/{quote(event_id, safe='')}",
                json=payload,
            )
        if response.status_code == 404:
            raise CalendarEventNotFoundError("Sự kiện không còn tồn tại trên Google Calendar.")
        if response.status_code == 403:
            raise CalendarReadOnlyError(_LOI_CHI_DOC.format(hanh_dong="sửa sự kiện trên"))
        if response.status_code != 200:
            raise CalendarAPIError(f"Google Calendar API lỗi {response.status_code} khi cập nhật sự kiện")
        return response.json()

    async def delete_event(self, *, calendar_id: str, event_id: str) -> None:
        """Xoá một sự kiện do người dùng thao tác trực tiếp (FR-069).

        Google trả 410 khi sự kiện đã bị xoá từ trước. Coi đó là thành công:
        trạng thái người dùng mong muốn đã đạt được, báo lỗi chỉ làm họ bấm
        lại một lần nữa mà không đổi được gì.
        """
        token = await self._access_token()
        calendar_path = quote(calendar_id, safe="")
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            response = await client.delete(f"{API_BASE}/calendars/{calendar_path}/events/{quote(event_id, safe='')}")
        if response.status_code in (200, 204, 410):
            return
        if response.status_code == 404:
            raise CalendarEventNotFoundError("Sự kiện không còn tồn tại trên Google Calendar.")
        if response.status_code == 403:
            raise CalendarReadOnlyError(_LOI_CHI_DOC.format(hanh_dong="xoá sự kiện khỏi"))
        raise CalendarAPIError(f"Google Calendar API lỗi {response.status_code} khi xoá sự kiện")

    async def fetch_incremental(self, source: Source, sync_token: str) -> tuple[list[dict], str | None]:
        """Chỉ lấy phần thay đổi kể từ lần đồng bộ trước (FR-103).

        Trả về cả sự kiện đã bị huỷ, khác với ``fetch_range``: bên gọi cần biết
        sự kiện nào biến mất để đánh dấu `stale` thay vì để nó nằm lại trong bộ
        nhớ đệm mãi mãi.

        Google trả 410 khi ``syncToken`` hết hiệu lực. Đó là tình huống bình
        thường sau vài ngày, không phải lỗi, nên ném ``CalendarSyncTokenExpiredError``
        để bên gọi đọc lại toàn bộ khoảng thời gian.
        """
        token = await self._access_token()
        events: list[dict] = []
        page_token: str | None = None
        next_sync_token: str | None = None
        calendar_path = quote(source.id, safe="")
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while True:
                params: dict = {"syncToken": sync_token, "singleEvents": "true", "maxResults": 250}
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(f"{API_BASE}/calendars/{calendar_path}/events", params=params)
                if response.status_code == 410:
                    raise CalendarSyncTokenExpiredError("syncToken hết hiệu lực, cần đọc lại toàn bộ khoảng thời gian.")
                if response.status_code != 200:
                    raise CalendarAPIError(f"Google Calendar API lỗi {response.status_code} khi đồng bộ tăng dần")
                body = response.json()
                events.extend(body.get("items", []))
                page_token = body.get("nextPageToken")
                next_sync_token = body.get("nextSyncToken") or next_sync_token
                if not page_token or len(events) >= MAX_EVENTS:
                    break
        return events, next_sync_token

    def normalize(self, raw_item: dict, source: Source) -> dict:
        start = raw_item.get("start", {})
        end = raw_item.get("end", {})
        start_value = start.get("dateTime") or start.get("date")
        end_value = end.get("dateTime") or end.get("date")
        all_day = "dateTime" not in start
        event_timezone = start.get("timeZone") or end.get("timeZone")
        sent_at = _event_datetime(start_value, all_day=all_day, timezone_name=event_timezone)
        display_start = _display_datetime(start_value, all_day=all_day, timezone_name=event_timezone)
        display_end = _display_datetime(end_value, all_day=all_day, timezone_name=event_timezone)
        text_parts = [raw_item.get("summary", ""), raw_item.get("description", ""), raw_item.get("location", "")]
        attendees = raw_item.get("attendees", [])
        deep_link_value = build_authuser_link(raw_item.get("htmlLink"), getattr(self._connection, "provider_user_id", None))
        return {
            "id": str(raw_item["id"]),
            "provider": "google_calendar",
            "source_id": source.id,
            "thread_id": raw_item.get("recurringEventId") or str(raw_item["id"]),
            "title": raw_item.get("summary") or "(không có tiêu đề)",
            "text": "\n".join(part for part in text_parts if part),
            "normalized_text": "\n".join(part for part in text_parts if part),
            "start_at": display_start,
            "end_at": display_end,
            # Shape chung của pipeline yêu cầu datetime để ghi cột DateTime;
            # start_at/end_at vẫn giữ chuỗi gốc để không mất timezone/all-day.
            "sent_at": sent_at,
            "all_day": all_day,
            "status": raw_item.get("status", "confirmed"),
            "organizer": raw_item.get("organizer", {}).get("email"),
            "attendees": [item.get("email") for item in attendees if item.get("email")],
            "deep_link": deep_link_value,
            "updated_at": raw_item.get("updated"),
            "evidence": {
                "event_id": str(raw_item["id"]),
                "calendar_id": source.id,
                "source_url": deep_link_value,
                "title": raw_item.get("summary") or "(không có tiêu đề)",
                "start": start_value,
                "end": end_value,
            },
        }

    def deep_link(self, raw_item: dict) -> str:
        return build_authuser_link(raw_item.get("htmlLink", ""), getattr(self._connection, "provider_user_id", None)) or ""


def parse_event_window(raw_item: dict) -> tuple[datetime, datetime | None, bool]:
    """Rút (bắt đầu, kết thúc, cả ngày) dạng datetime có múi giờ từ payload Google.

    Bộ nhớ đệm cần datetime thật để truy vấn theo khoảng, trong khi
    ``normalize`` trả chuỗi hiển thị. Tách riêng hàm này để hai nhu cầu đó
    không phải dùng chung một định dạng và không bên nào phải tự phân tích lại
    chuỗi ISO một lần nữa.
    """
    start = raw_item.get("start", {})
    end = raw_item.get("end", {})
    all_day = "dateTime" not in start
    timezone_name = start.get("timeZone") or end.get("timeZone")
    starts_at = _event_datetime(
        start.get("dateTime") or start.get("date"), all_day=all_day, timezone_name=timezone_name
    )
    end_value = end.get("dateTime") or end.get("date")
    ends_at = _event_datetime(end_value, all_day=all_day, timezone_name=timezone_name) if end_value else None
    return starts_at, ends_at, all_day


def _event_datetime(value: str | None, *, all_day: bool, timezone_name: str | None = None) -> datetime:
    if not value:
        raise ValueError("Calendar event thiếu thời gian bắt đầu.")
    if all_day:
        return datetime.combine(date.fromisoformat(value), time.min, tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(_timezone_name(timezone_name)))
    return parsed.astimezone(UTC)


def _timezone_name(timezone_name: str | None) -> str:
    return timezone_name or get_settings().app_timezone


def _display_datetime(value: str | None, *, all_day: bool, timezone_name: str | None) -> str | None:
    """Render timed Calendar values consistently in the user's app timezone."""
    if value is None or all_day:
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(_timezone_name(timezone_name)))
    return parsed.astimezone(ZoneInfo(get_settings().app_timezone)).isoformat()
