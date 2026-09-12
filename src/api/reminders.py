from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.db import get_db
from src.models.reminder import Reminder
from src.models.schemas import (
    DismissReminderRequest,
    DueNotificationsResponse,
    NotificationBundleResponse,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationTaskResponse,
    RecordDeliveriesRequest,
    RecordDeliveriesResponse,
    ReminderListResponse,
    ReminderResponse,
    SnoozeReminderRequest,
    UpdateNotificationPreferenceRequest,
)
from src.services import reminders as reminders_service

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _to_response(row: Reminder) -> ReminderResponse:
    return ReminderResponse.model_validate(row, from_attributes=True)


def _get_owned_reminder(db: Session, reminder_id: int, user_id: str) -> Reminder:
    row = db.execute(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lời nhắc.")
    return row


@router.get("", response_model=ReminderListResponse)
def list_reminders(
    task_id: int | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReminderListResponse:
    stmt = select(Reminder).where(Reminder.user_id == user_id)
    if task_id is not None:
        stmt = stmt.where(Reminder.task_id == task_id)
    rows = db.execute(stmt.order_by(Reminder.scheduled_at)).scalars().all()
    return ReminderListResponse(reminders=[_to_response(row) for row in rows])


@router.get("/due", response_model=DueNotificationsResponse)
def get_due_reminders(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DueNotificationsResponse:
    """Endpoint đọc nhẹ cho extension nạp lịch nhắc qua chrome.alarms (ADR-007
    mục 9) — không dựng hạ tầng push phía máy chủ trong P0."""
    bundles = reminders_service.get_due_notifications(db, user_id)
    return DueNotificationsResponse(
        notifications=[
            NotificationBundleResponse(
                bundle_key=bundle.bundle_key,
                scheduled_at=bundle.scheduled_at,
                reminder_ids=bundle.reminder_ids,
                tasks=[
                    NotificationTaskResponse(
                        kind=item.kind,
                        task_id=item.task_id,
                        title=item.title,
                        due_at=item.due_at,
                        milestone=item.milestone,
                        evidence_deep_link=item.evidence_deep_link,
                        payload=item.payload,
                    )
                    for item in bundle.tasks
                ],
            )
            for bundle in bundles
        ]
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Trung tâm thông báo (web) — trả cả đã đọc lẫn chưa đọc, mới nhất
    trước. Khác `/due` (chỉ trả thông báo CHƯA giao, dùng cho push extension)."""
    feed = reminders_service.list_notifications(db, user_id, limit=limit)
    return NotificationListResponse(
        notifications=[
            NotificationItemResponse(
                reminder_id=entry.reminder_id,
                kind=entry.task.kind,
                title=entry.task.title,
                milestone=entry.task.milestone,
                task_id=entry.task.task_id,
                due_at=entry.task.due_at,
                scheduled_at=entry.scheduled_at,
                evidence_deep_link=entry.task.evidence_deep_link,
                payload=entry.task.payload,
                is_read=entry.is_read,
            )
            for entry in feed
        ]
    )


@router.post("/deliveries", response_model=RecordDeliveriesResponse)
def record_deliveries(
    body: RecordDeliveriesRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RecordDeliveriesResponse:
    """Extension gọi ngay sau khi thật sự tạo được OS notification — chống
    giao trùng khi service worker khởi động lại giữa chừng (FR-091)."""
    recorded = reminders_service.record_deliveries(db, user_id, body.reminder_ids)
    return RecordDeliveriesResponse(recorded=recorded)


@router.post("/{reminder_id}/snooze", response_model=ReminderResponse)
def snooze_reminder(
    reminder_id: int,
    body: SnoozeReminderRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReminderResponse:
    reminder = _get_owned_reminder(db, reminder_id, user_id)
    if reminder.status != "scheduled":
        raise HTTPException(
            status_code=409, detail=f"Lời nhắc đang ở trạng thái '{reminder.status}', không nhắc lại được."
        )
    updated = reminders_service.snooze_reminder(db, reminder, minutes=body.minutes)
    return _to_response(updated)


@router.post("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(
    reminder_id: int,
    body: DismissReminderRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReminderResponse:
    reminder = _get_owned_reminder(db, reminder_id, user_id)
    if reminder.status != "scheduled":
        raise HTTPException(
            status_code=409, detail=f"Lời nhắc đang ở trạng thái '{reminder.status}', không bỏ qua được."
        )
    updated = reminders_service.dismiss_reminder(db, reminder, reason=body.reason)
    return _to_response(updated)


def _to_preference_response(pref) -> NotificationPreferenceResponse:
    """Dòng cấu hình tạo trước khi có cột `muted_kinds` đọc lên là NULL, mà
    schema đòi một danh sách — quy về danh sách rỗng ngay tại biên thay vì để
    người dùng cũ nhận 500 ở một endpoint chỉ đọc."""
    return NotificationPreferenceResponse(
        timezone=pref.timezone,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
        hourly_cap=pref.hourly_cap,
        batch_window_minutes=pref.batch_window_minutes,
        daily_brief_hour=pref.daily_brief_hour,
        extension_enabled=bool(pref.extension_enabled),
        telegram_enabled=bool(pref.telegram_enabled),
        web_push_enabled=bool(pref.web_push_enabled),
        muted_kinds=list(pref.muted_kinds or []),
    )


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> NotificationPreferenceResponse:
    pref = reminders_service.get_or_create_preference(db, user_id)
    return _to_preference_response(pref)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    body: UpdateNotificationPreferenceRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> NotificationPreferenceResponse:
    """Một chỗ duy nhất để chỉnh mọi thứ quyết định người dùng bị làm phiền
    tới mức nào: múi giờ, giờ yên lặng, trần mỗi giờ, cửa sổ gộp, kênh nào còn
    bật, loại nào đã tắt, và giờ nhận daily brief.

    Daily brief mặc định TẮT và chỉ bật khi gọi endpoint này với
    `dailyBriefHour` (tinh thần ADR-011: hệ thống chủ động thay người dùng thì
    phải do người dùng tự bật). Các kênh thì ngược lại — mặc định BẬT, vì bật
    kênh đã là một hành động tường minh trước đó (cài extension, nối Telegram,
    cho phép thông báo trình duyệt).
    """
    pref = reminders_service.get_or_create_preference(db, user_id)
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError as exc:
            raise HTTPException(status_code=422, detail=f"Múi giờ không hợp lệ: {body.timezone}") from exc
        pref.timezone = body.timezone
    if body.disable_daily_brief:
        pref.daily_brief_hour = None
    elif body.daily_brief_hour is not None:
        pref.daily_brief_hour = body.daily_brief_hour

    # Gán từng field khi và chỉ khi client gửi nó — PATCH ở đây là "sửa phần
    # đã nêu", nên một giao diện chỉ đổi một toggle không được vô tình ghi đè
    # các giá trị nó đọc từ lúc mở trang.
    for field in (
        "quiet_hours_start",
        "quiet_hours_end",
        "hourly_cap",
        "batch_window_minutes",
        "extension_enabled",
        "telegram_enabled",
        "web_push_enabled",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(pref, field, value)
    if body.muted_kinds is not None:
        # Bỏ trùng nhưng giữ thứ tự client gửi để so sánh trong test và log dễ đọc.
        pref.muted_kinds = list(dict.fromkeys(body.muted_kinds))

    db.commit()
    db.refresh(pref)
    return _to_preference_response(pref)
