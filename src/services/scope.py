"""Quyết định một user được đọc những nguồn nào trong lượt truy hồi này.

Tách riêng khỏi router để mọi đường vào agent đi qua đúng một chỗ. Thêm đường
mới mà quên đặt phạm vi thì công cụ tìm sẽ từ chối, chứ không âm thầm đọc kho
của tất cả mọi người.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.agents.tools.calendar_tool import reset_calendar_scope, set_calendar_scope
from src.agents.tools.core_tools import reset_search_scope, set_search_scope
from src.agents.tools.drive_search_tool import reset_drive_search_scope, set_drive_search_scope
from src.agents.tools.gmail_bridge_tool import reset_gmail_bridge_scope, set_gmail_bridge_scope
from src.agents.tools.gmail_tool import reset_gmail_scope, set_gmail_scope
from src.agents.tools.google_document_tool import reset_google_document_scope, set_google_document_scope
from src.agents.tools.jira_tool import reset_jira_scope, set_jira_scope
from src.agents.tools.plan_tool import reset_plan_scope, set_plan_scope
from src.agents.tools.planner_workspace_tool import reset_planner_workspace_scope, set_planner_workspace_scope
from src.agents.tools.productivity_tool import (
    reset_productivity_action_scope,
    set_productivity_action_scope,
)
from src.agents.tools.program_calendar_tool import (
    reset_program_calendar_scope,
    set_program_calendar_scope,
)
from src.agents.tools.program_information_tool import (
    reset_program_information_scope,
    set_program_information_scope,
)
from src.agents.tools.task_tool import reset_task_scope, set_task_scope
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.source_scope_access import SourceScopeAccess
from src.models.user import User
from src.services.llm_usage_scope import reset_llm_usage_user, set_llm_usage_user
from src.services.program_access import reconcile_program_access
from src.services.program_cohorts import resolve_program_cohort_slug

logger = logging.getLogger(__name__)


def apply_search_scope(
    user_id: str,
    db: Session,
    *,
    action_request_id: str = "",
    current_query: str = "",
    pending_action: dict | None = None,
) -> None:
    """Đặt phạm vi truy hồi cho user hiện tại.

    Không đặt gì cả nghĩa là bộ tool Discord sẽ từ chối tìm. Đó là trạng thái
    đúng khi chưa biết user được phép đọc nguồn nào — thà không trả lời được còn
    hơn trả lời bằng dữ liệu của người khác.
    """
    set_llm_usage_user(user_id)

    # Bảng tasks phân theo user_id nên phạm vi của nó là chính user này, đặt
    # trước mọi nhánh khác. Cờ demo không mở được chỗ này: "không giới hạn" với
    # tasks nghĩa là đọc việc của tất cả mọi người, không có nghĩa nào khác.
    if user_id:
        set_task_scope(user_id)
        set_plan_scope(user_id)
        set_planner_workspace_scope(user_id)
        set_calendar_scope(user_id)
        set_gmail_scope(user_id)
        set_gmail_bridge_scope(user_id)
        set_jira_scope(user_id)
        set_google_document_scope(user_id)
        set_drive_search_scope(user_id)
        set_productivity_action_scope(
            user_id,
            request_id=action_request_id,
            current_query=current_query,
            pending_action=pending_action,
        )
    else:
        reset_task_scope()
        reset_plan_scope()
        reset_planner_workspace_scope()
        reset_calendar_scope()
        reset_gmail_scope()
        reset_gmail_bridge_scope()
        reset_jira_scope()
        reset_google_document_scope()
        reset_drive_search_scope()
        reset_productivity_action_scope()

    now = datetime.now(UTC)
    # Mức A/B/C tính lại ở đây rồi mới truyền xuống tool lịch chương trình. Đọc
    # cột trong DB thì tài khoản cũ vẫn giữ mức sai cho tới lần đăng nhập sau,
    # còn hàm này tự chữa (ADR-004, ADR-008).
    if user_id:
        program_level = reconcile_program_access(db, user_id)
        user = db.get(User, int(user_id))
        if user is None:
            raise RuntimeError(f"Không tìm thấy user {user_id} khi đặt program scope.")
        effective_cohort = resolve_program_cohort_slug(user.program_cohort_slug)
        set_program_calendar_scope(program_level, effective_cohort)
        set_program_information_scope(program_level, effective_cohort)
    else:
        reset_program_calendar_scope()
        reset_program_information_scope()
    scope_ids = list(
        db.scalars(
            select(SourceScopeAccess.scope_id)
            .join(SourceScope, SourceScope.id == SourceScopeAccess.scope_id)
            .where(
                SourceScopeAccess.user_id == user_id,
                SourceScopeAccess.status == "confirmed",
                SourceScopeAccess.granted_at <= now,
                or_(SourceScopeAccess.valid_to.is_(None), SourceScopeAccess.valid_to > now),
                SourceScope.provider == "discord",
            )
        )
    )
    discord_author_external_id = db.scalar(
        select(Connection.provider_user_id)
        .where(
            Connection.user_id == user_id,
            Connection.provider == "discord",
            Connection.status.notin_(["error", "disconnected"]),
        )
        .limit(1)
    )

    # [] is a deliberate empty permission set. It must not become None, which
    # means unbounded access inside the retrieval helper.
    set_search_scope(
        sorted(set(scope_ids)),
        author_external_id=discord_author_external_id,
    )
    logger.info("Applied %d source scopes for user %s", len(scope_ids), user_id)


def reset_agent_scope() -> None:
    """Xóa toàn bộ scope ContextVar sau mỗi request agent."""
    reset_llm_usage_user()
    reset_search_scope()
    reset_task_scope()
    reset_plan_scope()
    reset_planner_workspace_scope()
    reset_calendar_scope()
    reset_gmail_scope()
    reset_gmail_bridge_scope()
    reset_jira_scope()
    reset_google_document_scope()
    reset_drive_search_scope()
    reset_productivity_action_scope()
    reset_program_calendar_scope()
    reset_program_information_scope()
