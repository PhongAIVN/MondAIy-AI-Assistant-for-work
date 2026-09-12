"""Phát hiện task và sự kiện lịch bị trùng nhau, rồi để người dùng chọn ưu tiên.

Luồng: detect (đọc task + bộ nhớ đệm lịch, không gọi Google) -> mỗi cặp trùng
thành 1 dòng `schedule_conflicts` kèm gợi ý rule-based -> người dùng resolve.

Hai kiểu trùng, xem docstring `ScheduleConflict`:

- `same_item`: tiêu đề gần giống và giờ sát nhau -> khả năng cùng một việc.
- `time_overlap`: hai việc khác nhau nhưng chiếm cùng khoảng giờ.

Ba giới hạn cố ý, không phải thiếu sót:

- Gợi ý bằng luật, không dùng LLM. Người dùng phải đọc được vì sao hệ thống
  nghiêng về một bên (PRD §8 yêu cầu giải thích được), và OD-03 về OpenRouter
  còn chưa chốt nên không thêm phụ thuộc LLM vào đường này.
- Không đủ căn cứ thì trả `undecided` chứ không đoán bên nào hơn.
- Resolve KHÔNG ghi gì lên Google và không tự dời hạn chót. Dời một cuộc họp
  của người khác hay tự đoán giờ mới đều vượt quá thẩm quyền của sản phẩm
  (FR-061: giờ còn mơ hồ thì để trống, không tự đoán).

TODO(PRD): kiểu `same_item` nằm trong tinh thần FR-032 (mâu thuẫn thì hiện cả
hai, không tự chọn). Kiểu `time_overlap` và thao tác chọn ưu tiên thì CHƯA có
FR tương ứng — cần PM chốt trước khi coi là phạm vi đã duyệt.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.calendar_event import CalendarEvent
from src.models.schedule_conflict import ScheduleConflict
from src.models.task import Task

# Task chỉ có một mốc `due_at`, không có độ dài. Lấy khối 30 phút giống
# src/api/tasks.py (calendar-sync) để hai chỗ nói cùng một điều về "một task
# chiếm bao nhiêu thời gian".
TASK_BLOCK = timedelta(minutes=30)
# Sự kiện thiếu `ends_at` (Google cho phép) cũng dùng đúng khối đó.
EVENT_FALLBACK_BLOCK = timedelta(minutes=30)
# Cùng ngưỡng tiêu đề với cluster_node để "trùng" nghĩa như nhau ở cả hai chỗ.
TITLE_SIMILARITY_THRESHOLD = 0.72
# Cùng một việc thì hai nguồn hay lệch giờ chút ít (nguồn ghi 14:00, lịch đặt
# 14:15). Rộng hơn 2 tiếng thì khả năng cao là hai việc khác nhau.
SAME_ITEM_START_TOLERANCE = timedelta(hours=2)
# Trạng thái task còn đáng để đối chiếu. dismissed/completed/cancelled thì
# không còn gì phải ưu tiên nữa.
ACTIVE_TASK_STATUSES = ("proposed", "confirmed")
# Task có `signal_strength` từ mức này trở lên nghĩa là đã có nhiều nguồn xác
# nhận cùng một hạn chót — khớp cách cluster_node tính (2/3 nguồn).
STRONG_SIGNAL = 0.66
# Người dùng bỏ qua lời nhắc từ mức này trở lên là tín hiệu họ không coi task
# quan trọng (ADR-007 mục 5 dùng chính con số này để giảm ưu tiên).
REPEATED_DISMISS = 2

RESOLUTIONS = ("prioritize_task", "prioritize_event", "accept_both")


def _as_utc(value: datetime) -> datetime:
    """SQLite đọc lại `DateTime(timezone=True)` thành naive — chuẩn hoá về
    UTC-aware trước khi so sánh, cùng cách src/services/reminders.py xử lý."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _normalize_title(title: str) -> str:
    """Bỏ khoảng trắng thừa và phân biệt hoa thường trước khi so tiêu đề."""
    return " ".join(title.lower().split())


def _titles_match(left: str, right: str) -> bool:
    """So tiêu đề mờ, cùng thuật toán và ngưỡng với cluster_node."""
    ratio = SequenceMatcher(None, _normalize_title(left), _normalize_title(right)).ratio()
    return ratio >= TITLE_SIMILARITY_THRESHOLD


def _task_window(task: Task) -> tuple[datetime, datetime]:
    """Khoảng thời gian một task chiếm trên lưới lịch.

    Task cả ngày chiếm trọn ngày đó; task có giờ chiếm một khối TASK_BLOCK kể
    từ hạn chót.
    """
    start = _as_utc(task.due_at)
    if task.all_day:
        midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight, midnight + timedelta(days=1)
    return start, start + TASK_BLOCK


def _event_window(event: CalendarEvent) -> tuple[datetime, datetime]:
    """Khoảng thời gian một sự kiện chiếm, bù khối mặc định khi thiếu `ends_at`."""
    start = _as_utc(event.starts_at)
    if event.ends_at is not None:
        end = _as_utc(event.ends_at)
        if end > start:
            return start, end
    if event.all_day:
        midnight = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight, midnight + timedelta(days=1)
    return start, start + EVENT_FALLBACK_BLOCK


def _overlap_minutes(left: tuple[datetime, datetime], right: tuple[datetime, datetime]) -> int:
    """Số phút hai khoảng chồng lên nhau; 0 nghĩa là không chồng."""
    overlap_start = max(left[0], right[0])
    overlap_end = min(left[1], right[1])
    seconds = (overlap_end - overlap_start).total_seconds()
    return int(seconds // 60) if seconds > 0 else 0


def _conflict_key(
    user_id: str,
    conflict_type: str,
    task: Task,
    event: CalendarEvent,
    task_start: datetime,
    event_start: datetime,
) -> str:
    """Khoá định danh một lần trùng, có băm cả giờ hai bên.

    Giờ nằm trong khoá là điều kiện để "đổi giờ thì sinh phiên bản mới" hoạt
    động: cặp task/sự kiện cũ đổi hạn chót sẽ cho khoá khác, dòng cũ chuyển
    `superseded` và dòng mới lại chờ người dùng quyết. Nếu khoá chỉ gồm id thì
    một quyết định cũ sẽ vô tình che mất lần trùng mới.
    """
    raw = "|".join(
        [
            user_id,
            conflict_type,
            str(task.id),
            event.calendar_id,
            event.event_id,
            task_start.isoformat(),
            event_start.isoformat(),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


def _classify(task: Task, event: CalendarEvent) -> tuple[str, int] | None:
    """Xác định cặp (task, sự kiện) trùng kiểu gì, hoặc None nếu không trùng.

    Thứ tự kiểm tra có chủ đích: `same_item` xét trước `time_overlap`, vì hai
    bản của cùng một việc thì đương nhiên chồng giờ, mà báo là "xung đột lịch"
    sẽ đẩy người dùng đi giải quyết sai vấn đề.

    `time_overlap` chỉ xét khi cả hai bên đều có giờ cụ thể. Một sự kiện cả
    ngày (sinh nhật, ngày nghỉ) không chiếm chỗ của khối 30 phút nào, gắn nhãn
    xung đột cho nó chỉ tạo nhiễu.
    """
    task_window = _task_window(task)
    event_window = _event_window(event)
    overlap = _overlap_minutes(task_window, event_window)

    starts_close = abs((task_window[0] - event_window[0]).total_seconds()) <= SAME_ITEM_START_TOLERANCE.total_seconds()
    if _titles_match(task.title, event.title) and starts_close:
        return "same_item", overlap

    if overlap > 0 and not task.all_day and not event.all_day:
        return "time_overlap", overlap

    return None


def _suggest(conflict_type: str, task: Task) -> tuple[str, list[str]]:
    """Suy ra nên ưu tiên bên nào, kèm lý do đọc được.

    Cơ chế: một chuỗi luật xếp theo độ mạnh của bằng chứng, luật nào khớp trước
    thì thắng, không khớp luật nào thì trả `undecided`. Mọi luật đều dựa vào
    thuộc tính đã có sẵn của task (mức mơ hồ, trạng thái, số nguồn, số lần bỏ
    qua nhắc) chứ không suy diễn gì về nội dung sự kiện — mondaiy không biết
    một cuộc họp trên lịch quan trọng tới đâu, nên không giả vờ biết.
    """
    if conflict_type == "same_item":
        if task.status == "proposed":
            # Việc đã nằm trên lịch rồi, bản task chỉ là đề xuất trùng.
            return "prioritize_event", ["event_already_on_calendar"]
        if task.source_count > 0:
            # Task đã xác nhận và có bằng chứng nguồn: nó là bản dày dữ liệu hơn.
            return "prioritize_task", ["task_has_evidence"]
        return "undecided", ["evidence_tie"]

    if task.ambiguous:
        # Giờ của task vốn là suy đoán, dời nó rẻ hơn dời một cuộc họp.
        return "prioritize_event", ["task_time_ambiguous"]
    if task.reminder_dismiss_count >= REPEATED_DISMISS:
        return "prioritize_event", ["task_repeatedly_dismissed"]
    if task.status == "confirmed" and task.signal_strength >= STRONG_SIGNAL:
        return "prioritize_task", ["task_multi_source"]
    if task.status == "proposed":
        # Task chưa được xác nhận, còn sự kiện là cam kết đã có trên lịch.
        return "prioritize_event", ["task_not_confirmed"]
    return "undecided", ["evidence_tie"]


def _event_snapshot(event: CalendarEvent) -> dict:
    """Ảnh chụp bên sự kiện, đủ để giao diện vẽ panel mà không đọc thêm bảng."""
    start, end = _event_window(event)
    return {
        "title": event.title,
        "calendar_id": event.calendar_id,
        "event_id": event.event_id,
        "starts_at": start.isoformat(),
        "ends_at": end.isoformat(),
        "all_day": event.all_day,
        "deep_link": event.deep_link,
        "synced_at": _as_utc(event.synced_at).isoformat() if event.synced_at else None,
    }


def _candidate_tasks(db: Session, user_id: str, time_from: datetime, time_to: datetime) -> list[Task]:
    """Task còn sống, có hạn chót rơi vào cửa sổ đang quét.

    Nới cửa sổ ra hai đầu một ngày vì task cả ngày và sự kiện cả ngày được quy
    về nửa đêm địa phương — một task nằm sát biên vẫn phải được đối chiếu.
    """
    stmt = select(Task).where(
        Task.user_id == user_id,
        Task.status.in_(ACTIVE_TASK_STATUSES),
        Task.due_at.is_not(None),
        Task.due_at >= time_from - timedelta(days=1),
        Task.due_at <= time_to + timedelta(days=1),
    )
    return list(db.execute(stmt).scalars())


def _candidate_events(db: Session, user_id: str, time_from: datetime, time_to: datetime) -> list[CalendarEvent]:
    """Sự kiện còn ở nguồn trong cửa sổ đang quét.

    Chỉ đọc bộ nhớ đệm `calendar_events`: đây đúng dữ liệu người dùng đang
    thấy trên lưới lịch, và không gọi Google nghĩa là detect chạy được ở mọi
    chỗ (kể cả trong confirm task) mà không tốn hạn mức API. Lọc theo giao nhau
    của khoảng thời gian thay vì chỉ theo `starts_at`, vì một event dài có thể
    bắt đầu trước cửa sổ hơn một ngày nhưng vẫn chiếm thời gian trong cửa sổ.
    """
    window_start = time_from - timedelta(days=1)
    window_end = time_to + timedelta(days=1)
    stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status == "active",
        CalendarEvent.starts_at <= window_end,
        or_(CalendarEvent.ends_at.is_(None), CalendarEvent.ends_at >= window_start),
    )
    return list(db.execute(stmt).scalars())


def _inactive_task_ids(db: Session, user_id: str, task_ids: list[int]) -> set[int]:
    """Trong các task được hỏi, những task không còn đáng đối chiếu nữa.

    Gồm task đã bỏ qua/hoàn thành/huỷ, task đã mất hạn chót, và task không còn
    tồn tại. Dùng để đóng những dòng `open` treo lại sau khi người dùng xử lý
    task ở chỗ khác — kể cả khi task đó nằm ngoài cửa sổ đang quét.
    """
    unique_ids = set(task_ids)
    if not unique_ids:
        return set()
    rows = db.execute(select(Task).where(Task.user_id == user_id, Task.id.in_(unique_ids))).scalars()
    active = {row.id for row in rows if row.status in ACTIVE_TASK_STATUSES and row.due_at is not None}
    return unique_ids - active


def detect_conflicts(
    db: Session,
    user_id: str,
    *,
    time_from: datetime,
    time_to: datetime,
    now: datetime | None = None,
) -> list[ScheduleConflict]:
    """Quét một cửa sổ thời gian và đồng bộ bảng `schedule_conflicts`.

    Cơ chế bốn bước:

    1. Ghép mọi cặp (task còn sống, sự kiện còn ở nguồn) trong cửa sổ, bỏ cặp
       đã biết là một (task.calendar_event_id trỏ đúng sự kiện đó).
    2. Cặp nào trùng thì tính `conflict_key`. Khoá đã tồn tại thì giữ nguyên
       dòng — chạy lại detect không sinh bản trùng và không xoá quyết định cũ.
    3. Khoá mới trên một cặp đã có dòng `open` nghĩa là giờ đã đổi: dòng cũ
       chuyển `superseded`, dòng mới mở ra chờ quyết định.
    4. Dòng `open` mà lần quét này không thấy trùng nữa thì chuyển `stale`.

    Trả về các dòng đang `open` sau khi đồng bộ, sắp theo giờ task.
    """
    now = now or datetime.now(UTC)
    tasks = _candidate_tasks(db, user_id, time_from, time_to)
    events = _candidate_events(db, user_id, time_from, time_to)

    existing_rows = list(db.execute(select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)).scalars())
    rows_by_key = {row.conflict_key: row for row in existing_rows}
    detected_keys: set[str] = set()

    for task in tasks:
        task_window = _task_window(task)
        for event in events:
            if task.calendar_event_id and task.calendar_event_id == event.event_id:
                # Chính task này đã tạo ra sự kiện đó qua calendar-sync — trùng
                # theo thiết kế, không phải chuyện cần người dùng quyết.
                continue
            classified = _classify(task, event)
            if classified is None:
                continue
            conflict_type, overlap = classified
            event_window = _event_window(event)
            key = _conflict_key(user_id, conflict_type, task, event, task_window[0], event_window[0])
            detected_keys.add(key)
            if key in rows_by_key:
                continue

            suggestion, reasons = _suggest(conflict_type, task)
            for row in existing_rows:
                same_pair = (
                    row.task_id == task.id
                    and row.calendar_id == event.calendar_id
                    and row.event_id == event.event_id
                    and row.status == "open"
                )
                if same_pair:
                    row.status = "superseded"
            created = ScheduleConflict(
                user_id=user_id,
                conflict_key=key,
                conflict_type=conflict_type,
                task_id=task.id,
                calendar_id=event.calendar_id,
                event_id=event.event_id,
                task_starts_at=task_window[0],
                event_starts_at=event_window[0],
                overlap_minutes=overlap,
                event_snapshot=_event_snapshot(event),
                suggestion=suggestion,
                suggestion_reasons=reasons,
                status="open",
                detected_at=now,
            )
            db.add(created)
            existing_rows.append(created)
            rows_by_key[key] = created

    scanned_task_ids = {task.id for task in tasks}
    stale_task_ids = _inactive_task_ids(db, user_id, [row.task_id for row in existing_rows if row.status == "open"])
    for row in existing_rows:
        if row.status != "open" or row.conflict_key in detected_keys:
            continue
        if row.task_id in stale_task_ids:
            # Task đã bị bỏ qua/hoàn thành/huỷ, hoặc hạn chót đã bị xoá —
            # không còn gì để ưu tiên, dù task nằm ngoài cửa sổ quét.
            row.status = "stale"
            continue
        if row.task_id not in scanned_task_ids:
            # Task nằm ngoài cửa sổ quét — lần này không nói được gì về nó,
            # đóng dòng ở đây sẽ xoá mất một xung đột vẫn còn thật.
            continue
        row.status = "stale"

    db.commit()
    return list_open_conflicts(db, user_id)


def detect_for_task(db: Session, task: Task, *, now: datetime | None = None) -> list[ScheduleConflict]:
    """Quét quanh hạn chót của đúng một task, dùng ngay sau khi task confirmed.

    Cửa sổ hẹp (±1 ngày) để confirm không phải trả giá cho một lần quét cả
    tháng, nhưng vẫn đủ rộng cho task cả ngày và lệch múi giờ.
    """
    if task.due_at is None:
        return []
    due_at = _as_utc(task.due_at)
    return detect_conflicts(
        db,
        task.user_id,
        time_from=due_at - timedelta(days=1),
        time_to=due_at + timedelta(days=1),
        now=now,
    )


def list_conflicts(db: Session, user_id: str, *, status: str | None = None) -> list[ScheduleConflict]:
    """Đọc các lần trùng của một người dùng, tuỳ chọn lọc theo trạng thái."""
    stmt = select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)
    if status is not None:
        stmt = stmt.where(ScheduleConflict.status == status)
    stmt = stmt.order_by(ScheduleConflict.task_starts_at, ScheduleConflict.id)
    return list(db.execute(stmt).scalars())


def list_open_conflicts(db: Session, user_id: str) -> list[ScheduleConflict]:
    """Các lần trùng còn chờ người dùng quyết."""
    return list_conflicts(db, user_id, status="open")


def resolve_conflict(
    db: Session,
    conflict: ScheduleConflict,
    resolution: str,
    *,
    note: str = "",
    now: datetime | None = None,
) -> ScheduleConflict:
    """Ghi lại quyết định của người dùng và áp hệ quả tối thiểu.

    Cơ chế: mọi kiểu trùng đều chỉ ghi `resolution` (nên dòng này về sau đọc
    được là người dùng có làm theo gợi ý hay không). Riêng `same_item` mới đụng
    tới task, và đụng tối thiểu:

    - `prioritize_event`: task là bản trùng của việc đã nằm trên lịch -> task
      chuyển `dismissed` và trỏ `calendar_event_id` sang sự kiện đó, nên lần
      detect sau không báo lại nữa.
    - `prioritize_task`: task là bản chính -> chỉ trỏ `calendar_event_id`, giữ
      nguyên trạng thái task.

    `time_overlap` không sửa gì cả: dời một cuộc họp hay đoán một hạn chót mới
    đều là việc của người dùng, không phải của sản phẩm.
    """
    if resolution not in RESOLUTIONS:
        raise ValueError(f"Quyết định không hợp lệ: {resolution}")
    if conflict.status != "open":
        raise ValueError(f"Lần trùng này đang ở trạng thái '{conflict.status}', không quyết lại được.")

    now = now or datetime.now(UTC)
    conflict.resolution = resolution
    conflict.resolution_note = note.strip()
    conflict.status = "resolved"
    conflict.resolved_at = now

    if conflict.conflict_type == "same_item" and resolution in ("prioritize_event", "prioritize_task"):
        task = db.execute(
            select(Task).where(Task.id == conflict.task_id, Task.user_id == conflict.user_id)
        ).scalar_one_or_none()
        if task is not None:
            task.calendar_event_id = conflict.event_id
            if resolution == "prioritize_event" and task.status in ACTIVE_TASK_STATUSES:
                task.status = "dismissed"

    db.commit()
    db.refresh(conflict)
    return conflict
