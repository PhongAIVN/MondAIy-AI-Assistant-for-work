"""Luồng thông báo end-to-end — 4 loại chạy chung 1 pipe (2026-08-12):

- task_due: mốc nhắc task đã confirmed sắp tới hạn (ADR-007, PRD §8.9 FR-090..097).
- task_proposed: task mới cần confirm (thay badge đếm rời trước đây).
- conflict_schedule: 2 task confirmed trùng/gần giờ nhau.
- conflict_evidence: 2 nguồn nói khác nhau về cùng deadline (fuse_and_rank()).
- daily_brief: tổng hợp cuối ngày theo giờ user tự chọn (mặc định TẮT).

Sinh thông báo -> gộp/chặn bão khi một kênh hỏi bundle tới hạn -> ghi nhận đã
giao (idempotent, tách receipt theo từng kênh) -> nhắc lại/bỏ qua không đụng
task.status.

Ba kênh giao dùng chung đúng pipe này và khác nhau đúng ở bước cuối: extension
tự kéo bằng chrome.alarms (ADR-007 mục 9), Telegram và Web Push do worker đẩy.
Vì vậy mọi luật chống bão — gộp bundle, giờ yên lặng, trần mỗi giờ, tắt kênh,
tắt theo loại — chỉ được cài đặt ở `get_due_notifications()`, không nhân bản
sang từng kênh.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from src.agents.briefing.evidence import EvidenceCluster
from src.models.channel_delivery import ChannelNotificationDelivery
from src.models.notification_preference import NotificationPreference
from src.models.reminder import NotificationDelivery, Reminder
from src.models.task import Task
from src.models.task_evidence import TaskEvidence

# FR-090: mặc định trước 1 ngày và trước 30 phút so với hạn chót.
DEFAULT_MILESTONES: tuple[tuple[str, timedelta], ...] = (
    ("1_day", timedelta(days=1)),
    ("30_min", timedelta(minutes=30)),
    # Nhắc ĐÚNG mốc giờ, không trừ lùi. Thiếu mốc này thì "nhắc tôi 3h40" lúc
    # 15:08 chỉ bắn 15:10 rồi im lặng đúng lúc người dùng cần — hệ thống mô
    # hình hoá hạn chót (nhắc TRƯỚC) mà không có báo thức (nhắc ĐÚNG LÚC).
    # Đặt cuối để hai mốc cảnh báo sớm vẫn được tạo trước.
    ("at_time", timedelta(0)),
)
DEFAULT_SNOOZE = timedelta(minutes=15)
# FR-096: 3 lý do bỏ qua cố định — lý do làm giảm ưu tiên lần sau, không xoá bằng chứng gốc.
DISMISS_REASONS = ("khong_can_nua", "da_lam_o_cho_khac", "han_chot_sai")
_TASK_RESOLVED_REASON = "task_resolved"
# 2 task confirmed cách nhau trong khoảng này bị coi là trùng giờ.
CONFLICT_SCHEDULE_WINDOW_MINUTES = 60
# Kind không gắn 1 task cụ thể (conflict_evidence gộp nhiều nguồn, daily_brief
# tổng hợp toàn user) thì không có "hạn" thật để tính urgency — dùng điểm cố
# định, xếp trên mức nhắc task_due bình thường vì cả hai đều cần chú ý ngay.
_FLAT_PRIORITY_BY_KIND = {"conflict_evidence": 800, "daily_brief": 200, "calendar_changed": 700}
# Chỉ báo lịch đổi khi sự kiện còn cách hiện tại trong khoảng này. Một buổi bị
# dời sau ba tuần nữa không đáng chen ngang; nó sẽ tự xuất hiện ở lưới tuần.
CALENDAR_CHANGE_HORIZON = timedelta(days=14)
_KIND_URGENCY_BONUS = {"conflict_schedule": 300}


def _as_utc(dt: datetime) -> datetime:
    """SQLite trả `DateTime(timezone=True)` naive sau khi đọc lại — chuẩn hoá
    về UTC-aware trước khi so sánh/tính toán, cùng cách guard tasks.py đã dùng."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


# Tên kênh giao -> cột bật/tắt tương ứng trong NotificationPreference. Bảng tra
# này là nơi duy nhất biết ánh xạ đó, để thêm kênh thứ tư chỉ phải sửa một chỗ.
_CHANNEL_ENABLED_FIELD = {
    "extension": "extension_enabled",
    "telegram": "telegram_enabled",
    "webpush": "web_push_enabled",
}


def is_channel_enabled(pref: NotificationPreference, channel: str) -> bool:
    """Người dùng còn muốn nhận thông báo trên kênh này hay không.

    Kênh lạ (gõ sai hằng số, kênh mới chưa khai báo ở bảng trên) được coi là
    BẬT: hằng số kênh do code quyết chứ không do người dùng nhập, nên một lỗi
    tra bảng phải biểu hiện thành thông báo thừa — thấy ngay và sửa được — chứ
    không phải thành im lặng tuyệt đối mà không ai biết để báo.
    """
    field = _CHANNEL_ENABLED_FIELD.get(channel)
    if field is None:
        return True
    return bool(getattr(pref, field))


def get_or_create_preference(db: Session, user_id: str) -> NotificationPreference:
    pref = db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id)).scalar_one_or_none()
    if pref is not None:
        return pref
    pref = NotificationPreference(user_id=user_id)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


def generate_default_reminders(db: Session, task: Task, *, now: datetime | None = None) -> list[Reminder]:
    """Sinh mốc nhắc mặc định (kind=task_due) cho 1 task vừa confirmed có due_at.

    Bỏ qua mốc đã trôi qua so với `now` — không nhắc việc đã hết hạn nhắc.
    Idempotent theo `milestone`: gọi lại (vd. confirm lần nữa sau khi sửa
    due_at) không tạo trùng mốc còn `scheduled`.
    """
    if task.due_at is None:
        return []
    now = now or datetime.now(UTC)
    due_at = _as_utc(task.due_at)

    existing_milestones = {
        row.milestone
        for row in db.execute(
            select(Reminder).where(Reminder.task_id == task.id, Reminder.kind == "task_due", Reminder.status == "scheduled")
        ).scalars()
    }

    created: list[Reminder] = []
    for milestone, offset in DEFAULT_MILESTONES:
        if milestone in existing_milestones:
            continue
        scheduled_at = due_at - offset
        if scheduled_at <= now:
            continue
        reminder = Reminder(
            task_id=task.id, user_id=task.user_id, kind="task_due", milestone=milestone, scheduled_at=scheduled_at
        )
        db.add(reminder)
        created.append(reminder)

    if created:
        db.commit()
        for reminder in created:
            db.refresh(reminder)
    return created


def reschedule_due_reminders(db: Session, task: Task) -> list[Reminder]:
    """Dời hạn một task đang mở thì các mốc nhắc task_due tính theo hạn cũ
    phải tắt đi và sinh lại theo hạn mới.

    `generate_default_reminders` idempotent theo milestone nên nếu chỉ gọi lại
    không, mốc cũ còn `scheduled` sẽ chặn mốc mới — giờ nhắc vẫn trỏ về hạn
    cũ dù task đã đổi ngày (rủi ro do Antigravity bắt ở review matrix).
    Chỉ đụng kind=task_due: conflict/calendar notice là quan sát tại thời điểm
    chạy, không phải hẹn tương lai, để nguyên.
    """
    db.execute(
        update(Reminder)
        .where(
            Reminder.task_id == task.id,
            Reminder.kind == "task_due",
            Reminder.status == "scheduled",
        )
        .values(status="cancelled", dismiss_reason="due_at_rescheduled")
    )
    db.flush()
    return generate_default_reminders(db, task)


def generate_proposed_notice(db: Session, task: Task, *, now: datetime | None = None) -> Reminder | None:
    """Task mới ở trạng thái 'proposed' -> 1 thông báo ngay (kind=task_proposed).

    Idempotent theo task_id: pipeline resync không tạo thông báo trùng cho
    cùng 1 task (persist_node upsert task đã tồn tại mỗi lần sync lại).
    """
    now = now or datetime.now(UTC)
    existing = db.execute(
        select(Reminder).where(Reminder.task_id == task.id, Reminder.kind == "task_proposed")
    ).scalar_one_or_none()
    if existing is not None:
        return None
    reminder = Reminder(
        task_id=task.id, user_id=task.user_id, kind="task_proposed", milestone="proposed", scheduled_at=now
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def _calendar_change_key(event_id: str, changed_at: datetime) -> str:
    """Khoá dedupe cho một lần đổi cụ thể của một sự kiện.

    Gộp cả mốc thay đổi vào khoá chứ không chỉ event_id: cùng một buổi bị dời
    hai lần trong hai ngày là hai tin khác nhau, người dùng phải biết cả hai.
    Băm vì `milestone` chỉ có String(32) mà event_id của Google thì dài.
    """
    raw = f"{event_id}|{changed_at.isoformat()}"
    return "cal-" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]


def generate_calendar_change_notice(
    db: Session,
    *,
    user_id: str,
    event_id: str,
    title: str,
    change: str,
    starts_at: datetime,
    previous_starts_at: datetime | None = None,
    deep_link: str | None = None,
    changed_at: datetime | None = None,
    now: datetime | None = None,
) -> Reminder | None:
    """Sự kiện lịch bị dời giờ hoặc bị huỷ ở nguồn -> 1 thông báo.

    Cơ chế lọc, theo thứ tự rẻ tiền trước: chỉ nhận `change` hợp lệ -> bỏ qua
    sự kiện đã trôi qua và sự kiện quá xa (`CALENDAR_CHANGE_HORIZON`) -> dedupe
    theo cặp (sự kiện, mốc thay đổi).

    Ba tầng lọc này là thứ giữ cho tính năng không thành máy phát rác. Google
    chạm vào metadata sự kiện khá thường xuyên, và báo mọi lần chạm là cách
    nhanh nhất khiến người dùng tắt thông báo — lúc đó ta mất luôn cả những tin
    thật sự quan trọng.

    Trả None khi không có gì đáng báo, để nơi gọi không phải tự đoán.
    """
    if change not in ("time_changed", "cancelled"):
        return None

    now = now or datetime.now(UTC)
    starts_at = _as_utc(starts_at)
    if starts_at < now or starts_at > now + CALENDAR_CHANGE_HORIZON:
        return None

    changed_at = _as_utc(changed_at or now)
    milestone = _calendar_change_key(event_id, changed_at)
    existing = db.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.kind == "calendar_changed",
            Reminder.milestone == milestone,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return None

    reminder = Reminder(
        task_id=None,
        user_id=user_id,
        kind="calendar_changed",
        milestone=milestone,
        scheduled_at=now,
        payload={
            "eventId": event_id,
            "title": title,
            "change": change,
            "startsAt": starts_at.isoformat(),
            "previousStartsAt": _as_utc(previous_starts_at).isoformat() if previous_starts_at else None,
            "deepLink": deep_link,
        },
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def detect_schedule_conflicts(db: Session, task: Task, *, now: datetime | None = None) -> list[Reminder]:
    """2 task CONFIRMED của cùng user cách nhau trong CONFLICT_SCHEDULE_WINDOW_MINUTES
    -> 1 thông báo conflict_schedule/cặp. Gọi lúc confirm_task (tasks.py).

    Dedupe theo cặp (task_id, related_task_id) không phân thứ tự — confirm cả
    2 task trong cặp không tạo 2 thông báo trùng ý.
    """
    if task.due_at is None:
        return []
    now = now or datetime.now(UTC)
    due_at = _as_utc(task.due_at)
    window = timedelta(minutes=CONFLICT_SCHEDULE_WINDOW_MINUTES)

    others = db.execute(
        select(Task).where(
            Task.user_id == task.user_id,
            Task.status == "confirmed",
            Task.id != task.id,
            Task.due_at.is_not(None),
            Task.due_at >= due_at - window,
            Task.due_at <= due_at + window,
        )
    ).scalars().all()

    created: list[Reminder] = []
    for other in others:
        pair_exists = db.execute(
            select(Reminder).where(
                Reminder.kind == "conflict_schedule",
                Reminder.status == "scheduled",
                Reminder.user_id == task.user_id,
                or_(
                    and_(Reminder.task_id == task.id, Reminder.related_task_id == other.id),
                    and_(Reminder.task_id == other.id, Reminder.related_task_id == task.id),
                ),
            )
        ).scalar_one_or_none()
        if pair_exists is not None:
            continue
        reminder = Reminder(
            task_id=task.id,
            related_task_id=other.id,
            user_id=task.user_id,
            kind="conflict_schedule",
            milestone="schedule",
            scheduled_at=now,
            payload={
                "otherTaskId": other.id,
                "otherTaskTitle": other.title,
                "otherDueAt": _as_utc(other.due_at).isoformat() if other.due_at else None,
            },
        )
        db.add(reminder)
        created.append(reminder)

    if created:
        db.commit()
        for reminder in created:
            db.refresh(reminder)
    return created


def _evidence_topic_key(topic: str) -> str:
    """milestone chỉ String(32) — dùng hash làm khoá dedupe theo topic thay vì
    lưu nguyên văn (có thể dài/chứa ký tự lạ từ nội dung tin nhắn thật)."""
    return "ev-" + hashlib.md5(topic.encode("utf-8")).hexdigest()[:20]


def generate_evidence_conflict_notices(
    db: Session, user_id: str, clusters: list[EvidenceCluster], *, now: datetime | None = None
) -> list[Reminder]:
    """Wire src/agents/briefing/evidence.py::fuse_and_rank() vào thông báo thật.

    cluster.conflict=True (2+ nguồn khác ngày cho cùng topic) -> 1 thông báo
    conflict_evidence, dedupe theo topic (chạy lại brief cùng topic không tạo
    thông báo trùng khi thông báo cũ còn `scheduled`).
    """
    now = now or datetime.now(UTC)
    created: list[Reminder] = []
    for cluster in clusters:
        if not cluster.conflict:
            continue
        topic_key = _evidence_topic_key(cluster.topic)
        existing = db.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.kind == "conflict_evidence",
                Reminder.milestone == topic_key,
                Reminder.status == "scheduled",
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        reminder = Reminder(
            task_id=None,
            user_id=user_id,
            kind="conflict_evidence",
            milestone=topic_key,
            scheduled_at=now,
            payload={
                "topic": cluster.topic,
                "items": [
                    {
                        "source": item.source,
                        "content": item.content[:300],
                        "dueAt": item.due_at.isoformat() if item.due_at else None,
                        "deepLink": None,
                    }
                    for item in cluster.items
                ],
            },
        )
        db.add(reminder)
        created.append(reminder)

    if created:
        db.commit()
        for reminder in created:
            db.refresh(reminder)
    return created


def build_daily_digest_payload(db: Session, user_id: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    due_soon = db.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == "confirmed",
            Task.due_at.is_not(None),
            Task.due_at >= now,
            Task.due_at <= now + timedelta(hours=24),
        )
        .order_by(Task.due_at)
    ).scalars().all()
    proposed_count = db.scalar(select(func.count(Task.id)).where(Task.user_id == user_id, Task.status == "proposed")) or 0
    return {
        "dueSoonCount": len(due_soon),
        "dueSoonTasks": [
            {"taskId": t.id, "title": t.title, "dueAt": _as_utc(t.due_at).isoformat()} for t in due_soon[:5]
        ],
        "dueSoonTruncated": max(0, len(due_soon) - 5),
        "proposedCount": proposed_count,
    }


def enqueue_due_daily_briefs(db: Session, *, now: datetime | None = None) -> int:
    """Sinh daily_brief cho user đã tự chọn giờ (`daily_brief_hour`), đúng giờ
    local hôm nay và chưa sinh trong ngày. Mặc định TẮT (`daily_brief_hour`
    NULL) — người dùng phải tự bật, cùng tinh thần auto_sync_enabled (ADR-011):
    hệ thống chủ động thay người dùng là thay đổi cần người dùng tự bật.
    """
    now = now or datetime.now(UTC)
    prefs = db.execute(
        select(NotificationPreference).where(NotificationPreference.daily_brief_hour.is_not(None))
    ).scalars().all()

    created = 0
    for pref in prefs:
        local_now = now.astimezone(ZoneInfo(pref.timezone))
        if local_now.hour != pref.daily_brief_hour:
            continue
        today_str = local_now.date().isoformat()
        if pref.daily_brief_last_date == today_str:
            continue
        payload = build_daily_digest_payload(db, pref.user_id, now)
        db.add(
            Reminder(
                task_id=None, user_id=pref.user_id, kind="daily_brief", milestone="digest", scheduled_at=now, payload=payload
            )
        )
        pref.daily_brief_last_date = today_str
        created += 1

    if created:
        db.commit()
    return created


def is_quiet_hours(dt: datetime, pref: NotificationPreference) -> bool:
    hour = dt.astimezone(ZoneInfo(pref.timezone)).hour
    start, end = pref.quiet_hours_start, pref.quiet_hours_end
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end  # khung qua nửa đêm, vd 22 -> 7


def defer_to_active_start(dt: datetime, pref: NotificationPreference) -> datetime:
    """Dời `dt` rơi vào giờ yên lặng tới đầu khung giờ hoạt động (ADR-007 mục 8)."""
    if not is_quiet_hours(dt, pref):
        return dt
    tz = ZoneInfo(pref.timezone)
    local = dt.astimezone(tz)
    active_start = local.replace(hour=pref.quiet_hours_end, minute=0, second=0, microsecond=0)
    if active_start <= local:
        active_start += timedelta(days=1)
    return active_start.astimezone(UTC)


def compute_priority(reminder: Reminder, task: Task | None, *, now: datetime) -> int:
    """Ưu tiên tính bằng luật (ADR-007 mục 5): càng gần hạn, signal nguồn càng
    mạnh thì điểm càng cao; càng bị bỏ qua nhiều lần thì điểm càng giảm. Mô
    hình không được đổi hàm này, chỉ được xếp lại trong cùng bậc điểm.

    conflict_evidence/daily_brief không gắn task -> điểm cố định theo kind.
    task_proposed không có "hạn" để tính urgency -> chỉ tính theo signal.
    """
    flat = _FLAT_PRIORITY_BY_KIND.get(reminder.kind)
    if flat is not None:
        return flat
    if task is None:
        return 100

    bonus = _KIND_URGENCY_BONUS.get(reminder.kind, 0)
    if task.due_at is None:
        return int(task.signal_strength * 100) - task.reminder_dismiss_count * 50 + bonus

    due_at = _as_utc(task.due_at)
    minutes_to_due = max((due_at - now).total_seconds() / 60, 0)
    urgency = max(0, 1440 - minutes_to_due)  # trong 24h tới hạn thì điểm tăng dần
    signal = task.signal_strength * 100
    dismiss_penalty = task.reminder_dismiss_count * 50
    return int(urgency + signal - dismiss_penalty) + bonus


@dataclass(frozen=True)
class NotificationTaskItem:
    kind: str
    title: str
    milestone: str
    task_id: int | None = None
    due_at: datetime | None = None
    evidence_deep_link: str | None = None
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationBundle:
    bundle_key: str
    scheduled_at: datetime
    reminder_ids: list[int]
    tasks: list[NotificationTaskItem]


def _first_evidence_deep_link(db: Session, task_id: int) -> str | None:
    row = db.execute(select(TaskEvidence).where(TaskEvidence.task_id == task_id).limit(1)).scalar_one_or_none()
    return row.deep_link if row else None


def _is_reminder_still_valid(reminder: Reminder, task: Task | None) -> bool:
    """Task đổi trạng thái sau khi thông báo được sinh (confirm/complete/cancel
    giữa chừng) thì thông báo cũ không còn đúng nữa — lọc ở đây thay vì dựa
    hẳn vào cancel_pending_reminders (chỗ nào quên gọi cũng không hiện sai)."""
    if reminder.kind in ("conflict_evidence", "daily_brief", "calendar_changed"):
        return True
    if reminder.kind == "task_proposed":
        if task is None:
            return False
        if task.status == "proposed":
            return True
        # Task agent tự gom và tự xác nhận luôn (reason auto_confirmed) vẫn
        # phải giao được thông báo "việc mới" — đó là cách user biết vừa có
        # gì được gom vào để xoá nếu sai. Task user tự duyệt tay từ proposed
        # thì thông báo cũ đã hết ý nghĩa, không hồi sinh.
        return task.status == "confirmed" and "auto_confirmed" in (task.reasons or [])
    return task is not None and task.status == "confirmed"


def _build_notification_task_item(db: Session, reminder: Reminder, task: Task | None) -> NotificationTaskItem | None:
    """None nếu thông báo không đủ dữ kiện để hiển thị an toàn (FR-097: có
    task/evidence thì phải mở được bằng chứng, không tự bịa link)."""
    if reminder.kind == "daily_brief":
        return NotificationTaskItem(
            kind="daily_brief",
            title=f"Tổng hợp hôm nay — {reminder.payload.get('dueSoonCount', 0)} việc sắp tới hạn",
            milestone=reminder.milestone,
            payload=reminder.payload,
        )
    if reminder.kind == "conflict_evidence":
        return NotificationTaskItem(
            kind="conflict_evidence",
            title=f"Nguồn tin không khớp: {reminder.payload.get('topic', '')}",
            milestone=reminder.milestone,
            payload=reminder.payload,
        )
    if reminder.kind == "calendar_changed":
        # Nói rõ chuyện gì đã xảy ra ngay ở tiêu đề. "Lịch có thay đổi" chung
        # chung buộc người dùng phải mở ra mới biết có cần quan tâm không.
        change_labels = {
            "cancelled": "bị huỷ",
            "details_changed": "đã cập nhật thông tin",
            "published": "đã được công bố",
            "time_changed": "đổi giờ",
        }
        label = change_labels.get(reminder.payload.get("change"), "có thay đổi")
        change_note = reminder.payload.get("changeNote")
        note_suffix = f" — {change_note[:160]}" if isinstance(change_note, str) and change_note.strip() else ""
        return NotificationTaskItem(
            kind="calendar_changed",
            title=f"{reminder.payload.get('title', 'Một sự kiện')} {label}{note_suffix}",
            milestone=reminder.milestone,
            evidence_deep_link=reminder.payload.get("deepLink"),
            payload=reminder.payload,
        )
    # task_due / task_proposed / conflict_schedule đều gắn 1 task cụ thể.
    if task is None:
        return None
    evidence_deep_link = _first_evidence_deep_link(db, task.id)
    if evidence_deep_link is None:
        # FR-097: không có bằng chứng để mở thì không hiển thị thông báo này.
        return None
    if reminder.kind == "conflict_schedule":
        title = f"{task.title} trùng giờ với \"{reminder.payload.get('otherTaskTitle', '')}\""
    else:
        title = task.title
    return NotificationTaskItem(
        kind=reminder.kind,
        title=title,
        milestone=reminder.milestone,
        task_id=task.id,
        due_at=_as_utc(task.due_at) if task.due_at else None,
        evidence_deep_link=evidence_deep_link,
        payload=reminder.payload,
    )


def get_due_notifications(
    db: Session,
    user_id: str,
    *,
    now: datetime | None = None,
    delivery_channel: str = "extension",
) -> list[NotificationBundle]:
    """FR-095/097: gộp thông báo cùng khung giờ thành 1, áp trần số thông
    báo/giờ và giờ yên lặng.

    KHÔNG đánh dấu đã giao ở đây — extension phải gọi `record_deliveries` sau
    khi thật sự tạo được OS notification, để chống giao trùng khi service
    worker khởi động lại giữa chừng (FR-091).
    """
    now = now or datetime.now(UTC)
    pref = get_or_create_preference(db, user_id)

    # Chặn ngay ở đây chứ không ở từng vòng giao: đây là cửa duy nhất mọi kênh
    # đi qua, nên tắt kênh ở một chỗ là tắt thật, không phụ thuộc kênh mới có
    # nhớ tự kiểm tra hay không. Thông báo không bị huỷ, chỉ là không đi lối
    # này — bật lại thì nó vẫn còn đó.
    if not is_channel_enabled(pref, delivery_channel):
        return []
    muted_kinds = set(pref.muted_kinds or ())

    if delivery_channel == "extension":
        delivered_reminder_ids = {
            row.reminder_id
            for row in db.execute(select(NotificationDelivery).where(NotificationDelivery.user_id == user_id)).scalars()
        }
    else:
        delivered_reminder_ids = {
            row.reminder_id
            for row in db.execute(
                select(ChannelNotificationDelivery).where(
                    ChannelNotificationDelivery.user_id == user_id,
                    ChannelNotificationDelivery.channel == delivery_channel,
                )
            ).scalars()
        }

    candidates = db.execute(
        select(Reminder, Task)
        .outerjoin(Task, Task.id == Reminder.task_id)
        .where(Reminder.user_id == user_id, Reminder.status == "scheduled")
    ).all()

    due: list[tuple[Reminder, Task | None]] = []
    for reminder, task in candidates:
        channels = reminder.payload.get("deliveryChannels") if isinstance(reminder.payload, dict) else None
        if channels is not None and delivery_channel not in channels:
            continue
        if delivery_channel == "email" and channels is None:
            continue
        if reminder.id in delivered_reminder_ids:
            continue
        if reminder.kind in muted_kinds:
            continue
        if not _is_reminder_still_valid(reminder, task):
            continue
        scheduled_at = defer_to_active_start(_as_utc(reminder.scheduled_at), pref)
        if scheduled_at > now:
            continue
        due.append((reminder, task))

    if not due:
        return []

    window_seconds = max(pref.batch_window_minutes, 1) * 60
    buckets: dict[int, list[tuple[Reminder, Task | None]]] = {}
    for reminder, task in due:
        bucket_key = int(_as_utc(reminder.scheduled_at).timestamp() // window_seconds)
        buckets.setdefault(bucket_key, []).append((reminder, task))

    bundle_priority = {
        key: max(compute_priority(reminder, task, now=now) for reminder, task in items)
        for key, items in buckets.items()
    }
    ordered_keys = sorted(buckets.keys(), key=lambda key: bundle_priority[key], reverse=True)

    one_hour_ago = now - timedelta(hours=1)
    if delivery_channel == "extension":
        recent_delivery_stmt = select(NotificationDelivery.id).where(
            NotificationDelivery.user_id == user_id, NotificationDelivery.delivered_at >= one_hour_ago
        )
    else:
        recent_delivery_stmt = select(ChannelNotificationDelivery.id).where(
            ChannelNotificationDelivery.user_id == user_id,
            ChannelNotificationDelivery.channel == delivery_channel,
            ChannelNotificationDelivery.delivered_at >= one_hour_ago,
        )
    recent_count = len(db.execute(recent_delivery_stmt).all())
    remaining_cap = max(pref.hourly_cap - recent_count, 0)
    if remaining_cap <= 0:
        return []

    bundles: list[NotificationBundle] = []
    for bucket_key in ordered_keys[:remaining_cap]:
        items = sorted(buckets[bucket_key], key=lambda pair: compute_priority(pair[0], pair[1], now=now), reverse=True)
        rendered: list[NotificationTaskItem] = []
        reminder_ids: list[int] = []
        for reminder, task in items:
            item = _build_notification_task_item(db, reminder, task)
            if item is None:
                continue
            rendered.append(item)
            reminder_ids.append(reminder.id)
        if not rendered:
            continue
        earliest = min(_as_utc(reminder.scheduled_at) for reminder, _ in items)
        bundles.append(
            NotificationBundle(
                bundle_key=f"batch-{bucket_key}", scheduled_at=earliest, reminder_ids=reminder_ids, tasks=rendered
            )
        )
    return bundles


@dataclass(frozen=True)
class NotificationFeedItem:
    """1 dòng cho Trung tâm thông báo (web) — bọc thêm reminder_id/scheduled_at/
    is_read quanh NotificationTaskItem, vì get_due_notifications gộp theo
    bundle còn feed này hiển thị phẳng, mới nhất trước."""

    reminder_id: int
    scheduled_at: datetime
    is_read: bool
    task: NotificationTaskItem


def list_notifications(
    db: Session,
    user_id: str,
    *,
    limit: int = 50,
    now: datetime | None = None,
) -> list[NotificationFeedItem]:
    """Trung tâm thông báo (web) — trả CẢ đã đọc lẫn chưa đọc, mới nhất
    trước. Khác get_due_notifications: cái đó chỉ trả thông báo CHƯA giao,
    có gộp bundle/áp trần/giờ yên lặng cho kênh push (extension). Ở đây
    người dùng tự mở trang nên không cần throttle, chỉ cần danh sách đầy đủ.

    "Đã đọc" = đã có NotificationDelivery — tái dùng đúng bảng delivery hiện
    có (record_deliveries), không thêm cột read_at riêng.
    """
    now = now or datetime.now(UTC)
    delivered_reminder_ids = {
        row.reminder_id
        for row in db.execute(select(NotificationDelivery).where(NotificationDelivery.user_id == user_id)).scalars()
    }

    candidates = db.execute(
        select(Reminder, Task)
        .outerjoin(Task, Task.id == Reminder.task_id)
        .where(Reminder.user_id == user_id, Reminder.status == "scheduled", Reminder.scheduled_at <= now)
        .order_by(Reminder.scheduled_at.desc())
        .limit(limit * 2)  # 1 phần bị lọc bởi _is_reminder_still_valid/thiếu evidence — nới biên cho đủ `limit` sau lọc
    ).all()

    feed: list[NotificationFeedItem] = []
    for reminder, task in candidates:
        if not _is_reminder_still_valid(reminder, task):
            continue
        item = _build_notification_task_item(db, reminder, task)
        if item is None:
            continue
        feed.append(
            NotificationFeedItem(
                reminder_id=reminder.id,
                scheduled_at=_as_utc(reminder.scheduled_at),
                is_read=reminder.id in delivered_reminder_ids,
                task=item,
            )
        )
        if len(feed) >= limit:
            break
    return feed


def record_deliveries(db: Session, user_id: str, reminder_ids: list[int]) -> list[int]:
    """Ghi nhận đã giao — idempotent: id đã ghi rồi thì không tạo dòng mới
    (FR-091: khởi động lại tiến trình nền không giao trùng)."""
    if not reminder_ids:
        return []
    already = {
        row.reminder_id
        for row in db.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.user_id == user_id, NotificationDelivery.reminder_id.in_(reminder_ids)
            )
        ).scalars()
    }
    newly = [reminder_id for reminder_id in reminder_ids if reminder_id not in already]
    for reminder_id in newly:
        db.add(NotificationDelivery(reminder_id=reminder_id, user_id=user_id))
    if newly:
        db.commit()
    return newly


def record_channel_deliveries(
    db: Session,
    user_id: str,
    reminder_ids: list[int],
    *,
    channel: str,
    provider_message_id: str | None = None,
) -> list[int]:
    """Receipt idempotent riêng từng kênh; không chặn delivery của extension."""
    if not reminder_ids:
        return []
    already = {
        row.reminder_id
        for row in db.execute(
            select(ChannelNotificationDelivery).where(
                ChannelNotificationDelivery.channel == channel,
                ChannelNotificationDelivery.user_id == user_id,
                ChannelNotificationDelivery.reminder_id.in_(reminder_ids),
            )
        ).scalars()
    }
    newly = [reminder_id for reminder_id in reminder_ids if reminder_id not in already]
    for reminder_id in newly:
        db.add(
            ChannelNotificationDelivery(
                channel=channel,
                reminder_id=reminder_id,
                user_id=user_id,
                provider_message_id=provider_message_id,
            )
        )
    if newly:
        db.commit()
    return newly


def snooze_reminder(db: Session, reminder: Reminder, *, minutes: int | None = None, now: datetime | None = None) -> Reminder:
    """FR-093: dời thời điểm giao thông báo, KHÔNG đổi trạng thái công việc.

    Xoá receipt cũ để reminder giao lại được ở mốc mới — không xoá thì
    `get_due_notifications` sẽ coi reminder này là đã giao vĩnh viễn.

    Xoá trên MỌI kênh chứ không riêng extension: "nhắc lại sau 15 phút" là ý
    định của người dùng về lời nhắc, không phải về cái máy họ đang cầm. Chỉ dọn
    bảng của extension thì bấm nhắc lại từ Telegram hay từ thông báo trình
    duyệt sẽ dời lịch xong mà không kênh nào giao lại — đúng cái người dùng vừa
    yêu cầu lại là cái không xảy ra.
    """
    now = now or datetime.now(UTC)
    delta = timedelta(minutes=minutes) if minutes else DEFAULT_SNOOZE
    reminder.scheduled_at = now + delta
    reminder.snooze_count += 1
    db.execute(delete(NotificationDelivery).where(NotificationDelivery.reminder_id == reminder.id))
    db.execute(
        delete(ChannelNotificationDelivery).where(ChannelNotificationDelivery.reminder_id == reminder.id)
    )
    db.commit()
    db.refresh(reminder)
    return reminder


def dismiss_reminder(db: Session, reminder: Reminder, *, reason: str) -> Reminder:
    """FR-092/096: chỉ tắt LỜI NHẮC/thông báo này, không đụng task.status. Lý
    do bỏ qua tăng `task.reminder_dismiss_count` (nếu có task gắn), làm giảm
    ưu tiên lần sau (mục 5)."""
    if reason not in DISMISS_REASONS:
        raise ValueError(f"Lý do bỏ qua không hợp lệ: {reason}")
    reminder.status = "cancelled"
    reminder.dismiss_reason = reason
    if reminder.task_id is not None:
        task = db.get(Task, reminder.task_id)
        if task is not None:
            task.reminder_dismiss_count += 1
    db.commit()
    db.refresh(reminder)
    return reminder


def cancel_pending_reminders(db: Session, task_id: int) -> None:
    """Task hoàn thành hoặc bị huỷ thì mọi thông báo còn treo gắn với nó
    (kể cả conflict_schedule mà nó là task còn lại trong cặp) cũng phải tắt —
    không thì extension vẫn nhắc một việc đã xong/đã huỷ."""
    db.execute(
        update(Reminder)
        .where(
            or_(Reminder.task_id == task_id, Reminder.related_task_id == task_id),
            Reminder.status == "scheduled",
        )
        .values(status="cancelled", dismiss_reason=_TASK_RESOLVED_REASON)
    )
    db.commit()
