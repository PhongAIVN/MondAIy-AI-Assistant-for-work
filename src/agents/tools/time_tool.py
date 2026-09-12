"""Công cụ thời gian cho agent chat.

Model không biết hôm nay là ngày nào — nó chỉ có ngày trong dữ liệu huấn luyện.
Không cấp mốc hiện tại thì mọi câu hỏi kiểu "việc nào sắp tới hạn", "tin này cũ
chưa", "còn mấy ngày nữa" đều trả lời sai một cách tự tin. Hai công cụ ở đây làm
đúng một việc: cho model biết bây giờ là lúc nào, và đo khoảng cách giữa mốc
thời gian của một tin nhắn với hiện tại.

Không đoán thay người dùng: chuỗi không parse được thì nói không parse được,
chuỗi thiếu múi giờ thì nói rõ là đang giả định múi giờ ứng dụng. Cùng tinh thần
BR-05 mà `pipeline/time_resolve.py` đang giữ cho due_at.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil import parser as dateutil_parser
from langchain_core.tools import tool

from src.config import get_settings

logger = logging.getLogger(__name__)

# datetime.weekday() trả 0 cho thứ Hai.
_WEEKDAY_NAMES = (
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
)

_FALLBACK_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Chuỗi mở đầu bằng năm bốn chữ số thì đọc theo ISO, không đọc ngày trước.
_ISO_LIKE = re.compile(r"\s*\d{4}-\d{1,2}-\d{1,2}")


def app_timezone() -> ZoneInfo:
    """Múi giờ hiển thị của ứng dụng, đọc từ config."""
    name = get_settings().app_timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        # Cấu hình sai không được làm chết lượt chat. Ghi log rồi dùng giờ VN,
        # vì đó là múi giờ của toàn bộ người dùng pilot.
        logger.warning("APP_TIMEZONE %r không hợp lệ, tạm dùng Asia/Ho_Chi_Minh", name)
        return _FALLBACK_TZ


def now() -> datetime:
    """Thời điểm hiện tại kèm múi giờ ứng dụng.

    Tách thành hàm riêng để test đóng băng được thời gian mà không phải vá
    datetime toàn cục.
    """
    return datetime.now(app_timezone())


def _format_date(moment: datetime) -> str:
    """Một mốc viết theo cách người Việt vẫn đọc."""
    return f"{_WEEKDAY_NAMES[moment.weekday()]}, {moment:%d/%m/%Y}"


@dataclass(frozen=True)
class ParsedTime:
    """Một mốc đã hiểu được, kèm ghi chú đã phải giả định gì để hiểu."""

    moment: datetime
    # True khi chuỗi gốc không nói múi giờ và ta phải gán múi giờ ứng dụng.
    # Chỗ gọi phải nói ra điều này, đừng để người đọc tưởng con số là chắc chắn.
    timezone_assumed: bool


def parse_timestamp(raw: str) -> ParsedTime | None:
    """Hiểu một chuỗi ngày giờ do model hoặc người dùng đưa vào.

    Trả None khi không hiểu được — gọi ở đâu thì chỗ đó phải xử lý, tuyệt đối
    không tự đoán một mốc gần đúng rồi trả lời như thật.
    """
    text = (raw or "").strip()
    if not text:
        return None

    try:
        # Hai quy ước ngược nhau đi vào cùng một chỗ: chuỗi người dùng gõ kiểu
        # 06/08/2026 phải đọc ngày trước, còn occurred_at lấy từ DB là ISO nên
        # phải đọc năm trước. Bật dayfirst cho cả hai thì 2026-08-06 bị hiểu
        # thành 8 tháng 6 — sai hai tháng mà vẫn trả lời rất tự tin.
        moment = dateutil_parser.parse(text, dayfirst=not _ISO_LIKE.match(text), fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None

    if moment.tzinfo is None:
        return ParsedTime(moment.replace(tzinfo=app_timezone()), timezone_assumed=True)
    return ParsedTime(moment, timezone_assumed=False)


@tool
def current_datetime() -> str:
    """Cho biết hôm nay là ngày nào, bây giờ là mấy giờ.

    Gọi công cụ này trước khi trả lời bất kỳ câu hỏi nào có yếu tố thời gian:
    hôm nay, tuần này, sắp tới hạn, đã quá hạn, mới hay cũ, còn mấy ngày.

    Returns:
        Một mốc ISO duy nhất theo múi giờ ứng dụng, kèm thứ để model đối chiếu
    """
    current = now()
    return (
        f"Hiện tại: {current.isoformat(timespec='minutes')} "
        f"({_WEEKDAY_NAMES[current.weekday()]}, {app_timezone().key})."
    )


@tool
def relative_time(timestamp: str) -> str:
    """Đo khoảng cách từ một mốc thời gian tới hiện tại.

    Dùng khi đã có ngày giờ của một tin nhắn, một hạn chót hay một sự kiện và
    cần biết nó cách hôm nay bao lâu, đã qua hay chưa tới.

    Args:
        timestamp: Ngày giờ cần so, ví dụ "06/08/2026", "2026-08-06T14:30:00+07:00"

    Returns:
        Mốc đã hiểu được, khoảng cách tới hiện tại và chiều quá khứ hay tương lai
    """
    raw = (timestamp or "").strip()
    if not raw:
        return "Chưa có mốc thời gian nào để so."

    parsed = parse_timestamp(raw)
    if parsed is None:
        return f"Không hiểu được mốc thời gian {raw!r}. Cần dạng ngày/tháng/năm hoặc chuỗi ISO."

    moment = parsed.moment
    note = f" (chuỗi gốc không ghi múi giờ, đang hiểu theo {moment.tzname()})" if parsed.timezone_assumed else ""

    delta = moment - now()
    total_seconds = abs(delta.total_seconds())
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)

    if days:
        distance = f"{days} ngày {hours} giờ" if hours else f"{days} ngày"
    elif hours:
        distance = f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"
    else:
        distance = f"{minutes} phút"

    direction = "trước" if delta.total_seconds() < 0 else "nữa"
    return (
        f"{_format_date(moment)} {moment:%H:%M} "
        f"({moment.isoformat(timespec='seconds')}){note}\n"
        f"Cách hiện tại {distance} {direction}."
    )
