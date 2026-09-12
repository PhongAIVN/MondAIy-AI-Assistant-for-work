"""Constrained write tool for calendar events, tasks, and todos.

The LLM may extract fields, but it does not decide whether a write is allowed.
The API places the authenticated user, the current turn, and any immediately
pending draft in a ContextVar.  This module validates that context again before
performing a side effect.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.connectors.calendar import CalendarAPIError, CalendarConnector, build_authuser_link
from src.services.connections import preferred_connection

ProductivityKind = Literal["calendar_event", "task", "todo"]

_CALENDAR_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}
# Docstring của create_productivity_item dặn model đừng đoán email từ tên gọi,
# nhưng đó chỉ là lời dặn — model vẫn có thể coi "Endy" như một email. Google
# Calendar trả 400 cho CẢ sự kiện chỉ vì một attendee sai định dạng, nên phải
# lọc cứng ở đây thay vì tin lời dặn suông.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Họ động từ "bảo trợ lý báo lại cho tôi". Trước đây chỉ có `nhắc tôi`, nên
# "nhắn tôi 3h40 hỏi quota AI" bị từ chối vì đúng MỘT chữ cái — người dùng viết
# `nhắn` chứ không phải `nhắc`. Model đã hiểu đúng hoàn toàn (nó tính ra
# 15:40 và gọi tool với đủ tham số); chính cổng regex này chặn lại.
#
# Bắt buộc phải có tân ngữ ngôi thứ nhất (`tôi`/`mình`), nếu không thì "báo cáo"
# hay "gọi vốn" sẽ khớp nhầm. Đây là ràng buộc giữ cổng không bị nới rộng.
_NOTIFY_ME = (
    r"(?:(?:nhắc|nhắn|báo|gọi|ping|thông\s+báo|đánh\s+thức)\s+(?:tin\s+)?(?:cho\s+)?(?:tôi|mình)"
    r"|\b(?:remind|notify|ping|text|message|wake)\s+me\b)"
)
_CREATE_VERB = re.compile(
    r"(?i)(?:\b(?:add|create|schedule|make)\b|tạo|thêm|đặt|ghi|lên\s+lịch|" + _NOTIFY_ME + r")"
)
_CALENDAR_NOUN = re.compile(
    r"(?i)(?:\b(?:calendar|event|meeting|workshop|appointment)\b|lịch|sự\s+kiện|cuộc\s+họp|cuộc\s+hẹn)"
)
_TASK_NOUN = re.compile(
    r"(?i)(?:\b(?:task|todo|to-do|reminder)\b|công\s+việc|nhiệm\s+vụ|việc\s+cần\s+làm|"
    + _NOTIFY_ME + r")"
)
_CALENDAR_WRITE_REQUEST = re.compile(
    r"(?i)(?:\b(?:add|create|schedule|make)\b|tao|them|dat|ghi|len\s+lich|nhac\s+(?:toi|minh))"
    r".*(?:\b(?:calendar|event|meeting|workshop|appointment)\b|lich|su\s+kien|cuoc\s+hop|cuoc\s+hen)"
)
_START_EVIDENCE = re.compile(
    # Mốc ngày/period đơn lẻ ("tối nay", "ngày mai") chưa đủ chứng minh
    # một giờ bắt đầu. Chỉ nhận giờ user thực sự nói; nếu model tự chọn 20:00
    # thì provenance vẫn đỏ và tool phải hỏi lại.
    r"(?i)(?:(?:lúc|luc|at)\s+\d{1,2}(?::\d{2}|h\d{0,2}|\s*(?:giờ|gio))?|"
    r"\d{1,2}(?::\d{2}|h\d{0,2})\b)"
)
_END_OR_DURATION_EVIDENCE = re.compile(
    r"(?i)(?:kéo\s+dài|thời\s+lượng|duration|for\s+\d+|"
    r"\d+\s*(?:phút|tiếng|minutes?|mins?|hours?|hrs?)\b|"
    r"(?:trong|khoảng)\s+\d+\s*(?:giờ|phút)\b|"
    # ":?" ở đây vì form nháp (ProductivityApprovalCard) gửi lại dạng
    # "kết thúc: 20:18:00 ..." — có dấu hai chấm chen giữa nhãn và giờ, thiếu
    # nó thì regex không nhận ra người dùng đã điền, cứ hỏi lại vô hạn dù ô
    # Kết thúc trên form đã có giá trị.
    r"(?:đến|tới|kết\s+thúc(?:\s+lúc)?|until|ends?\s+at)\s*:?\s*\d{1,2})"
)
_DEADLINE_EVIDENCE = re.compile(
    # Tên field và ngày đơn lẻ không đủ: reminder/task cần giờ cụ thể, không
    # cho model biến "ngày mai" thành 09:00 hay 23:59 theo default ngầm.
    r"(?i)(?:(?:lúc|luc|at)\s+\d{1,2}(?::\d{2}|h\d{0,2}|\s*(?:giờ|gio))?|"
    r"\d{1,2}(?::\d{2}|h\d{0,2})\b)"
)

_TITLE_COMMAND_PARTS = re.compile(
    r"(?i)(?:\b(?:dien\s+thoai|tro\s+ly|hey|hay|vui\s+long)\b|"
    r"\b(?:toi|minh|em)\s+(?:muon|can|co)\b|"
    r"\b(?:tao|them|dat|ghi|len\s+lich|create|add|schedule)\b"
    r"(?:\s+(?:mot))?(?:\s+(?:vao\s+)?(?:lich|calendar|su\s+kien|event|task|todo|"
    r"cong\s+viec|nhiem\s+vu))?|"
    r"\b(?:nhac|nhan|bao|goi|ping|thong\s+bao)\s+(?:tin\s+)?(?:cho\s+)?(?:toi|minh|em)\b|"
    r"\b(?:vao|tren)\s+(?:lich|calendar)\b|\b(?:cho|giup)\s+(?:toi|minh|em)\b)"
)
_TITLE_TIME_PARTS = re.compile(
    r"(?i)(?:\b(?:hom\s+nay|toi\s+nay|sang\s+nay|chieu\s+nay|ngay\s+mai|"
    r"sang\s+mai|chieu\s+mai|toi\s+mai|today|tonight|tomorrow)\b|"
    r"\b(?:luc|vao)\s+\d{1,2}(?::\d{2}|h\d{0,2})?\b|"
    r"\b\d{1,2}(?::\d{2}|h\d{0,2})\b|"
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|"
    r"\b(?:keo\s+dai|trong|khoang|for)\s+\d+\s*(?:phut|tieng|gio|minutes?|hours?)\b|"
    r"\b(?:nhe|nha|please)\b)"
)
_TIME_HINTS = (
    (re.compile(r"(?i)\bsang\s+mai\b"), "Sáng mai"),
    (re.compile(r"(?i)\bchieu\s+mai\b"), "Chiều mai"),
    (re.compile(r"(?i)\btoi\s+mai\b"), "Tối mai"),
    (re.compile(r"(?i)\bngay\s+mai\b|\btomorrow\b"), "Ngày mai"),
    (re.compile(r"(?i)\bsang\s+nay\b"), "Sáng nay"),
    (re.compile(r"(?i)\bchieu\s+nay\b"), "Chiều nay"),
    (re.compile(r"(?i)\btoi\s+nay\b|\btonight\b"), "Tối nay"),
    (re.compile(r"(?i)\bhom\s+nay\b|\btoday\b"), "Hôm nay"),
)


@dataclass(frozen=True)
class _ActionScope:
    user_id: str
    request_id: str
    current_query: str
    pending_action: dict | None


_scope: ContextVar[_ActionScope | None] = ContextVar("productivity_action_scope", default=None)


def set_productivity_action_scope(
    user_id: str,
    *,
    request_id: str,
    current_query: str,
    pending_action: dict | None = None,
) -> None:
    _scope.set(
        _ActionScope(
            user_id=user_id,
            request_id=request_id,
            current_query=current_query,
            pending_action=pending_action,
        )
    )


def reset_productivity_action_scope() -> None:
    _scope.set(None)


def _kind_is_explicit(text: str, kind: ProductivityKind) -> bool:
    original = text
    folded = _fold(text)
    noun = _CALENDAR_NOUN if kind == "calendar_event" else _TASK_NOUN
    return bool(_CREATE_VERB.search(original) and noun.search(original)) or (
        kind == "calendar_event" and _is_calendar_write_request(folded)
    )


def _is_calendar_write_request(text: str) -> bool:
    return bool(_CALENDAR_WRITE_REQUEST.search(_fold(text)))


def _authorized(scope: _ActionScope, kind: ProductivityKind) -> bool:
    if _kind_is_explicit(scope.current_query, kind) or (
        kind == "calendar_event" and _is_calendar_write_request(scope.current_query)
    ):
        return True
    pending = scope.pending_action or {}
    return pending.get("status") == "needs_clarification" and pending.get("kind") == kind


def _fold(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    ).replace("đ", "d")


def _title_has_user_evidence(title: str, query: str) -> bool:
    """Reject a title invented entirely by the model.

    Significant title words must occur in the current user message. Once a
    title has passed this check, its provenance flag travels with the pending
    draft instead of copying raw prompt text into message extras.
    """
    title_words = {word for word in re.findall(r"\w+", _fold(title)) if len(word) > 2}
    query_words = set(re.findall(r"\w+", _fold(query)))
    return bool(title_words) and title_words.issubset(query_words)


def _without_folded_matches(value: str, pattern: re.Pattern[str]) -> str:
    """Bỏ các span nhận diện trên bản không dấu nhưng giữ chữ gốc có dấu."""
    folded = _fold(value)
    characters = list(value)
    for match in pattern.finditer(folded):
        for index in range(match.start(), min(match.end(), len(characters))):
            characters[index] = " "
    return "".join(characters)


def _time_hint(query: str) -> str:
    folded = _fold(query)
    for pattern, label in _TIME_HINTS:
        if pattern.search(folded):
            return label
    return ""


def _infer_title_from_query(query: str) -> str:
    """Giữ phần nội dung user đã nói khi model bỏ trống title.

    Chỉ xoá command và mốc thời gian khỏi chính câu user; không sinh thêm từ
    nên title vẫn qua được cổng provenance `_title_has_user_evidence`.
    """
    candidate = _without_folded_matches(query, _TITLE_COMMAND_PARTS)
    candidate = _without_folded_matches(candidate, _TITLE_TIME_PARTS)
    candidate = re.sub(r"[;,.:!?]+", " ", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" -–—")
    folded_words = [word for word in re.findall(r"\w+", _fold(candidate)) if len(word) > 1]
    generic = {"lich", "calendar", "su", "kien", "event", "task", "todo", "viec"}
    if not folded_words or all(word in generic for word in folded_words):
        return ""
    return candidate[:1].upper() + candidate[1:]


def _field_provenance(scope: _ActionScope, title: str) -> dict[str, bool]:
    previous = (scope.pending_action or {}).get("provenance", {})
    query = scope.current_query
    return {
        "title_explicit": bool(previous.get("title_explicit") or _title_has_user_evidence(title, query)),
        "start_explicit": bool(previous.get("start_explicit") or _START_EVIDENCE.search(query)),
        "end_or_duration_explicit": bool(
            previous.get("end_or_duration_explicit")
            or _END_OR_DURATION_EVIDENCE.search(query)
            or (scope.pending_action and re.fullmatch(r"(?i)\s*\d+\s*giờ\s*", query))
        ),
        "deadline_explicit": bool(previous.get("deadline_explicit") or _DEADLINE_EVIDENCE.search(query)),
    }


def _merge_pending(scope: _ActionScope, key: str, value):
    if value not in (None, "", 0):
        return value
    return (scope.pending_action or {}).get("draft", {}).get(key)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    from src.agents.tools.time_tool import parse_timestamp

    parsed = parse_timestamp(value)
    return parsed.moment if parsed else None


def _clarification(
    *,
    kind: ProductivityKind,
    missing_fields: list[str],
    draft: dict,
    provenance: dict[str, bool],
) -> dict:
    labels = {
        "title": "tên nội dung",
        "starts_at": "thời gian bắt đầu",
        "end_or_duration": "thời gian kết thúc hoặc thời lượng",
        "deadline": "deadline",
    }
    missing = [labels[field] for field in missing_fields]
    time_hint = str(draft.get("time_hint") or "")
    title = str(draft.get("title") or "").strip()
    if kind == "calendar_event" and set(missing_fields) == {"title", "starts_at", "end_or_duration"}:
        question = (
            "Mình hiểu bạn muốn thêm một sự kiện vào lịch. Bạn cho mình xin tên sự kiện, "
            "thời gian bắt đầu và thời lượng hoặc thời gian kết thúc nhé."
        )
    elif kind == "calendar_event" and missing_fields == ["starts_at", "end_or_duration"] and time_hint:
        question = (
            f"{time_hint}, “{title}” bắt đầu lúc mấy giờ, "
            "và kéo dài bao lâu hoặc kết thúc lúc mấy giờ?"
        )
    elif kind == "calendar_event" and missing_fields == ["starts_at"] and time_hint:
        question = f"{time_hint}, “{title}” bắt đầu lúc mấy giờ?"
    elif missing_fields == ["end_or_duration"]:
        question = f"{draft.get('title') or 'Nội dung này'} kéo dài bao lâu hoặc kết thúc lúc mấy giờ?"
    elif missing_fields == ["deadline"] and time_hint:
        question = f"{time_hint} bạn muốn được nhắc “{title or 'việc này'}” lúc mấy giờ?"
    elif missing_fields == ["deadline"]:
        question = f"Deadline của {draft.get('title') or 'việc này'} là khi nào?"
    else:
        question = f"Mình cần thêm {', '.join(missing)} để tạo {('lịch' if kind == 'calendar_event' else kind)}."
    safe_draft = dict(draft)
    if "title" in missing_fields:
        safe_draft["title"] = ""
    if "starts_at" in missing_fields:
        safe_draft["starts_at"] = ""
    if "end_or_duration" in missing_fields:
        safe_draft["ends_at"] = ""
        safe_draft["duration_minutes"] = None
    if "deadline" in missing_fields:
        safe_draft["deadline"] = ""

    return {
        "status": "needs_clarification",
        "kind": kind,
        "missing_fields": missing_fields,
        "question": question,
        "message": question,
        "draft": safe_draft,
        # Keep only field-level evidence flags. Raw user text already belongs
        # to conversation history and is not duplicated into action metadata.
        "provenance": provenance,
    }


def _error(kind: ProductivityKind, message: str) -> dict:
    return {"status": "error", "kind": kind, "message": message}


@tool
async def create_productivity_item(
    kind: ProductivityKind,
    title: str = "",
    starts_at: str = "",
    ends_at: str = "",
    duration_minutes: int | None = None,
    deadline: str = "",
    description: str = "",
    calendar_id: str = "primary",
    attendees: list[str] | None = None,
) -> dict:
    """Create one user-requested calendar event, task, or todo.

    Call only when the user explicitly asks to create/add/schedule an item, or
    when they answer the immediately preceding clarification for a pending
    item. Never invent a missing time. First call ``current_datetime`` when a
    relative phrase must be resolved, then pass ISO-8601 values with timezone.

    Required fields:
      - calendar_event: title, starts_at, and either ends_at or duration_minutes
      - task/todo: title and deadline

    Args:
        kind: calendar_event, task, or todo
        title: Concise title taken from the user's words
        starts_at: ISO-8601 event start including timezone
        ends_at: ISO-8601 event end including timezone
        duration_minutes: Explicit duration; do not supply a default
        deadline: ISO-8601 task/todo deadline including timezone
        description: Optional details stated by the user
        calendar_id: Google Calendar target, normally primary
        attendees: Real email addresses the user explicitly gave for
            calendar_event invitees. Never invent an email for a bare name —
            leave this empty rather than guess.
    """
    scope = _scope.get()
    if scope is None or not scope.user_id:
        return _error(kind, "Chưa xác định được người dùng nên chưa tạo nội dung.")
    if not _authorized(scope, kind):
        return _error(
            kind,
            # Câu cũ đổ lỗi cho người dùng ("không có yêu cầu rõ ràng từ người dùng")
            # và `respond_node` bê nguyên nó ra làm cả câu trả lời. Người dùng
            # vừa nói rõ điều họ muốn thì đọc câu đó chỉ thấy bị phủ nhận.
            # Nói mình chưa chắc, và nói luôn cách gỡ.
            "Mình chưa chắc bạn muốn mình tạo cái này nên chưa tạo. "
            "Nhắn lại kèm từ như \"tạo task\" hoặc \"nhắc tôi lúc ...\" là mình làm ngay.",
        )

    title = str(_merge_pending(scope, "title", title) or "").strip()
    previous_title_explicit = bool(
        (scope.pending_action or {}).get("provenance", {}).get("title_explicit")
    )
    if not previous_title_explicit and not _title_has_user_evidence(title, scope.current_query):
        inferred_title = _infer_title_from_query(scope.current_query)
        if inferred_title:
            title = inferred_title
    starts_at = str(_merge_pending(scope, "starts_at", starts_at) or "").strip()
    ends_at = str(_merge_pending(scope, "ends_at", ends_at) or "").strip()
    duration_minutes = _merge_pending(scope, "duration_minutes", duration_minutes)
    deadline = str(_merge_pending(scope, "deadline", deadline) or "").strip()
    description = str(_merge_pending(scope, "description", description) or "").strip()
    calendar_id = (calendar_id or "primary").strip()
    # Danh sách nên _merge_pending (viết cho scalar) không dùng được: [] không
    # rơi vào (None, "", 0) nên sẽ "merge" thành chính cái rỗng đó, không bao
    # giờ lấy lại được draft trước — người dùng trả lời câu hỏi làm rõ ở lượt
    # sau mà không nhắc lại tên người tham dự thì mất trắng.
    attendees = [a.strip() for a in (attendees or []) if a and a.strip()] or (
        (scope.pending_action or {}).get("draft", {}).get("attendees") or []
    )
    attendees = [a for a in attendees if _EMAIL_RE.match(a)]
    provenance = _field_provenance(scope, title)
    time_hint = _time_hint(scope.current_query) or str(
        (scope.pending_action or {}).get("draft", {}).get("time_hint") or ""
    )

    draft = {
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "duration_minutes": duration_minutes,
        "deadline": deadline,
        "description": description,
        "calendar_id": calendar_id,
        "attendees": attendees,
        "time_hint": time_hint,
    }
    missing_fields: list[str] = []
    if not title or not provenance["title_explicit"]:
        missing_fields.append("title")

    if kind == "calendar_event":
        if not starts_at or not provenance["start_explicit"]:
            missing_fields.append("starts_at")
        if (not ends_at and not duration_minutes) or not provenance["end_or_duration_explicit"]:
            missing_fields.append("end_or_duration")
    elif not deadline or not provenance["deadline_explicit"]:
        missing_fields.append("deadline")

    if missing_fields:
        return _clarification(
            kind=kind,
            missing_fields=missing_fields,
            draft=draft,
            provenance=provenance,
        )

    if kind == "calendar_event":
        start = _parse_datetime(starts_at)
        end = _parse_datetime(ends_at)
        if start is None:
            return _clarification(
                kind=kind,
                missing_fields=["starts_at"],
                draft={**draft, "starts_at": ""},
                provenance=provenance,
            )
        if duration_minutes is not None:
            if duration_minutes <= 0 or duration_minutes > 10_080:
                return _error(kind, "Thời lượng phải lớn hơn 0 và không quá 7 ngày.")
            end = start + timedelta(minutes=duration_minutes)
        if end is None or end <= start:
            return _error(kind, "Thời gian kết thúc phải sau thời gian bắt đầu.")
        return _approval_required(
            scope,
            kind=kind,
            draft={
                **draft,
                "starts_at": start.isoformat(),
                "ends_at": end.isoformat(),
            },
            provenance=provenance,
        )

    due_at = _parse_datetime(deadline)
    if due_at is None:
        return _clarification(
            kind=kind,
            missing_fields=["deadline"],
            draft={**draft, "deadline": ""},
            provenance=provenance,
        )
    return _approval_required(
        scope,
        kind=kind,
        draft={**draft, "deadline": due_at.isoformat()},
        provenance=provenance,
    )


def _approval_required(
    scope: _ActionScope,
    *,
    kind: ProductivityKind,
    draft: dict,
    provenance: dict[str, bool],
) -> dict:
    approval_id = hashlib.sha256(scope.request_id.encode()).hexdigest()
    label = "sự kiện Calendar" if kind == "calendar_event" else kind
    action = {
        "status": "pending_approval",
        "kind": kind,
        "approval_id": approval_id,
        "message": (
            f"Mình đã chuẩn bị {label} “{draft['title']}”. Hãy kiểm tra thông tin và bấm Chấp nhận để thực hiện."
        ),
        "draft": draft,
        "provenance": provenance,
    }
    action["signature"] = _sign_action(action)
    return action


def _sign_action(action: dict) -> str:
    from src.config import get_settings

    secret = get_settings().app_secret_key
    if not secret:
        raise ValueError("APP_SECRET_KEY chưa cấu hình nên không thể ký action.")
    signed_fields = {key: action.get(key) for key in ("status", "kind", "approval_id", "draft", "provenance")}
    body = json.dumps(
        signed_fields,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def execute_productivity_action(user_id: str, action: dict) -> dict:
    """Execute one server-stored proposal after an authenticated approval."""
    if action.get("status") != "pending_approval":
        raise ValueError("Action không ở trạng thái chờ duyệt.")
    signature = str(action.get("signature") or "")
    if not signature or not hmac.compare_digest(signature, _sign_action(action)):
        raise ValueError("Chữ ký action không hợp lệ.")
    approval_id = str(action.get("approval_id") or "")
    if not approval_id:
        raise ValueError("Action thiếu approval ID.")
    kind = action.get("kind")
    if kind not in {"calendar_event", "task", "todo"}:
        raise ValueError("Loại action không hợp lệ.")
    draft = action.get("draft") or {}
    provenance = action.get("provenance") or {}
    title = str(draft.get("title") or "").strip()
    if not title or not provenance.get("title_explicit"):
        raise ValueError("Action thiếu tiêu đề.")

    scope = _ActionScope(
        user_id=user_id,
        request_id=f"approval:{approval_id}",
        current_query="",
        pending_action=None,
    )
    if kind == "calendar_event":
        if not provenance.get("start_explicit") or not provenance.get("end_or_duration_explicit"):
            raise ValueError("Action Calendar thiếu provenance thời gian.")
        starts_at = _parse_datetime(str(draft.get("starts_at") or ""))
        ends_at = _parse_datetime(str(draft.get("ends_at") or ""))
        if starts_at is None or ends_at is None or ends_at <= starts_at:
            raise ValueError("Action Calendar có khoảng thời gian không hợp lệ.")
        return await _create_calendar_event(
            scope,
            title=title,
            description=str(draft.get("description") or ""),
            starts_at=starts_at,
            ends_at=ends_at,
            calendar_id=str(draft.get("calendar_id") or "primary"),
            attendees=[str(a) for a in (draft.get("attendees") or [])],
        )

    due_at = _parse_datetime(str(draft.get("deadline") or ""))
    if due_at is None or not provenance.get("deadline_explicit"):
        raise ValueError("Action task/todo thiếu deadline hợp lệ.")
    return _create_task(
        scope,
        kind=kind,
        title=title,
        description=str(draft.get("description") or ""),
        due_at=due_at,
    )


async def _create_calendar_event(
    scope: _ActionScope,
    *,
    title: str,
    description: str,
    starts_at: datetime,
    ends_at: datetime,
    calendar_id: str,
    attendees: list[str] | None = None,
) -> dict:
    from src.db import engine

    with Session(engine) as db:
        connection = preferred_connection(db, scope.user_id, "google")
        if connection is None:
            return _error("calendar_event", "Google Calendar chưa được kết nối.")
        if not set((connection.scopes or "").split()).intersection(_CALENDAR_WRITE_SCOPES):
            return _error(
                "calendar_event",
                "Kết nối Google hiện chỉ có quyền đọc. Hãy kết nối lại để cấp quyền tạo lịch.",
            )

        event_id = hashlib.sha256(scope.request_id.encode()).hexdigest()[:32]
        try:
            created = await CalendarConnector(connection, db).create_event(
                calendar_id=calendar_id,
                title=title,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                event_id=event_id,
                attendees=attendees,
            )
        except CalendarAPIError as exc:
            return _error("calendar_event", str(exc))

    return {
        "status": "created",
        "kind": "calendar_event",
        "message": (f"Đã thêm “{title}” vào Google Calendar từ {starts_at.isoformat()} đến {ends_at.isoformat()}."),
        "result": {
            "calendar_event_id": str(created["id"]),
            "calendar_url": build_authuser_link(created.get("htmlLink"), connection.provider_user_id),
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
    }


def _create_task(
    scope: _ActionScope,
    *,
    kind: Literal["task", "todo"],
    title: str,
    description: str,
    due_at: datetime,
) -> dict:
    from src.db import engine
    from src.models.task import Task
    from src.services.reminders import generate_default_reminders

    # `tasks.cluster_key` là VARCHAR(64). Giữ prefix để phân biệt nguồn nhưng
    # cắt digest còn 58 ký tự: 6 + 58 = 64. Trước đây ghép toàn bộ SHA-256 tạo
    # chuỗi 70 ký tự, SQLite vẫn nhận nhưng PostgreSQL production từ chối.
    cluster_key = f"agent-{hashlib.sha256(scope.request_id.encode()).hexdigest()[:58]}"
    with Session(engine) as db:
        row = db.execute(
            select(Task).where(Task.user_id == scope.user_id, Task.cluster_key == cluster_key)
        ).scalar_one_or_none()
        already_created = row is not None
        if row is None:
            row = Task(
                user_id=scope.user_id,
                cluster_key=cluster_key,
                title=title,
                detail=description,
                due_at=due_at.astimezone(UTC),
                ambiguous=False,
                status="confirmed",
                source_count=1,
                signal_strength=1.0,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            # Task tạo từ chat là `confirmed` ngay, nhưng trước đây đường này
            # KHÔNG sinh mốc nhắc nào — khác hẳn confirm thủ công ở
            # `src/api/tasks.py` và đường pipeline ở `persist.py`. Hệ quả:
            # "nhắc tôi 3h40" tạo được task có hạn mà không bao giờ nhắc.
            # Không có vòng quét nền nào bù cho việc này.
            generate_default_reminders(db, row)
        # Đọc id TRONG session. `generate_default_reminders` có commit bên
        # trong, mà commit làm hết hạn thuộc tính của `row`; đọc `row.id` sau
        # khi thoát `with` sẽ nổ DetachedInstanceError.
        task_id = row.id

    label = "todo" if kind == "todo" else "task"
    return {
        "status": "created",
        "kind": kind,
        "message": f"Đã tạo {label} “{title}” với deadline {due_at.isoformat()}.",
        "result": {
            "task_id": task_id,
            "deadline": due_at.isoformat(),
            "already_created": already_created,
        },
    }
