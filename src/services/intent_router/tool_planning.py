"""Lập kế hoạch tool cho vòng agent hội thoại — xem package __init__.py.

Model nhỏ chọn tool rất chập chờn, nên node `think` không phó mặc hoàn toàn
cho nó: sau khi model đề xuất, các luật dưới đây vá lại danh sách tool. Mọi
luật đều khớp trên chuỗi đã bỏ dấu qua `_fold`, để người gõ không dấu nhận
được đúng hành vi như người gõ có dấu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from json import dumps

from dateutil import parser as dateutil_parser

from src.config import get_settings
from src.services.intent_router._shared import _fold
from src.services.source_routing import analyze_source_mentions
from src.services.temporal_understanding import TemporalDecision, resolve_temporal

_AGENT_PUBLIC_WEB = re.compile(
    r"(?i)(?:web\s+search|tim\s+tren\s+(?:mang|internet)|tra\s+tren\s+mang|"
    r"tren\s+internet|tin\s+tuc|thoi\s+tiet|gia\s+(?:vang|xang|bitcoin)|"
    r"tieu\s+su|sinh\s+(?:ngay|nam)|\bai\s+la\b|tong\s+thong|thu\s+tuong)"
)
_AGENT_CALENDAR = re.compile(r"(?i)(?:\blich\b|calendar|su kien|cuoc hen|meeting|event)")
_AGENT_CALENDAR_WRITE = re.compile(r"(?i)(?:tao|them|dat|sua|xoa|huy|create|add|edit|delete|cancel)")
_AGENT_PLANNER = re.compile(
    r"(?i)(?:len\s+ke\s+hoach|xep\s+lich\s+(?:lam|viec)|plan\s+(?:my|the)?\s*(?:day|week)|"
    r"happy\s*time|gio\s+lam\s+viec|nghi\s+trua|workday\s+contract)"
)
_AGENT_PRODUCTIVITY_CREATE = re.compile(
    r"(?i)(?=.*(?:tao|them|dat|ghi|len\s+lich|nhac\s+(?:toi|minh)|create|add|schedule))"
    r"(?=.*(?:lich|calendar|event|meeting|workshop|task|todo|to-do|cong\s+viec|"
    r"nhiem\s+vu|viec\s+can\s+lam|nhac\s+(?:toi|minh))).+"
)
_AGENT_GMAIL = re.compile(r"(?i)(?:\bgmail\b|\be-?mail\b|\bmail\b|inbox|hop thu|thu dien tu)")
_AGENT_GMAIL_WRITE = re.compile(
    r"(?i)(?:gui|send|forward|chuyen tiep|archive|luu tru|gan nhan|label|xoa|delete|"
    r"(?:tra loi|reply)\s+(?:email|e-?mail|mail|thu))"
)
_AGENT_JIRA = re.compile(r"(?i)(?:\bjira\b|issue|ticket|bug|epic|task\s+jira)")
_AGENT_JIRA_ACTIVITY = re.compile(
    r"(?i)(?=.*(?:du an|project))(?=.*(?:da lam|thuc hien|tham gia|contributed|contrib|worked))"
)
_AGENT_JIRA_WRITE = re.compile(
    r"(?i)(?:tao|them|sua|update|xoa|delete|close|assign|transition)\s+(?:jira|issue|ticket|bug)"
)
_AGENT_DISCORD = re.compile(r"(?i)(?:\bdiscord\b|\btin\s+nhan\b|\bkenh\b|\bchannel\b)")
_AGENT_GROUP_DISCUSSION = re.compile(
    r"(?i)(?=.*(?:\bnhom\b|\bteam\b|\bmoi nguoi\b))"
    r"(?=.*(?:\bchot\b|\bquyet dinh\b|\btrao doi\b|\bnoi\b|\bban\b)).+"
)
_GOOGLE_SHEETS_URL = re.compile(
    r"https?://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9_-]+(?:[/?#][^\s<>)]+)?",
    re.IGNORECASE,
)
_GOOGLE_DOCS_URL = re.compile(
    r"https?://docs\.google\.com/document/d/[a-zA-Z0-9_-]+(?:[/?#][^\s<>)]+)?",
    re.IGNORECASE,
)
_AGENT_TODAY = re.compile(r"(?i)(?:\bhom nay\b|\btoday\b|\bdaily\b|(?:tom tat|tong hop)\s+ngay(?!\s+(?:mai|mot))\b)")
_AGENT_OVERVIEW = re.compile(
    r"(?i)(?:tom tat|tong hop|diem chinh|can chu y|co gi|"
    r"what changed|what happened|overview|summari[sz]e)"
)
# Câu hỏi lịch trình: "hôm nay tôi cần làm gì", "nên làm gì tiếp theo", "tuần
# này có gì". Người dùng hỏi một câu, nhưng câu trả lời đúng phải gom từ cả bốn
# nguồn đọc. Trước đây có hai luật rời — một cho "tóm tắt hôm nay", một cho "nên
# làm gì tiếp theo" — nên cách hỏi nào không khớp đúng chữ thì rơi hết xuống
# lưới an toàn và chỉ tra mỗi Discord. Liệt kê từng cách nói là cách chữa dở,
# nhưng nó vẫn tốt hơn để câu phổ biến nhất của sản phẩm trả lời sai.
_AGENT_AGENDA = re.compile(
    r"(?i)(?:"
    r"(?:can|nen|phai)\s+lam\s+(?:nhung\s+)?gi|lam\s+gi\s+tiep|lam\s+nhung\s+gi|"
    r"(?:cong\s+)?viec\s+nao\s+(?:can|nen)\s+(?:lam|uu tien)|"
    r"co\s+(?:cong\s+)?viec\s+gi|(?:cong\s+)?viec\s+gi\s+(?:can|phai)\s+lam|"
    r"lich\s+trinh|agenda|briefing|"
    r"what\s+should\s+i\s+do|what\s+do\s+i\s+(?:need|have)\s+to\s+do|next\s+step|"
    r"what'?s\s+on\s+my\s+(?:plate|agenda)"
    r")"
)
# Mốc thời gian một câu lịch trình đang nói tới. Ghép với `_AGENT_OVERVIEW` thì
# "hôm nay có gì" cũng được coi là hỏi lịch trình.
_AGENT_PERIOD = re.compile(
    r"(?i)(?:\bhom nay\b|\btoday\b|\bdaily\b|\bngay mai\b|\bmai\b|\btomorrow\b|"
    r"\btuan nay\b|\bthis week\b|\btuan (?:sau|toi)\b|\bnext week\b|\bsap toi\b|"
    r"\bthang\s+(?:[1-9]|1[0-2])(?:\s+(?:nam\s+)?\d{4})?\b|"
    r"\b(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+\d{4}\b)"
)
_AGENT_MONTH = re.compile(r"(?i)\bthang\s+(?P<month>[1-9]|1[0-2])(?:\s+(?:nam\s+)?(?P<year>\d{4}))?\b")
_AGENT_CONVERSATIONAL_MEMORY = re.compile(
    r"(?i)(?:\b(?:toi|minh|em)\s+ten\b|\bten\s+(?:cua\s+)?(?:toi|minh|em)\b|"
    r"\bgoi\s+(?:toi|minh|em)\s+la\b|\b(?:toi|minh|em)\s+thich\b|"
    r"\b(?:hay\s+)?nho\s+(?:rang|la)?\b|\bmy\s+name\b|\bwhat(?:'s|\s+is)\s+my\s+name\b|"
    r"\bremember\s+(?:that|my)\b|\b(?:ban\s+)?(?:biet|nho)\s+gi\s+ve\s+toi\b|"
    r"\b(?:ho so|profile|bo nho|memory)\s+(?:cua\s+)?(?:toi|minh|my)\b|"
    r"\b(?:toi|minh|em)\s+la\s+(?:mot\s+)?(?:hoc vien|sinh vien|mentor|giang vien|quan ly du an)\b|"
    r"\b(?:mui gio|timezone)\b|\b(?:tra loi|response|answer)\b.{0,25}"
    r"\b(?:ngan gon|suc tich|chi tiet|tieng viet|tieng anh|concise|detailed|english|vietnamese)\b)"
)
_AGENT_MY_DISCORD_MESSAGES = re.compile(
    # "nhan" (rụng dấu của cả "nhắn" lẫn "nhận") và "noi" đã đủ gợi ý nhắn tin
    # trong ngữ cảnh app này nên không cần thêm điều kiện. "viet"/"trao doi" là
    # động từ chung hơn (viết báo cáo, viết yêu cầu Jira...) nên chỉ khớp khi
    # có từ khoá discord/tin nhắn/kênh gần đó.
    r"(?i)(?:\b(?:toi|minh|em)\s+da\s+(?:nhan|noi)\b|"
    r"\b(?:toi|minh|em)\s+da\s+(?:viet|trao doi)\b(?=.{0,25}\b(?:discord|tin nhan|kenh)\b)|"
    r"\b(?:discord|tin nhan|kenh)\b(?=.{0,25}\b(?:toi|minh|em)\s+da\s+(?:viet|trao doi)\b)|"
    r"\b(?:toi|minh|em)\s+(?:noi|viet)\s+gi\b|"
    r"\btin nhan\s+(?:discord\s+)?cua\s+(?:toi|minh|em)\b|"
    r"\b(?:my|i)\s+(?:discord\s+)?messages?\b|\bwhat did i\s+(?:say|write)\b)"
)
_AGENT_MY_DISCORD_ACTIVITY = re.compile(
    # "...nhan bao nhieu" một mình là hỏi số lượng chung (điểm, tin nhắn nào
    # cũng nhận được cả) — chỉ khớp khi có discord/kênh/tin nhắn gần đó.
    r"(?i)(?:\bhoat dong discord cua\s+(?:toi|minh|em)\b|"
    r"\b(?:toi|minh|em)\s+(?:da\s+)?nhan\s+bao nhieu\b(?=.{0,25}\b(?:discord|kenh|tin nhan)\b)|"
    r"\b(?:toi|minh|em)\s+(?:da\s+)?nhan\s+o\s+(?:kenh|dau)\b|"
    r"\bmy discord activity\b)"
)

# Câu hỏi về thông báo chính thức của chương trình. Khác câu hỏi tra cứu nội
# dung: người hỏi không biết trước thông báo nói gì nên không thể tự đưa từ
# khóa, vì vậy tra theo độ liên quan trả về thảo luận vụn thay vì thông báo.
_AGENT_ANNOUNCEMENT = re.compile(
    r"(?i)(?:\bthong bao\b|\bannouncement\b|"
    r"\bco gi moi\b|\bcap nhat gi\b|\btin moi\b|"
    r"\b(?:chuong trinh|btc|ban to chuc)\b.{0,20}\b(?:thong bao|nhac|luu y)\b|"
    r"\bdoi lich\b|\bnghi hoc\b)"
)

_AGENT_PROGRAM_INFORMATION = re.compile(
    r"(?i)(?:\bthong tin chuong trinh\b|\bcau hoi thuong gap\b|\bfaq\b|"
    r"\bquy dinh\b|\bthe le\b|\bcach nop bai\b|\bnop bai o dau\b|"
    r"\bchuong trinh\b.{0,28}\b(?:la gi|ho tro|lien he|tham gia|quy dinh|nop bai)\b|"
    r"\bmondaiy\b.{0,32}\b(?:la gi|lam duoc gi|tinh nang|su dung|ket noi)\b|"
    r"\b(?:cach dung|huong dan|tinh nang moi|co gi moi)\b.{0,32}\b"
    r"(?:mondaiy|san pham|routine|google sheets|anh|chat)\b)"
)


# Câu lịch trình không nói mốc thì nhìn bảy ngày tới. Xa hơn nữa thì danh sách
# dài tới mức không còn là câu trả lời cho "hôm nay tôi cần làm gì".
_AGENDA_HORIZON_DAYS = 7
# Thư nhắc về việc của hôm nay thường đã tới từ mấy hôm trước, nên Gmail đọc lùi
# về quá khứ chứ không dùng chung cửa sổ với Calendar.
_AGENDA_MAIL_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class ToolPlanContext:
    """Mọi thứ luật cần biết để vá danh sách tool của một vòng think."""

    query: str
    # Mốc "bây giờ" do node truyền vào, không tự gọi datetime.now: test phải
    # đóng băng được thời gian, và mọi cửa sổ trong cùng một vòng phải cùng mốc.
    now: datetime
    routing_context: str = ""
    observations: list[dict] = field(default_factory=list)
    pending_action: dict | None = None
    web_search_enabled: bool = False
    # Số vòng tool đã chạy. Lưới an toàn "cứ tra Discord đi" chỉ được bung ở vòng
    # đầu: từ vòng hai trở đi, danh sách rỗng nghĩa là model đã xem observation
    # rồi và chủ động dừng, ép tra thêm lúc đó là lặp vô hạn.
    tool_iterations: int = 0
    # Tên các tool thực sự đang gắn cho lượt này. None nghĩa là không giới hạn.
    # Luật chỉ được tự thêm tool nằm trong tập này: tool không tồn tại thì tầng
    # thực thi bỏ qua im lặng, không sinh observation nào, nên vòng sau luật lại
    # thấy thiếu và thêm lại — lặp cho tới khi cạn trần số vòng.
    available_tools: frozenset[str] | None = None
    temporal_resolution: TemporalDecision | None = None
    conversational_route: dict | None = None


def _agent_folded(query: str) -> str:
    """Chuỗi dùng để khớp luật: gộp khoảng trắng, thường hoá, bỏ dấu."""
    return _fold(" ".join(query.split())).casefold()


# Mốc model tự điền chỉ được tin nếu nó rơi trong khoảng này quanh hiện tại.
# Model nhỏ rất hay điền năm trong dữ liệu huấn luyện của nó — đã gặp thật: hỏi
# "lịch của tôi" thì nó truyền time_from của năm 2023, tool đọc đúng khoảng đó
# và trả về rỗng, còn người dùng thì tưởng lịch mình trống.
_MODEL_WINDOW_PAST_LIMIT_DAYS = 90
_MODEL_WINDOW_FUTURE_LIMIT_DAYS = 400


def _parse_moment(value: object) -> datetime | None:
    """Đọc một mốc model điền, trả None nếu không hiểu được."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return dateutil_parser.parse(value.strip())
    except (ValueError, OverflowError, TypeError):
        return None


def _model_window_is_plausible(args: dict, current: datetime, keys: tuple[str, str]) -> bool:
    """Cửa sổ model tự điền có nằm quanh hiện tại không.

    Cơ chế: cả hai mốc phải đọc được và phải giao với khoảng tin được quanh
    `current`. Chỉ khi đó mới giữ giá trị của model — nó hiểu được những cách nói
    mà luật ở đây không phủ, ví dụ "lịch tháng 12". Ngoài khoảng đó thì gần như
    chắc chắn là model bịa năm, và bịa năm thì tool trả rỗng chứ không báo lỗi.
    """
    start = _parse_moment(args.get(keys[0]))
    end = _parse_moment(args.get(keys[1]))
    if start is None or end is None or start >= end:
        return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=current.tzinfo)
    if end.tzinfo is None:
        end = end.replace(tzinfo=current.tzinfo)
    som_nhat = current - timedelta(days=_MODEL_WINDOW_PAST_LIMIT_DAYS)
    muon_nhat = current + timedelta(days=_MODEL_WINDOW_FUTURE_LIMIT_DAYS)
    return start <= muon_nhat and end >= som_nhat


def calendar_window(query: str, current: datetime, temporal: TemporalDecision | None = None) -> tuple[str, str]:
    """Cửa sổ hữu hạn cho câu hỏi lịch, suy từ chữ trong câu."""
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    folded = _agent_folded(query)
    resolved = temporal or resolve_temporal(query, current)
    if resolved.time_from and resolved.time_to:
        return resolved.time_from.isoformat(), resolved.time_to.isoformat()

    if "ngay mai" in folded or re.search(r"(?:^|\s)mai(?:$|\s|[?.!,])", folded) or "tomorrow" in folded:
        start = day_start + timedelta(days=1)
        end = start + timedelta(days=1)
    elif "hom nay" in folded or "today" in folded:
        start = day_start
        end = start + timedelta(days=1)
    elif "tuan sau" in folded or "next week" in folded:
        start = day_start - timedelta(days=day_start.weekday()) + timedelta(days=7)
        end = start + timedelta(days=7)
    elif "tuan nay" in folded or "this week" in folded:
        start = day_start - timedelta(days=day_start.weekday())
        end = start + timedelta(days=7)
    elif "thang nay" in folded or "this month" in folded:
        start = day_start.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        # "Lịch của tôi" không nói mốc thì hiểu là hôm nay. Trước đây lấy 30 ngày
        # tới: model nhận về một đống sự kiện rồi tự thu lại thành "hôm nay bạn
        # có..." mà không nói mình đã bỏ qua những ngày nào, nên người đọc tưởng
        # cả tháng chỉ có ngần đó việc. Muốn rộng hơn thì hỏi rõ tuần này.
        start = day_start
        end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def gmail_window(query: str, current: datetime, temporal: TemporalDecision | None = None) -> tuple[str, str]:
    """Cửa sổ Gmail mặc định là 30 ngày vừa qua, không quét hộp thư vô hạn."""
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    folded = _agent_folded(query)
    resolved = temporal or resolve_temporal(query, current)
    if resolved.time_from and resolved.time_to:
        return resolved.time_from.isoformat(), resolved.time_to.isoformat()
    if "hom nay" in folded or "today" in folded:
        return day_start.isoformat(), (day_start + timedelta(days=1)).isoformat()
    if "tuan nay" in folded or "this week" in folded:
        start = day_start - timedelta(days=day_start.weekday())
        return start.isoformat(), (start + timedelta(days=7)).isoformat()
    if "thang nay" in folded or "this month" in folded:
        start = day_start.replace(day=1)
        return (
            start.isoformat(),
            (start.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat(),
        )
    return (current - timedelta(days=30)).isoformat(), current.isoformat()


def can_answer_from_memory(query: str) -> bool:
    """Câu chỉ cần nhớ lại điều người dùng đã tự nói thì không cần tra nguồn."""
    return bool(_AGENT_CONVERSATIONAL_MEMORY.search(_agent_folded(query)))


def is_productivity_create(query: str, pending_action: dict | None = None) -> bool:
    """Lượt đang tạo event/task, kể cả khi đang trả lời câu hỏi làm rõ."""
    return bool(_AGENT_PRODUCTIVITY_CREATE.search(_agent_folded(query)) or pending_action)


def _prefer_calendar_search(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Ép câu hỏi lịch sang Calendar read tool đúng một lần khi model bỏ qua."""
    folded = _agent_folded(context.query)
    if not _AGENT_CALENDAR.search(folded) or _AGENT_CALENDAR_WRITE.search(folded):
        return tool_calls
    time_from, time_to = calendar_window(context.query, context.now, context.temporal_resolution)
    patched: list[dict] = []
    found = False
    for call in tool_calls:
        if call.get("name") != "calendar_search_events":
            patched.append(call)
            continue
        found = True
        args = dict(call.get("args") or {})
        args.setdefault("query", "")
        # Không dùng setdefault cho mốc thời gian: setdefault giữ nguyên giá trị
        # model đã điền, kể cả khi đó là một năm nó bịa ra. Chỉ giữ mốc của model
        # khi cửa sổ đó còn nằm quanh hiện tại.
        if not _model_window_is_plausible(args, context.now, ("time_from", "time_to")):
            args["time_from"], args["time_to"] = time_from, time_to
        patched.append({**call, "args": args})
    if found:
        return patched
    if any(item.get("name") == "calendar_search_events" for item in context.observations):
        return patched
    return [
        *tool_calls,
        {
            "name": "calendar_search_events",
            "args": {"query": "", "time_from": time_from, "time_to": time_to},
            "id": "auto-calendar-search",
        },
    ]


def _prefer_gmail_search(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Đảm bảo câu hỏi Gmail có một truy vấn chỉ-đọc, giới hạn thời gian."""
    folded = _agent_folded(context.query)
    if not _AGENT_GMAIL.search(folded) or _AGENT_GMAIL_WRITE.search(folded):
        return tool_calls
    time_from, time_to = gmail_window(context.query, context.now, context.temporal_resolution)
    patched: list[dict] = []
    found = False
    for call in tool_calls:
        if call.get("name") not in {"gmail_search_emails", "gmail_deadline_sweep"}:
            patched.append(call)
            continue
        found = True
        args = dict(call.get("args") or {})
        args.setdefault("query", "")
        # Cùng lý do như bên Calendar: mốc model bịa thì tool đọc đúng khoảng
        # rỗng đó rồi trả về "không có email nào", nghe như hộp thư trống thật.
        if not _model_window_is_plausible(args, context.now, ("time_from", "time_to")):
            args["time_from"], args["time_to"] = time_from, time_to
        patched.append({**call, "name": "gmail_deadline_sweep", "args": args})
    if found:
        return patched
    return [
        *tool_calls,
        {
            "name": "gmail_deadline_sweep",
            "args": {"query": "", "time_from": time_from, "time_to": time_to},
            "id": "auto-gmail-search",
        },
    ]


def _prefer_gmail_bridge(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Add a complementary content-led Gmail query without replacing OAuth Gmail."""
    folded = _agent_folded(context.query)
    settings = get_settings()
    if (
        not _AGENT_GMAIL.search(folded)
        or _AGENT_GMAIL_WRITE.search(folded)
        or not settings.anythingllm_gmail_bridge_enabled
        or not settings.anythingllm_gmail_bridge_user_id
    ):
        return tool_calls
    if context.available_tools and "gmail_bridge_search" not in context.available_tools:
        return tool_calls
    time_from, time_to = gmail_window(context.query, context.now, context.temporal_resolution)
    # The legacy Gmail sweep keeps its historical window semantics. For the
    # bridge, an explicit "tháng 8" must also become the actual August sent
    # window; the bridge's second query will widen history independently.
    month_match = re.search(r"(?:thang|month)\s+(\d{1,2})(?:\s+(?:nam|year)\s+(\d{4}))?", folded)
    if month_match and 1 <= int(month_match.group(1)) <= 12:
        month = int(month_match.group(1))
        year = int(month_match.group(2) or context.now.year)
        start = context.now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=year + 1, month=1) if month == 12 else start.replace(month=month + 1)
        time_from, time_to = start.isoformat(), end.isoformat()
    existing = next((item for item in tool_calls if item.get("name") == "gmail_bridge_search"), None)
    remaining = [item for item in tool_calls if item.get("name") != "gmail_bridge_search"]
    args = dict((existing or {}).get("args") or {})
    args.setdefault("query", context.query)
    args["time_from"], args["time_to"] = time_from, time_to
    return [
        *remaining,
        {"name": "gmail_bridge_search", "args": args, "id": (existing or {}).get("id", "auto-gmail-bridge")},
    ]


def _prefer_jira_search(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Route explicit Jira reads to the canonical Jira source tool."""
    routing_text = context.routing_context or context.query
    folded = _agent_folded(routing_text)
    if not (_AGENT_JIRA.search(folded) or _AGENT_JIRA_ACTIVITY.search(folded)) or _AGENT_JIRA_WRITE.search(folded):
        return tool_calls
    existing = next((call for call in tool_calls if call.get("name") == "jira_search_issues"), None)
    remaining = [call for call in tool_calls if call.get("name") != "jira_search_issues"]
    args = dict((existing or {}).get("args") or {})
    args.setdefault("query", routing_text)
    return [
        *remaining,
        {"name": "jira_search_issues", "args": args, "id": (existing or {}).get("id", "auto-jira-search")},
    ]


def _prefer_google_document_tools(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """URL Google phải đi vào connector thật, không rơi sang retrieval Discord."""
    routing_text = context.routing_context or context.query
    sheet_match = _GOOGLE_SHEETS_URL.search(routing_text)
    doc_match = _GOOGLE_DOCS_URL.search(routing_text)
    if not sheet_match and not doc_match:
        return tool_calls

    google_names = {"google_sheets_task_proposals", "google_docs_task_proposals"}
    discord_names = {
        "discord_search_program",
        "discord_search_messages",
        "discord_search_my_messages",
        "discord_get_my_activity",
        "discord_list_announcements",
    }
    planned = [call for call in tool_calls if call.get("name") not in google_names | discord_names]
    observed = {item.get("name") for item in context.observations}
    if sheet_match and "google_sheets_task_proposals" not in observed:
        planned.append(
            {
                "name": "google_sheets_task_proposals",
                "args": {"spreadsheet_url": sheet_match.group(0).rstrip(".,;!?")},
                "id": "auto-google-sheets",
            }
        )
    if doc_match and "google_docs_task_proposals" not in observed:
        planned.append(
            {
                "name": "google_docs_task_proposals",
                "args": {"document_url": doc_match.group(0).rstrip(".,;!?")},
                "id": "auto-google-docs",
            }
        )
    return planned


def _discord_is_relevant(context: ToolPlanContext) -> bool:
    folded = _agent_folded(context.query)
    routing_folded = _agent_folded(context.routing_context or context.query)
    decision = analyze_source_mentions(context.routing_context or context.query)
    return bool(
        "discord" in decision.candidate_sources
        or decision.explicit_sources == ("all",)
        or decision.mode == "entity_discovery"
        or _AGENT_DISCORD.search(routing_folded)
        or _AGENT_GROUP_DISCUSSION.search(folded)
        or _AGENT_ANNOUNCEMENT.search(folded)
        or _AGENT_MY_DISCORD_ACTIVITY.search(folded)
        or _AGENT_MY_DISCORD_MESSAGES.search(folded)
        or is_agenda_query(context.query)
    )


def _remove_unrequested_discord(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Không để model hoặc fallback tự biến câu mơ hồ thành truy vấn Discord."""
    if _discord_is_relevant(context):
        return tool_calls
    discord_names = {
        "discord_search_program",
        "discord_search_messages",
        "discord_search_my_messages",
        "discord_get_my_activity",
        "discord_list_announcements",
    }
    return [call for call in tool_calls if call.get("name") not in discord_names]


def _apply_conversational_route(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Map quyết định source-agnostic sang đúng một source adapter."""
    route = context.conversational_route or {}
    action = route.get("action")
    if action in {"EXPLAIN", "CLARIFY"}:
        return []
    if action not in {"READ", "RETRY", "SWITCH_SOURCE"}:
        return tool_calls
    # Source role không được ghi đè intent ghi. “Tạo event trên Calendar” có
    # Calendar là đích, nhưng tool đúng vẫn là productivity write + approval.
    if is_productivity_create(context.query, context.pending_action):
        return tool_calls
    source = route.get("source")
    resource = str(route.get("resource_ref") or context.query)
    if not source:
        return tool_calls

    if source == "google_sheets" and _GOOGLE_SHEETS_URL.search(resource):
        args = {"spreadsheet_url": _GOOGLE_SHEETS_URL.search(resource).group(0).rstrip(".,;!?")}
        locator = str(route.get("resource_locator") or "").strip()
        if locator:
            args["sheet_name"] = locator
        return [
            {"name": "google_sheets_task_proposals", "args": args, "id": "route-google-sheets"}
        ]
    if source == "google_docs" and _GOOGLE_DOCS_URL.search(resource):
        return [{"name": "google_docs_task_proposals", "args": {"document_url": resource}, "id": "route-google-docs"}]
    if source == "gmail":
        time_from, time_to = gmail_window(resource, context.now, context.temporal_resolution)
        return [
            {
                "name": "gmail_deadline_sweep",
                "args": {"query": resource, "time_from": time_from, "time_to": time_to},
                "id": "route-gmail",
            }
        ]
    if source == "jira":
        return [{"name": "jira_search_issues", "args": {"query": resource}, "id": "route-jira"}]
    if source == "calendar":
        time_from, time_to = calendar_window(resource, context.now, context.temporal_resolution)
        return [
            {
                "name": "calendar_search_events",
                "args": {"query": "", "time_from": time_from, "time_to": time_to},
                "id": "route-calendar",
            }
        ]
    if source == "discord":
        discord_tools = {
            "discord_search_program",
            "discord_search_messages",
            "discord_search_my_messages",
            "discord_get_my_activity",
            "discord_list_announcements",
        }
        selected = [call for call in tool_calls if call.get("name") in discord_tools]
        if selected:
            return selected
        return [{"name": "discord_search_program", "args": {"query": resource}, "id": "route-discord"}]
    if source == "tasks":
        return [{"name": "list_tasks", "args": {"status": "proposed"}, "id": "route-tasks"}]
    return tool_calls


def _prefer_project_source_discovery(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Search all relevant personal sources when a project is named but source is not."""
    routing_text = context.routing_context or context.query
    # Yêu cầu TẠO thì không có gì để khám phá. "nhắc tôi 01/09 23:59 nộp dự án
    # P004" có tên dự án, nhưng người dùng đang ĐỌC CHO máy ghi chứ không nhờ
    # máy đọc hộ — quét năm nguồn ở đây chỉ tốn lượt gọi và làm ngập ngân sách
    # ngữ cảnh bằng dữ liệu không liên quan tới việc sắp tạo.
    if is_productivity_create(context.query, context.pending_action):
        return tool_calls
    decision = analyze_source_mentions(routing_text)
    if decision.mode == "explicit" and decision.explicit_sources == ("all",):
        selected_sources = set(decision.candidate_sources)
    elif decision.mode == "entity_discovery":
        selected_sources = set(decision.candidate_sources)
    else:
        return tool_calls
    entity_query = " ".join(decision.entities)
    start = context.now - timedelta(days=180)
    end = context.now + timedelta(days=1)
    required = [
        {"name": "list_tasks", "args": {"status": "proposed"}, "id": "auto-project-tasks"},
        {"name": "jira_search_issues", "args": {"query": entity_query}, "id": "auto-project-jira"},
        {
            "name": "gmail_deadline_sweep",
            "args": {"query": entity_query, "time_from": start.isoformat(), "time_to": end.isoformat()},
            "id": "auto-project-gmail",
        },
        {
            "name": "calendar_search_events",
            "args": {"query": entity_query, "time_from": start.isoformat(), "time_to": end.isoformat()},
            "id": "auto-project-calendar",
        },
        {
            "name": "discord_search_program",
            "args": {"query": entity_query, "since": start.isoformat(), "until": end.isoformat()},
            "id": "auto-project-discord",
        },
    ]
    required_by_source = {
        "tasks": required[0],
        "jira": required[1],
        "gmail": required[2],
        "calendar": required[3],
        "discord": required[4],
    }
    existing = {call.get("name") for call in tool_calls}
    return [
        *tool_calls,
        *(
            call
            for source, call in required_by_source.items()
            if source in selected_sources and call["name"] not in existing
        ),
    ]


def _prefer_web_search(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Câu hỏi kiến thức công khai thì đưa sang web search."""
    if not context.web_search_enabled:
        return tool_calls
    if not _AGENT_PUBLIC_WEB.search(_agent_folded(context.query)):
        return tool_calls
    discord_reads = {
        "discord_search_program",
        "discord_search_my_messages",
        "discord_get_my_activity",
        "discord_list_announcements",
    }
    if not tool_calls or all(call.get("name") in discord_reads for call in tool_calls):
        return [{"name": "web_search", "args": {"query": context.query}, "id": "auto-web-search"}]
    return tool_calls


def _prefer_personal_discord_tool(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Không trả lời câu hỏi ngôi thứ nhất bằng chunk lẫn nhiều tác giả."""
    folded = _agent_folded(context.query)
    if _AGENT_MY_DISCORD_ACTIVITY.search(folded):
        target = "discord_get_my_activity"
    elif _AGENT_MY_DISCORD_MESSAGES.search(folded):
        target = "discord_search_my_messages"
    else:
        return tool_calls

    discord_reads = {
        "discord_search_program",
        "discord_search_my_messages",
        "discord_get_my_activity",
        "discord_list_announcements",
        # Tên cũ có thể còn do model sinh trong một lượt nâng cấp.
        "discord_search_messages",
    }
    source = next((call for call in tool_calls if call.get("name") == target), None)
    source = source or next((call for call in tool_calls if call.get("name") in discord_reads), None)
    non_discord = [call for call in tool_calls if call.get("name") not in discord_reads]
    raw_args = dict((source or {}).get("args") or {})
    allowed = {"since", "until"}
    if target == "discord_search_my_messages":
        allowed.add("query")
    args = {key: value for key, value in raw_args.items() if key in allowed}
    if target == "discord_search_my_messages":
        # Không kế thừa query do model dựng cho kho nhiều tác giả: nó có
        # thể chứa tên một người mà model tự đoán. Tool cá nhân đã khóa
        # author theo OAuth, và query phải là nguyên văn yêu cầu của user.
        args["query"] = context.query
    return [
        *non_discord,
        {
            "name": target,
            "args": args,
            "id": (source or {}).get("id") or f"auto-{target}",
        },
    ]


def _prefer_announcement_tool(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Hỏi chương trình thông báo gì thì đọc luồng thông báo, không tra độ liên quan.

    Cơ chế: nhận ra ý định bằng luật chuỗi, rồi thay mọi lời gọi truy hồi Discord
    chung bằng `discord_list_announcements`, giữ lại since/until model đã đặt.
    Câu hỏi cá nhân ("tôi đã nhắn gì") không đi qua đây vì luật cá nhân chạy sau
    và sẽ ghi đè lại — thứ tự đó là cố ý, danh tính người hỏi quan trọng hơn.
    """
    if not _AGENT_ANNOUNCEMENT.search(_agent_folded(context.query)):
        return tool_calls
    if any(call.get("name") == "discord_list_announcements" for call in tool_calls):
        return tool_calls

    generic = {"discord_search_program", "discord_search_messages"}
    source = next((call for call in tool_calls if call.get("name") in generic), None)
    others = [call for call in tool_calls if call.get("name") not in generic]
    raw_args = dict((source or {}).get("args") or {})
    args = {key: value for key, value in raw_args.items() if key in {"since", "until"}}
    return [
        *others,
        {
            "name": "discord_list_announcements",
            "args": args,
            "id": (source or {}).get("id") or "auto-discord-announcements",
        },
    ]


def _prefer_program_information(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Ưu tiên bản đội ngũ đã duyệt cho FAQ, không lấy thảo luận Discord vụn."""
    folded = _agent_folded(context.query)
    if not _AGENT_PROGRAM_INFORMATION.search(folded):
        return tool_calls
    if _AGENT_ANNOUNCEMENT.search(folded) or _AGENT_CALENDAR.search(folded):
        return tool_calls
    if any(call.get("name") == "program_information_search" for call in tool_calls):
        return tool_calls
    generic = {"discord_search_program", "discord_search_messages"}
    source = next((call for call in tool_calls if call.get("name") in generic), None)
    others = [call for call in tool_calls if call.get("name") not in generic]
    return [
        *others,
        {
            "name": "program_information_search",
            "args": {"query": context.query},
            "id": (source or {}).get("id") or "auto-program-information",
        },
    ]


def _prefer_planner_workspace(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Ép intent lập kế hoạch đi qua planner thay vì trả lời bằng danh sách task."""
    folded = _agent_folded(context.query)
    if not _AGENT_PLANNER.search(folded):
        return tool_calls
    is_configuration = bool(re.search(r"(?i)(?:dat|doi|sua|set|cau\s*hinh).{0,30}(?:gio|happy|nghi|workday)", folded))
    target = "configure_planner_workday" if is_configuration else "generate_planner_plan"
    if any(call.get("name") == target for call in tool_calls):
        return tool_calls
    if target == "configure_planner_workday":
        clocks = re.findall(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b", context.query)
        args: dict[str, object] = {}
        if "happy" in folded and len(clocks) >= 2:
            args.update({"happy_time_start": clocks[0], "happy_time_end": clocks[1], "happy_time_enabled": True})
        elif "nghi trua" in folded and len(clocks) >= 2:
            args.update({"lunch_start": clocks[0], "lunch_end": clocks[1]})
        elif len(clocks) >= 2:
            args.update({"workday_start": clocks[0], "workday_end": clocks[1]})
        return [*tool_calls, {"name": target, "args": args, "id": "auto-planner-config"}]
    days = 7 if re.search(r"(?i)(?:tuan|week)", folded) else 1
    return [
        *tool_calls,
        {"name": target, "args": {"days": days}, "id": "auto-planner-workspace"},
    ]


def agenda_window(query: str, current: datetime, temporal: TemporalDecision | None = None) -> tuple[datetime, datetime]:
    """Khoảng thời gian mà một câu hỏi lịch trình đang nói tới.

    Không nói mốc nào thì lấy bảy ngày tới: "tôi nên làm gì tiếp theo" hỏi về
    việc sắp phải làm, không phải về cả quý.
    """
    folded = _agent_folded(query)
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    resolved = temporal or resolve_temporal(query, current)
    if resolved.time_from and resolved.time_to:
        return resolved.time_from, resolved.time_to
    if "hom nay" in folded or "today" in folded or "daily" in folded:
        return day_start, day_start + timedelta(days=1)
    if "ngay mai" in folded or re.search(r"(?:^|\s)mai(?:$|\s|[?.!,])", folded) or "tomorrow" in folded:
        start = day_start + timedelta(days=1)
        return start, start + timedelta(days=1)
    if "tuan nay" in folded or "this week" in folded:
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
    if "tuan sau" in folded or "tuan toi" in folded or "next week" in folded:
        start = day_start - timedelta(days=day_start.weekday()) + timedelta(days=7)
        return start, start + timedelta(days=7)
    return current, current + timedelta(days=_AGENDA_HORIZON_DAYS)


def is_agenda_query(query: str) -> bool:
    """Câu hỏi kiểu "hôm nay tôi cần làm gì" — cần gom nhiều nguồn để trả lời.

    Câu có nêu đích danh một nguồn ("email hôm nay có gì") thì không tính: người
    dùng đã tự thu hẹp phạm vi, luật riêng của nguồn đó lo.
    """
    folded = _agent_folded(query)
    if _AGENT_CALENDAR.search(folded) or _AGENT_GMAIL.search(folded) or _AGENT_JIRA.search(folded):
        return False
    if _AGENT_PUBLIC_WEB.search(folded):
        return False
    if _AGENT_AGENDA.search(folded):
        return True
    if resolve_temporal(query, datetime.now().astimezone()).kind != "none" and _AGENT_OVERVIEW.search(folded):
        return True
    return bool(_AGENT_PERIOD.search(folded) and _AGENT_OVERVIEW.search(folded))


def _ensure_agenda_coverage(context: ToolPlanContext, tool_calls: list[dict]) -> list[dict]:
    """Rà đủ năm nguồn đọc cho một câu hỏi lịch trình.

    Cơ chế: dựng cửa sổ thời gian từ chính câu hỏi, rồi bổ sung những tool chưa
    được model gọi và cũng chưa chạy ở vòng trước. Năm nguồn nói năm chuyện khác
    nhau và không thay thế được nhau — `calendar_search_events` cho biết hôm nay
    có cuộc họp nào, `gmail_deadline_sweep` cho biết có thư nào cần xem,
    `list_tasks` là việc đã trích sẵn từ các connector, còn
    `jira_search_issues` là issue có deadline trong cửa sổ, còn
    `discord_search_program` là phần trao đổi chưa kịp thành task. Thiếu một
    nguồn là câu trả lời thiếu hẳn một mảng mà người dùng không biết là đã thiếu.

    Gmail đọc lùi về quá khứ chứ không theo cửa sổ của câu hỏi: thư nhắc về cuộc
    họp hôm nay thường đã tới từ mấy hôm trước.
    """
    if not is_agenda_query(context.query):
        return tool_calls

    temporal = context.temporal_resolution or resolve_temporal(context.query, context.now)
    start, end = agenda_window(context.query, context.now, temporal)
    historical_month = temporal.kind in {"explicit_month", "last_month", "this_month", "next_month"}
    mail_from = start if historical_month else start - timedelta(days=_AGENDA_MAIL_LOOKBACK_DAYS)
    mail_to = min(end, context.now)

    # Model có tự gọi Discord thì vẫn phải đóng khung lại: nó không biết hôm nay
    # là ngày nào theo múi giờ ứng dụng nên mốc nó đoán không được để nguyên.
    # list_tasks cũng vậy: model hay hiểu "hôm nay" là "đúng hạn hôm nay" rồi tự
    # thêm due_before/due_after, trong khi câu hỏi agenda đang hỏi "còn việc gì
    # đang treo" chứ không phải "việc gì đúng hạn hôm nay" — bó hẹp kiểu đó làm
    # rớt hết task có hạn ở ngày khác dù chúng vẫn còn nguyên trên bảng tasks.
    bounded: list[dict] = []
    for call in tool_calls:
        name = call.get("name")
        if name == "discord_search_program":
            args = dict(call.get("args") or {})
            args.setdefault("query", context.query)
            args["since"] = start.isoformat()
            args["until"] = end.isoformat()
            bounded.append({**call, "args": args})
            continue
        if name == "list_tasks":
            args = dict(call.get("args") or {})
            args.pop("due_before", None)
            args.pop("due_after", None)
            args.setdefault("status", "proposed")
            bounded.append({**call, "args": args})
            continue
        if name == "jira_search_issues":
            args = dict(call.get("args") or {})
            args.setdefault("query", "")
            args["due_after"] = start.isoformat()
            args["due_before"] = end.isoformat()
            bounded.append({**call, "args": args})
            continue
        bounded.append(call)

    required = [
        {"name": "list_tasks", "args": {"status": "proposed"}, "id": "auto-agenda-tasks"},
        {
            "name": "calendar_search_events",
            "args": {"query": "", "time_from": start.isoformat(), "time_to": end.isoformat()},
            "id": "auto-agenda-calendar",
        },
        {
            "name": "gmail_deadline_sweep",
            "args": {
                "time_from": mail_from.isoformat(),
                "time_to": mail_to.isoformat(),
            },
            "id": "auto-agenda-gmail-deadline-sweep",
        },
        {
            "name": "jira_search_issues",
            "args": {
                "query": "",
                "due_after": start.isoformat(),
                "due_before": end.isoformat(),
            },
            "id": "auto-agenda-jira",
        },
        {
            "name": "discord_search_program",
            "args": {
                "query": context.query,
                "since": start.isoformat(),
                "until": end.isoformat(),
            },
            "id": "auto-agenda-knowledge",
        },
    ]
    covered = {item.get("name") for item in context.observations}
    covered |= {call.get("name") for call in bounded}
    if context.available_tools is not None:
        covered |= {call["name"] for call in required if call["name"] not in context.available_tools}
    return [*bounded, *(call for call in required if call["name"] not in covered)]


def _tool_signature(call: dict) -> str:
    """Khoá ổn định để một action đã quan sát không bị model gọi lặp lại."""
    return f"{call.get('name', '')}:{dumps(call.get('args') or {}, sort_keys=True, ensure_ascii=False)}"


def _dedupe_tool_calls(tool_calls: list[dict], observations: list[dict]) -> list[dict]:
    """Bỏ tool đã chạy với đúng bộ tham số đó, và bỏ tool trùng trong cùng vòng."""
    seen = {_tool_signature({"name": item.get("name"), "args": item.get("args") or {}}) for item in observations}
    unique: list[dict] = []
    for call in tool_calls:
        signature = _tool_signature(call)
        if not call.get("name") or signature in seen:
            continue
        seen.add(signature)
        unique.append(call)
    return unique


def plan_tool_calls(tool_calls: list[dict], context: ToolPlanContext) -> list[dict]:
    """Chốt danh sách tool cho một vòng think, từ đề xuất của model.

    Cơ chế: chạy lần lượt các luật vá theo chủ đề (lịch, Gmail, tóm tắt ngày,
    web, câu hỏi ưu tiên rộng), rồi mới tới lưới an toàn cuối cùng và bước khử
    trùng. Thứ tự có ý nghĩa — luật web chỉ được ghi đè khi danh sách còn rỗng
    hoặc chỉ có mỗi truy hồi Discord, nên nó phải chạy sau các luật kia.
    """
    planned = list(tool_calls)
    planned = _prefer_calendar_search(context, planned)
    planned = _prefer_gmail_search(context, planned)
    planned = _prefer_gmail_bridge(context, planned)
    planned = _prefer_jira_search(context, planned)
    planned = _prefer_google_document_tools(context, planned)
    planned = _prefer_project_source_discovery(context, planned)
    planned = _prefer_program_information(context, planned)
    planned = _prefer_planner_workspace(context, planned)
    # Thông báo chính thức phải thay truy hồi Discord chung trước; luật cá nhân
    # chạy sau để câu “tôi đã nhắn gì về thông báo” vẫn ưu tiên danh tính user.
    planned = _prefer_announcement_tool(context, planned)
    planned = _prefer_personal_discord_tool(context, planned)
    planned = _prefer_web_search(context, planned)
    planned = _ensure_agenda_coverage(context, planned)
    planned = _remove_unrequested_discord(context, planned)
    planned = _apply_conversational_route(context, planned)

    # Model nhỏ hay im lặng bỏ qua bước tra nguồn rồi trả lời "không có thông
    # tin". Đây là trợ lý đọc ngữ cảnh công việc nên gần như câu nào cũng cần tra
    # nguồn; cứ tra sẵn ở vòng đầu rồi để model tự bỏ qua nếu không liên quan.
    if (
        not planned
        and (context.conversational_route or {}).get("action") not in {"EXPLAIN", "CLARIFY"}
        and not context.observations
        and context.tool_iterations == 0
        and not can_answer_from_memory(context.query)
        and not is_productivity_create(context.query, context.pending_action)
        # Gmail ghi chưa có tool thực thi trong agent này. Tra Discord
        # không thể giúp gửi mail và chỉ tạo câu trả lời lạc đề; để model
        # dừa trên contract chỉ-đọc và nói rõ giới hạn.
        and not (
            _AGENT_GMAIL.search(_agent_folded(context.query))
            and _AGENT_GMAIL_WRITE.search(_agent_folded(context.query))
        )
    ):
        folded = _agent_folded(context.query)
        if _AGENT_ANNOUNCEMENT.search(folded) and not _AGENT_MY_DISCORD_MESSAGES.search(folded):
            planned = [
                {
                    "name": "discord_list_announcements",
                    "args": {},
                    "id": "auto-discord-announcements",
                }
            ]
        elif _AGENT_MY_DISCORD_ACTIVITY.search(folded):
            planned = [{"name": "discord_get_my_activity", "args": {}, "id": "auto-my-discord-activity"}]
        elif _AGENT_MY_DISCORD_MESSAGES.search(folded):
            planned = [
                {
                    "name": "discord_search_my_messages",
                    "args": {"query": context.query},
                    "id": "auto-my-discord-messages",
                }
            ]
        elif _discord_is_relevant(context):
            planned = [
                {
                    "name": "discord_search_program",
                    "args": {"query": context.query},
                    "id": "auto-discord-search",
                }
            ]

    if context.available_tools is not None:
        planned = [call for call in planned if call.get("name") in context.available_tools]

    return _dedupe_tool_calls(planned, context.observations)
