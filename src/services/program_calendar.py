"""Nhập và đọc lịch chương trình từ ICS feed của ban tổ chức.

Ban tổ chức không mở API cho bên thứ ba; thứ duy nhất họ phát ra là một feed
`.ics` chuẩn iCalendar. Module này tự phân tích ICS thay vì thêm thư viện: phần
cần dùng chỉ là VEVENT phẳng, không RRULE, không VTIMEZONE, và mọi mốc đều là
UTC dạng `Z` — thêm một phụ thuộc cho từng đó việc là đắt hơn giá trị nhận về.

Ranh giới quyền nằm ở tầng tool (`program_calendar_tool`), không nằm ở đây.
Module này chỉ chịu trách nhiệm: đọc đúng, ghi đúng, và đánh dấu sự kiện nào là
của riêng một nhóm.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.program_event import ProgramEvent
from src.services.program_cohorts import normalize_program_cohort_slug

logger = logging.getLogger(__name__)

# Tiền tố UID của Phoenix mã hóa luôn loại mốc, ví dụ "daily:2026-07-25@...".
# Đây là dữ liệu của BTC nên bảng ánh xạ đặt ở một chỗ, không rải trong code.
_UID_PREFIX_TO_TYPE = {
    "event": "custom",
    "daily": "daily_deadline",
    "weekly": "weekly_deadline",
    "gate": "gate_deadline",
    "duty": "mentor_duty",
}

# Loại sự kiện chỉ liên quan tới một nhóm mentor. Không phải bí mật, nhưng đưa
# vào lịch chung là trả lời sai người: học viên nhóm khác nhận được giờ trực của
# nhóm không phải của mình và tưởng đó là lịch của mình.
TEAM_SCOPED_TYPES = frozenset({"mentor_duty"})

# "Chủ trì: X" là cách Phoenix nhét người phụ trách vào DESCRIPTION của ICS.
# Tách ra thành cột riêng để câu trả lời nêu được ai chủ trì mà không phải in cả
# đoạn mô tả.
_HOST_PATTERN = re.compile(r"^Chủ trì:\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedEvent:
    """Một VEVENT đã đọc xong, chưa gắn vào cohort nào."""

    external_id: str
    event_type: str
    visibility: str
    title: str
    description: str
    host: str | None
    location_url: str | None
    starts_at: datetime
    ends_at: datetime | None
    source_updated_at: datetime | None

    @property
    def content_hash(self) -> str:
        """Băm phần nội dung người đọc nhìn thấy, không băm mốc quan sát.

        DTSTAMP đổi mỗi lần BTC sinh lại feed dù không sửa gì; băm cả nó vào thì
        lần nhập nào cũng báo "đã cập nhật" và ta mất khả năng biết BTC có thật
        sự đổi lịch hay không.
        """
        payload = " ".join(
            [
                self.title,
                self.description,
                self.host or "",
                self.location_url or "",
                self.starts_at.isoformat(),
                self.ends_at.isoformat() if self.ends_at else "",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ImportResult:
    """Kết quả một lần nhập feed, đủ để script in ra và test khẳng định."""

    created: int
    updated: int
    unchanged: int
    # Mốc quản trị đã nhận về tay nên lần nhập này không đụng tới (ADR-010).
    skipped_admin: int = 0
    # Mốc mà feed đổi đúng vào trường quản trị đang giữ — cần người xử.
    conflicts: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged + self.skipped_admin


def _unfold(raw: str) -> list[str]:
    """Gộp các dòng bị gấp của ICS về lại một dòng.

    RFC 5545 cho phép cắt dòng dài rồi nối tiếp bằng một dòng bắt đầu bằng dấu
    cách hoặc tab. Tách theo `\n` mà không gộp lại thì mọi mô tả dài đều mất
    đuôi, và tệ hơn là mất im lặng.
    """
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _unescape(value: str) -> str:
    """Trả text về dạng người đọc: `\\n` thành xuống dòng, bỏ escape dấu phẩy."""
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            following = value[index + 1]
            out.append({"n": "\n", "N": "\n"}.get(following, following))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _parse_moment(value: str) -> datetime | None:
    """Đọc mốc ICS dạng `20260724T130000Z` hoặc `20260724`.

    Trả None thay vì ném lỗi: một VEVENT hỏng không được làm hỏng cả lần nhập.
    """
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        if "T" in text:
            # Không có Z và feed không gửi VTIMEZONE — coi là UTC và ghi log,
            # vì đoán múi giờ ở đây là đoán sai giờ họp của người dùng.
            logger.warning("Mốc ICS không có múi giờ: %s, tạm coi là UTC", text)
            return datetime.strptime(text, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
        return datetime.strptime(text, "%Y%m%d").replace(tzinfo=UTC)
    except ValueError:
        logger.warning("Không đọc được mốc ICS: %s", text)
        return None


def _event_type(uid: str) -> str:
    """Suy loại mốc từ tiền tố UID; không nhận ra thì coi là sự kiện thường."""
    prefix = uid.split(":", 1)[0].strip().lower()
    return _UID_PREFIX_TO_TYPE.get(prefix, "custom")


def _split_host(description: str) -> tuple[str, str | None]:
    """Tách dòng "Chủ trì: X" khỏi phần mô tả còn lại."""
    match = _HOST_PATTERN.search(description)
    if match is None:
        return description.strip(), None
    host = match.group(1).strip()
    remainder = _HOST_PATTERN.sub("", description).strip()
    return remainder, host or None


def parse_ics(raw: str) -> list[ParsedEvent]:
    """Đọc toàn bộ VEVENT trong một feed ICS.

    Cơ chế: gộp dòng gấp, duyệt tuần tự, mỗi lần gặp BEGIN:VEVENT thì mở một
    khối thuộc tính mới và đóng lại ở END:VEVENT. Thuộc tính có tham số
    (`DTSTART;TZID=...`) được cắt ở dấu `;` đầu tiên. Khối thiếu UID hoặc thiếu
    DTSTART bị bỏ qua vì không có khóa ổn định thì lần nhập sau sẽ nhân bản nó.
    """
    events: list[ParsedEvent] = []
    current: dict[str, str] | None = None

    for line in _unfold(raw):
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            current = {}
            continue
        if stripped == "END:VEVENT":
            if current is not None:
                parsed = _build_event(current)
                if parsed is not None:
                    events.append(parsed)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        name, value = line.split(":", 1)
        current[name.split(";", 1)[0].strip().upper()] = value

    return events


def _build_event(fields: dict[str, str]) -> ParsedEvent | None:
    """Dựng một ParsedEvent từ các thuộc tính thô của một khối VEVENT."""
    uid = _unescape(fields.get("UID", "")).strip()
    starts_at = _parse_moment(fields.get("DTSTART", ""))
    if not uid or starts_at is None:
        logger.warning("Bỏ qua VEVENT thiếu UID hoặc DTSTART: %s", sorted(fields))
        return None

    ends_at = _parse_moment(fields.get("DTEND", ""))
    # Phoenix ghi hạn nộp bằng DTSTART == DTEND. Giữ nguyên thì mọi hạn chót đều
    # hiện thành "khoảng thời gian dài 0 phút", đọc rất khó hiểu.
    if ends_at is not None and ends_at <= starts_at:
        ends_at = None

    description, host = _split_host(_unescape(fields.get("DESCRIPTION", "")))
    event_type = _event_type(uid)
    location = _unescape(fields.get("LOCATION", "") or fields.get("URL", "")).strip()

    return ParsedEvent(
        external_id=uid,
        event_type=event_type,
        visibility="team" if event_type in TEAM_SCOPED_TYPES else "program",
        title=_unescape(fields.get("SUMMARY", "")).strip(),
        description=description,
        host=host,
        location_url=location[:512] or None,
        starts_at=starts_at,
        ends_at=ends_at,
        source_updated_at=_parse_moment(fields.get("DTSTAMP", "")),
    )


def import_program_calendar(
    db: Session,
    raw_ics: str,
    *,
    cohort_slug: str,
    observed_at: datetime | None = None,
) -> ImportResult:
    """Nhập feed vào bảng `program_events` theo kiểu upsert.

    Cơ chế: đọc feed, nạp sẵn các dòng đang có của đúng cohort này vào một dict
    theo `external_id`, rồi với mỗi sự kiện so `content_hash`. Trùng băm thì chỉ
    dời `observed_at`, khác băm thì ghi đè nội dung. Không xóa dòng vắng mặt
    trong feed — BTC gỡ một buổi khỏi lịch và feed lỗi một nửa là hai chuyện
    khác nhau, mà từ phía ta chúng trông giống hệt nhau.

    Hai thứ lần nhập này **không** được đụng vào (ADR-010):

    - mốc do quản trị tự tạo (`origin = "admin"`);
    - những trường quản trị đã sửa tay trên một mốc của feed
      (`locked_fields`). Feed đổi đúng vào trường đang khóa thì đánh
      `source_conflict` để người quyết định, chứ không tự chọn hộ.
    """
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    now = observed_at or datetime.now(UTC)
    parsed_events = parse_ics(raw_ics)
    existing = {
        event.external_id: event
        for event in db.scalars(select(ProgramEvent).where(func.lower(ProgramEvent.cohort_slug) == cohort_slug))
    }

    created = updated = unchanged = skipped_admin = conflicts = 0
    for parsed in parsed_events:
        row = existing.get(parsed.external_id)
        if row is None:
            db.add(_new_row_from_feed(parsed, cohort_slug=cohort_slug, now=now))
            created += 1
            continue

        if row.origin == "admin":
            # Quản trị đã nhận mốc này về tay mình. Feed không còn quyền ghi.
            skipped_admin += 1
            continue

        row.observed_at = now
        locked = set(row.locked_fields or [])
        incoming = _feed_snapshot(parsed)

        if locked and _feed_changed_locked_field(row.feed_payload, incoming, locked):
            row.source_conflict = True
            conflicts += 1

        # Ảnh chụp feed luôn được cập nhật kể cả khi không ghi đè trường bị
        # khóa: nó là "bản gốc hiện tại" để quản trị đối chiếu và hoàn về.
        row.feed_payload = incoming

        if row.content_hash == parsed.content_hash and not locked:
            unchanged += 1
            continue

        changed = _apply_feed_fields(row, parsed, locked)
        row.content_hash = parsed.content_hash
        row.source_updated_at = parsed.source_updated_at
        if changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    logger.info(
        "Nhập lịch cohort %s: %d mới, %d cập nhật, %d không đổi, %d bỏ qua vì admin giữ, %d xung đột",
        cohort_slug,
        created,
        updated,
        unchanged,
        skipped_admin,
        conflicts,
    )
    return ImportResult(
        created=created,
        updated=updated,
        unchanged=unchanged,
        skipped_admin=skipped_admin,
        conflicts=conflicts,
    )


# Các trường feed sở hữu. Đây cũng là tập trường quản trị được phép khóa.
FEED_FIELDS = (
    "event_type",
    "visibility",
    "title",
    "description",
    "host",
    "location_url",
    "starts_at",
    "ends_at",
)


def _feed_snapshot(parsed: ParsedEvent) -> dict:
    """Ảnh chụp giá trị feed dưới dạng JSON lưu được."""
    return {
        "event_type": parsed.event_type,
        "visibility": parsed.visibility,
        "title": parsed.title,
        "description": parsed.description,
        "host": parsed.host,
        "location_url": parsed.location_url,
        "starts_at": parsed.starts_at.isoformat(),
        "ends_at": parsed.ends_at.isoformat() if parsed.ends_at else None,
    }


def _feed_changed_locked_field(previous: dict | None, incoming: dict, locked: set[str]) -> bool:
    """Feed có đổi đúng vào trường quản trị đang giữ không.

    Chưa có ảnh chụp trước thì coi là chưa đổi: dòng đó được khóa từ trước khi
    ta bắt đầu chụp, và báo xung đột dựa trên chỗ trống là báo động giả.
    """
    if not previous:
        return False
    return any(previous.get(field) != incoming.get(field) for field in locked)


def _apply_feed_fields(row: ProgramEvent, parsed: ParsedEvent, locked: set[str]) -> bool:
    """Ghi các trường feed sở hữu, bỏ qua trường đang bị khóa."""
    values = {
        "event_type": parsed.event_type,
        "visibility": parsed.visibility,
        "title": parsed.title,
        "description": parsed.description,
        "host": parsed.host,
        "location_url": parsed.location_url,
        "starts_at": parsed.starts_at,
        "ends_at": parsed.ends_at,
    }
    changed = False
    for field, value in values.items():
        if field in locked or getattr(row, field) == value:
            continue
        setattr(row, field, value)
        changed = True
    return changed


def _new_row_from_feed(parsed: ParsedEvent, *, cohort_slug: str, now: datetime) -> ProgramEvent:
    """Dòng mới từ feed.

    Mặc định `published`: feed là bản ban tổ chức đã công bố công khai, giữ nó ở
    `draft` nghĩa là học viên mất lịch cho tới khi có người bấm phát hành từng
    mốc một. Mốc do quản trị tự tạo mới bắt đầu ở `draft`.
    """
    return ProgramEvent(
        cohort_slug=cohort_slug,
        external_id=parsed.external_id,
        event_type=parsed.event_type,
        visibility=parsed.visibility,
        title=parsed.title,
        description=parsed.description,
        host=parsed.host,
        location_url=parsed.location_url,
        starts_at=parsed.starts_at,
        ends_at=parsed.ends_at,
        content_hash=parsed.content_hash,
        source_updated_at=parsed.source_updated_at,
        observed_at=now,
        origin="feed",
        status="published",
        published_at=now,
        feed_payload=_feed_snapshot(parsed),
    )


async def refresh_from_feed(
    db: Session,
    *,
    feed_url: str,
    cohort_slug: str,
    timeout_seconds: float = 30.0,
) -> ImportResult:
    """Tải feed ICS rồi nhập vào DB.

    Tách khỏi `import_program_calendar` để phần đọc mạng không dính vào phần
    logic — mọi test luật nhập chạy được mà không cần mock HTTP, còn hàm này chỉ
    còn đúng một việc để hỏng.
    """
    import httpx

    # feed_url là config của operator (PHOENIX_ICS_FEED_URL), không phải input
    # người dùng — nên không chặn IP nội bộ để operator vẫn tự host feed được.
    # Nhưng chốt scheme về http/https để một giá trị sai (file://, gopher://…)
    # không biến hàm này thành đường đọc file cục bộ hay SSRF scheme lạ.
    scheme = urlparse(feed_url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"feed_url phải là http/https, nhận scheme: {scheme!r}")

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(feed_url)
        response.raise_for_status()
        raw = response.text

    return import_program_calendar(db, raw, cohort_slug=cohort_slug)


def list_program_events(
    db: Session,
    *,
    cohort_slug: str,
    since: datetime | None = None,
    until: datetime | None = None,
    query: str = "",
    event_types: list[str] | None = None,
    include_team_scoped: bool = False,
    statuses: tuple[str, ...] = ("published",),
    limit: int = 20,
) -> list[ProgramEvent]:
    """Đọc lịch chương trình của một cohort, mặc định bỏ sự kiện riêng của nhóm.

    `include_team_scoped` và `statuses` đều để mặc định ở giá trị hẹp nhất chứ
    không phải tham số bắt buộc: quên truyền thì kết quả hẹp hơn thực tế, chứ
    không rộng hơn quyền. Chỉ trang quản trị mới truyền `statuses` khác.
    """
    cohort_slug = normalize_program_cohort_slug(cohort_slug)
    filters = [func.lower(ProgramEvent.cohort_slug) == cohort_slug]
    if statuses:
        filters.append(ProgramEvent.status.in_(statuses))
    if not include_team_scoped:
        filters.append(ProgramEvent.visibility == "program")
    if since is not None:
        filters.append(ProgramEvent.starts_at >= since)
    if until is not None:
        filters.append(ProgramEvent.starts_at <= until)
    if event_types:
        filters.append(ProgramEvent.event_type.in_(event_types))

    terms = [term for term in re.split(r"\W+", query, flags=re.UNICODE) if len(term) >= 2]
    for term in terms:
        pattern = f"%{term}%"
        filters.append(ProgramEvent.title.ilike(pattern) | ProgramEvent.description.ilike(pattern))

    statement = (
        select(ProgramEvent)
        .where(*filters)
        .order_by(ProgramEvent.starts_at.asc(), ProgramEvent.id.asc())
        .limit(max(1, min(limit, 100)))
    )
    return list(db.scalars(statement))
