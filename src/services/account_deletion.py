"""Xoá vĩnh viễn 1 tài khoản và toàn bộ dữ liệu cá nhân của họ.

Vì sao cần file riêng thay vì `db.delete(user)`: hầu hết bảng lưu `user_id`
dạng String rời (khớp JWT sub), KHÔNG đặt ForeignKey tới `users.id` — xem quy
ước ghi trong `src/models/message.py`/`connection.py`. Không có ForeignKey thì
không có `ondelete=CASCADE`, nên xoá thẳng User để lại rác ở ~20 bảng khác.
Chỉ 5 bảng đặt FK thật tới `users.id` (brief, run, user_profile_memories,
user_memories, user_memory_evidence) — các bảng đó tự cascade, không liệt kê
lại ở đây.

Cố tình KHÔNG xoá `audit_events` — bảng này không có cột `user_id` (tham
chiếu qua `object_id` chung), và theo đúng thiết kế ở `src/models/telemetry.py`
đây là "bằng chứng vận hành" phải giữ lại, khác `telemetry_events` (số liệu
sản phẩm, xoá được theo thời hạn lưu mà không mất bằng chứng).
"""

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.models.app_rating import AppRating
from src.models.calendar_event import CalendarEvent, CalendarOperation
from src.models.channel_delivery import ChannelNotificationDelivery, TelegramLinkIntent
from src.models.cluster import Cluster, ClusterMessage
from src.models.connection import Connection
from src.models.conversation import Conversation
from src.models.llm_usage import LLMUsageEvent
from src.models.meeting_note import MeetingNote
from src.models.message import Message
from src.models.notification_preference import NotificationPreference
from src.models.program_calendar_sync import ProgramCalendarSync
from src.models.program_information import ProgramInformationRequest
from src.models.push_subscription import PushSubscription
from src.models.recording_quota import RecordingQuotaSlot
from src.models.reminder import Reminder
from src.models.routine import Routine, RoutineRun
from src.models.source_scope_access import SourceScopeAccess
from src.models.sync_cursor import SyncCursor
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.models.telemetry import TelemetryEvent
from src.models.user import User
from src.services.connections import revoke_connection_tokens

logger = logging.getLogger(__name__)

# Bảng không có FK tới users.id -> phải tự xoá theo user_id. Con của những
# bảng này (task_evidence, cluster_messages, notification_deliveries,
# channel_notification_deliveries, meeting_action_items, conversation_messages,
# schedule_conflicts) đều có FK ondelete=CASCADE trỏ về đúng 1 bảng trong danh
# sách này, nên tự biến mất theo, không cần liệt kê riêng.
_TABLES_WITHOUT_USER_FK = (
    Task,
    Cluster,
    Message,
    Reminder,
    Conversation,
    MeetingNote,
    Routine,
    RoutineRun,
    CalendarEvent,
    CalendarOperation,
    AppRating,
    PushSubscription,
    RecordingQuotaSlot,
    SourceScopeAccess,
    SyncCursor,
    NotificationPreference,
    ProgramCalendarSync,
    TelemetryEvent,
    LLMUsageEvent,
    TelegramLinkIntent,
    ChannelNotificationDelivery,
)


async def delete_user_account(db: Session, user_id: str) -> None:
    """Xoá toàn bộ dữ liệu của `user_id` rồi xoá chính hàng User, trong 1
    transaction — thất bại giữa chừng thì rollback hết, không để lại xoá dở."""
    numeric_user_id = int(user_id)

    connections = db.execute(select(Connection).where(Connection.user_id == user_id)).scalars().all()
    for connection in connections:
        await revoke_connection_tokens(connection)

    # Không phụ thuộc PRAGMA foreign_keys của SQLite hay cấu hình cascade của
    # từng database: xoá rõ các bảng con trước khi xoá task/cluster/message.
    db.execute(
        delete(TaskEvidence).where(TaskEvidence.task_id.in_(select(Task.id).where(Task.user_id == user_id)))
    )
    db.execute(
        delete(ClusterMessage).where(
            ClusterMessage.cluster_id.in_(select(Cluster.id).where(Cluster.user_id == user_id))
            | ClusterMessage.message_id.in_(select(Message.id).where(Message.user_id == user_id))
        )
    )

    for model in _TABLES_WITHOUT_USER_FK:
        db.execute(delete(model).where(model.user_id == user_id))

    db.execute(delete(Connection).where(Connection.user_id == user_id))
    # Câu hỏi được người dùng chủ động chuyển cho đội ngũ dùng FK thật tới
    # users.id. Xoá rõ ràng để quyền xoá tài khoản không bị chặn bởi FK.
    db.execute(delete(ProgramInformationRequest).where(ProgramInformationRequest.requester_id == numeric_user_id))

    user = db.get(User, numeric_user_id)
    if user is not None:
        db.delete(user)

    db.commit()
    logger.info("Đã xoá tài khoản user_id=%s và toàn bộ dữ liệu liên quan.", user_id)
