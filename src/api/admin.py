"""Endpoint cho admin portal — chỉ số liệu tổng hợp và trạng thái vận hành.

Ranh giới của cả file này nằm ở hai chỗ trong tài liệu đã duyệt:

PRD §4.4 loại "bảng quản trị theo dõi chi tiết hành vi cá nhân" khỏi phạm vi sáu
tuần, và PRD §5 ghi người vận hành chỉ được "xem trạng thái tổng hợp và nhật ký
đã loại thông tin nhạy cảm; không mặc định được xem nội dung cá nhân gốc".

Nên ở đây có: đếm, trạng thái đồng bộ, tỷ lệ lỗi, nhật ký thay đổi. Không có:
nội dung email hay tin nhắn, câu hỏi người dùng đã đặt, câu trả lời đã nhận,
tiêu đề việc cần làm, bản tóm lược. Thêm endpoint mới mà chạm tới nhóm sau là
material change về quyền riêng tư — cần ADR chứ không sửa thẳng ở đây.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from src.api.deps import require_admin
from src.db import get_db
from src.models.admin_schemas import (
    AdminAppRatingRow,
    AdminAppRatingSummary,
    AdminAuditListResponse,
    AdminAuditRow,
    AdminConnectionRow,
    AdminFeedbackBreakdown,
    AdminOverviewResponse,
    AdminProgramAccessUpdateRequest,
    AdminRoleBreakdown,
    AdminRunListResponse,
    AdminRunRow,
    AdminSourceHealth,
    AdminSourceScopeGrantRequest,
    AdminSourceScopeGrantResponse,
    AdminSourceScopeRow,
    AdminSourcesResponse,
    AdminTelemetryCount,
    AdminTelemetryResponse,
    AdminUserListResponse,
    AdminUserRow,
    AdminUserUpdateRequest,
)
from src.models.app_rating import AppRating
from src.models.brief import Brief
from src.models.connection import Connection
from src.models.evidence import SourceScope
from src.models.run import Run
from src.models.source_scope_access import SourceScopeAccess
from src.models.task import Task
from src.models.telemetry import AuditEvent, TelemetryEvent
from src.models.user import User
from src.services.program_access import set_program_access
from src.services.program_cohorts import normalize_program_cohort_slug
from src.services.telemetry import emit_audit

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Trạng thái Connection nào tính là hỏng. Danh sách chứ không phải "khác
# connected", vì trạng thái chờ đồng bộ lần đầu là bình thường, không phải lỗi.
_FAILED_CONNECTION_STATUSES = ("error", "revoked", "expired")
_SYNCING_CONNECTION_STATUSES = ("connected_pending_sync", "syncing")


@router.get("/source-scopes", response_model=list[AdminSourceScopeRow])
def list_source_scopes(
    db: Session = Depends(get_db),
) -> list[AdminSourceScopeRow]:
    """List scope metadata only; never returns source content."""
    rows = db.scalars(select(SourceScope).order_by(SourceScope.provider, SourceScope.name, SourceScope.id)).all()
    return [
        AdminSourceScopeRow(
            id=row.id,
            provider=row.provider,
            external_id=row.external_id,
            name=row.name,
            tier=row.tier,
        )
        for row in rows
    ]


@router.put("/users/{user_id}/source-scopes", response_model=AdminSourceScopeGrantResponse)
def replace_user_source_scopes(
    user_id: int,
    payload: AdminSourceScopeGrantRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSourceScopeGrantResponse:
    """Replace a user's active source-scope grants.

    Revocation is recorded, not deleted, so a bad grant can be audited. The
    endpoint changes access only; it does not expose messages or embeddings.
    """
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy user.")

    requested = sorted(set(payload.scope_ids))
    existing_scopes = (
        set(db.scalars(select(SourceScope.id).where(SourceScope.id.in_(requested))).all()) if requested else set()
    )
    missing = sorted(set(requested) - existing_scopes)
    if missing:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy source scope: {missing}.")

    now = datetime.now(UTC)
    active = db.scalars(
        select(SourceScopeAccess).where(
            SourceScopeAccess.user_id == str(user_id),
            SourceScopeAccess.status == "confirmed",
            SourceScopeAccess.granted_at <= now,
            or_(SourceScopeAccess.valid_to.is_(None), SourceScopeAccess.valid_to > now),
        )
    ).all()
    requested_set = set(requested)
    for grant in active:
        if grant.scope_id not in requested_set:
            grant.status = "revoked"
            grant.valid_to = now

    active_scope_ids = {grant.scope_id for grant in active if grant.scope_id in requested_set}
    for scope_id in requested:
        if scope_id not in active_scope_ids:
            db.add(
                SourceScopeAccess(
                    user_id=str(user_id),
                    scope_id=scope_id,
                    status="confirmed",
                    granted_by=str(admin.id),
                    granted_at=now,
                )
            )
    emit_audit(
        db,
        action="source_scope_access_replaced",
        object_type="user",
        object_id=str(user_id),
        actor_type="admin",
        actor_id=str(admin.id),
        scope_count=len(requested),
    )
    db.commit()
    return AdminSourceScopeGrantResponse(user_id=str(user_id), scope_ids=requested)


def _count(db: Session, statement: Select) -> int:
    """Đếm số dòng của một truy vấn, trả 0 thay vì None khi bảng rỗng."""
    return db.execute(select(func.count()).select_from(statement.subquery())).scalar() or 0


def _window_start(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


@router.get("/overview", response_model=AdminOverviewResponse)
def overview(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    """Số liệu tổng hợp toàn hệ thống cho trang chủ admin."""
    since = _window_start(days)

    total_users = _count(db, select(User.id))
    inactive_users = _count(db, select(User.id).where(User.is_active.is_(False)))

    role_rows = db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all()
    role_counts = {str(role): int(count) for role, count in role_rows}

    # "Đang dùng" tính theo dấu vết vận hành trong cửa sổ, không theo lần đăng
    # nhập cuối — hệ thống chưa ghi lần đăng nhập, mà đoán bừa thì số liệu sai
    # mà không ai biết. Một người có run mới hoặc nguồn vừa đồng bộ là đang dùng.
    users_with_recent_run = select(Run.user_id).where(Run.created_at >= since).distinct()
    active_user_ids = {str(uid) for (uid,) in db.execute(users_with_recent_run).all()}
    recent_sync = select(Connection.user_id).where(Connection.last_synced_at >= since).distinct()
    active_user_ids |= {str(uid) for (uid,) in db.execute(recent_sync).all()}

    total_connections = _count(db, select(Connection.id))
    failed_connections = _count(db, select(Connection.id).where(Connection.status.in_(_FAILED_CONNECTION_STATUSES)))
    health = 100.0
    if total_connections:
        health = round((total_connections - failed_connections) / total_connections * 100, 1)

    runs_window = select(Run.id).where(Run.created_at >= since)
    runs_total = _count(db, runs_window)
    runs_succeeded = _count(db, runs_window.where(Run.status == "succeeded"))
    runs_failed = _count(db, runs_window.where(Run.status == "failed"))
    runs_running = _count(db, select(Run.id).where(Run.status.in_(("queued", "running"))))

    briefs_generated = _count(db, select(Brief.id).where(Brief.created_at >= since))
    tasks_proposed = _count(db, select(Task.id).where(Task.status == "proposed"))
    tasks_confirmed = _count(db, select(Task.id).where(Task.status == "confirmed"))
    # "Mâu thuẫn" ở đây là việc mà pipeline đánh dấu thời gian chưa rõ và người
    # dùng chưa xử lý — đó là tín hiệu duy nhất về mâu thuẫn đang có trong DB.
    # Chưa có model conflict riêng, nên đừng đọc con số này như số vụ mâu thuẫn
    # giữa hai nguồn.
    open_conflicts = _count(db, select(Task.id).where(Task.ambiguous.is_(True), Task.status == "proposed"))

    feedback_rows = db.execute(
        select(
            TelemetryEvent.attributes["verdict"].as_string(),
            func.count(TelemetryEvent.id),
        )
        .where(TelemetryEvent.name == "answer_feedback", TelemetryEvent.created_at >= since)
        .group_by(TelemetryEvent.attributes["verdict"].as_string())
    ).all()
    feedback_counts = {str(verdict): int(count) for verdict, count in feedback_rows if verdict}

    return AdminOverviewResponse(
        total_users=total_users,
        active_users=len(active_user_ids),
        inactive_users=inactive_users,
        roles=AdminRoleBreakdown(
            participant=role_counts.get("participant", 0),
            mentor=role_counts.get("mentor", 0),
            admin=role_counts.get("admin", 0),
        ),
        total_connections=total_connections,
        failed_connections=failed_connections,
        source_health_percent=health,
        runs_total=runs_total,
        runs_succeeded=runs_succeeded,
        runs_failed=runs_failed,
        runs_running=runs_running,
        briefs_generated=briefs_generated,
        tasks_proposed=tasks_proposed,
        tasks_confirmed=tasks_confirmed,
        open_conflicts=open_conflicts,
        feedback_total=sum(feedback_counts.values()),
        feedback_helpful=feedback_counts.get("helpful", 0),
        window_days=days,
        generated_at=datetime.now(UTC),
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    search: str = Query(default="", max_length=255),
    role: str = Query(default="", max_length=16),
    program_access_level: Literal["A", "B", "C"] | None = Query(
        default=None,
        alias="programAccessLevel",
        description="Lọc theo phân loại quyền truy cập chương trình hiện tại.",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """Danh sách tài khoản kèm số nguồn và số run — không kèm nội dung của họ."""
    statement = select(User)
    if search:
        pattern = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(func.lower(User.email).like(pattern), func.lower(User.display_name).like(pattern))
        )
    if role:
        statement = statement.where(User.role == role)
    if program_access_level is not None:
        statement = statement.where(User.program_access_level == program_access_level)

    total = _count(db, statement)
    rows = db.execute(statement.order_by(User.created_at.desc()).limit(limit).offset(offset))
    users = list(rows.scalars().all())

    # Đếm gộp một lần cho cả trang thay vì mỗi user một truy vấn — trang 200
    # dòng mà đếm lẻ là 400 lượt round-trip.
    user_ids = [u.id for u in users]
    connection_counts: dict[str, int] = {}
    run_counts: dict[str, int] = {}
    if user_ids:
        # Connection.user_id lưu dạng chuỗi còn Run.user_id là khoá ngoại số —
        # hai bảng lệch kiểu từ trước, nên phải so bằng đúng kiểu của từng bảng.
        conn_rows = db.execute(
            select(Connection.user_id, func.count(Connection.id))
            .where(Connection.user_id.in_([str(i) for i in user_ids]))
            .group_by(Connection.user_id)
        ).all()
        connection_counts = {str(uid): int(count) for uid, count in conn_rows}
        run_rows = db.execute(
            select(Run.user_id, func.count(Run.id)).where(Run.user_id.in_(user_ids)).group_by(Run.user_id)
        ).all()
        run_counts = {str(uid): int(count) for uid, count in run_rows}

    items = [
        AdminUserRow(
            id=str(u.id),
            email=u.email,
            display_name=u.display_name or "",
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            last_synced_at=u.last_synced_at,
            connection_count=connection_counts.get(str(u.id), 0),
            run_count=run_counts.get(str(u.id), 0),
            program_access_level=u.program_access_level,
            program_cohort_slug=normalize_program_cohort_slug(u.program_cohort_slug) if u.program_cohort_slug else None,
        )
        for u in users
    ]
    return AdminUserListResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/users/{user_id}", response_model=AdminUserRow)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminUserRow:
    """Đổi role hoặc khoá/mở tài khoản, ghi lại vào audit log theo FR-070."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User không tồn tại.")
    if payload.role is None and payload.is_active is None and payload.program_cohort_slug is None:
        raise HTTPException(status_code=422, detail="Không có trường nào để cập nhật.")

    # Tự hạ quyền hoặc tự khoá mình là cách nhanh nhất để không còn ai vào được
    # /admin — phải sửa bằng script trên máy chủ mới gỡ ra được.
    if target.id == actor.id:
        if payload.role is not None and payload.role != actor.role:
            raise HTTPException(status_code=400, detail="Không tự đổi role của chính mình được.")
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="Không tự khoá tài khoản của mình được.")

    before = {"role": target.role, "is_active": target.is_active, "program_cohort_slug": target.program_cohort_slug}
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.program_cohort_slug is not None:
        target.program_cohort_slug = payload.program_cohort_slug.strip() or None

    # Không cần chốt "phải còn ít nhất một admin" ở đây: người gọi luôn là admin
    # và không phải là target (tự đổi đã chặn ở trên), nên sau thao tác luôn còn
    # ít nhất chính họ.
    emit_audit(
        db,
        action="admin_user_updated",
        object_type="user",
        object_id=str(target.id),
        actor_type="admin",
        actor_id=str(actor.id),
        before=before,
        after={"role": target.role, "is_active": target.is_active, "program_cohort_slug": target.program_cohort_slug},
    )
    db.commit()
    db.refresh(target)

    return AdminUserRow(
        id=str(target.id),
        email=target.email,
        display_name=target.display_name or "",
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        last_synced_at=target.last_synced_at,
        program_access_level=target.program_access_level,
        program_cohort_slug=(
            normalize_program_cohort_slug(target.program_cohort_slug) if target.program_cohort_slug else None
        ),
    )


@router.patch("/users/{user_id}/program-access", response_model=AdminUserRow)
def update_program_access(
    user_id: int,
    payload: AdminProgramAccessUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> AdminUserRow:
    """Manually confirm/revoke program access after external validation."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User không tồn tại.")
    before = target.program_access_level
    set_program_access(db, str(target.id), payload.level, granted_by=str(actor.id))
    emit_audit(
        db,
        action="program_access_updated",
        object_type="user",
        object_id=str(target.id),
        actor_type="admin",
        actor_id=str(actor.id),
        before=before,
        after=payload.level,
    )
    db.commit()
    db.refresh(target)
    return AdminUserRow(
        id=str(target.id),
        email=target.email,
        display_name=target.display_name or "",
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        last_synced_at=target.last_synced_at,
        program_access_level=target.program_access_level,
        program_cohort_slug=(
            normalize_program_cohort_slug(target.program_cohort_slug) if target.program_cohort_slug else None
        ),
    )


@router.get("/sources", response_model=AdminSourcesResponse)
def list_sources(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> AdminSourcesResponse:
    """Sức khoẻ đồng bộ theo từng nhà cung cấp, kèm các kết nối đang lỗi."""
    provider_rows = db.execute(
        select(
            Connection.provider,
            func.count(Connection.id),
            func.max(Connection.last_synced_at),
        ).group_by(Connection.provider)
    ).all()

    providers = []
    for provider, total, last_synced in provider_rows:
        failed = _count(
            db,
            select(Connection.id).where(
                Connection.provider == provider,
                Connection.status.in_(_FAILED_CONNECTION_STATUSES),
            ),
        )
        syncing = _count(
            db,
            select(Connection.id).where(
                Connection.provider == provider,
                Connection.status.in_(_SYNCING_CONNECTION_STATUSES),
            ),
        )
        providers.append(
            AdminSourceHealth(
                provider=str(provider),
                total=int(total),
                connected=int(total) - failed - syncing,
                syncing=syncing,
                failed=failed,
                last_synced_at=last_synced,
            )
        )

    # Kết nối lỗi lên đầu: đó là thứ admin mở trang này để tìm.
    rows = list(
        db.execute(
            select(Connection)
            .order_by(
                Connection.status.in_(_FAILED_CONNECTION_STATUSES).desc(),
                Connection.connected_at.desc(),
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )

    # Không join thẳng users: Connection.user_id là chuỗi còn User.id là số, mà
    # ép kiểu trong SQL thì gặp một user_id không phải số là cả truy vấn ném lỗi
    # thay vì bỏ qua dòng đó. Tra riêng rồi ghép trong Python thì dòng lạ chỉ
    # mất phần email.
    numeric_ids = {int(c.user_id) for c in rows if str(c.user_id).isdigit()}
    emails: dict[str, str] = {}
    if numeric_ids:
        emails = {
            str(uid): email
            for uid, email in db.execute(select(User.id, User.email).where(User.id.in_(numeric_ids))).all()
        }

    connections = [
        AdminConnectionRow(
            id=conn.id,
            user_id=str(conn.user_id),
            user_email=emails.get(str(conn.user_id), ""),
            provider=conn.provider,
            status=conn.status,
            initial_sync_completed=conn.initial_sync_completed,
            connected_at=conn.connected_at,
            last_synced_at=conn.last_synced_at,
            email_count=conn.email_count,
            last_error=(conn.last_error or "")[:300] or None,
        )
        for conn in rows
    ]
    return AdminSourcesResponse(providers=providers, connections=connections)


@router.get("/runs", response_model=AdminRunListResponse)
def list_runs(
    status: str = Query(default="", max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AdminRunListResponse:
    """Các lượt chạy pipeline gần đây — trạng thái và lỗi, không có kết quả."""
    statement = select(Run)
    if status:
        statement = statement.where(Run.status == status)
    total = _count(db, statement)
    rows = db.execute(statement.order_by(Run.created_at.desc()).limit(limit)).scalars().all()

    items = [
        AdminRunRow(
            id=run.id,
            user_id=str(run.user_id),
            status=run.status,
            created_at=run.created_at,
            sources_count=len(run.sources or []),
            error_message=(run.error_message or "")[:300] or None,
        )
        for run in rows
    ]
    return AdminRunListResponse(items=items, total=total)


@router.get("/audit", response_model=AdminAuditListResponse)
def list_audit(
    action: str = Query(default="", max_length=48),
    object_type: str = Query(default="", max_length=48),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AdminAuditListResponse:
    """Nhật ký thay đổi theo FR-070 — ai làm gì, lúc nào, trên bản ghi nào."""
    statement = select(AuditEvent)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if object_type:
        statement = statement.where(AuditEvent.object_type == object_type)

    total = _count(db, statement)
    rows = db.execute(statement.order_by(AuditEvent.created_at.desc()).limit(limit)).scalars().all()

    items = [
        AdminAuditRow(
            id=ev.id,
            action=ev.action,
            object_type=ev.object_type,
            object_id=ev.object_id,
            actor_type=ev.actor_type,
            actor_id=ev.actor_id,
            version_label=ev.version_label,
            details=ev.details,
            created_at=ev.created_at,
        )
        for ev in rows
    ]
    return AdminAuditListResponse(items=items, total=total)


@router.get("/telemetry", response_model=AdminTelemetryResponse)
def telemetry_summary(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> AdminTelemetryResponse:
    """Đếm sự kiện đo lường theo tên trong cửa sổ thời gian.

    Trả về đúng tên sự kiện và số đếm. Bản thân bảng telemetry đã lọc thuộc tính
    theo danh sách cho phép (services/telemetry.py) nên không có nội dung gốc,
    nhưng ở đây vẫn chỉ lấy số đếm chứ không trả `attributes` ra ngoài.
    """
    since = _window_start(days)

    event_rows = db.execute(
        select(
            TelemetryEvent.name,
            func.count(TelemetryEvent.id),
            func.avg(TelemetryEvent.duration_ms),
        )
        .where(TelemetryEvent.created_at >= since)
        .group_by(TelemetryEvent.name)
        .order_by(func.count(TelemetryEvent.id).desc())
    ).all()

    events = [
        AdminTelemetryCount(
            name=str(name),
            count=int(count),
            avg_duration_ms=int(avg) if avg is not None else None,
        )
        for name, count, avg in event_rows
    ]

    feedback_rows = db.execute(
        select(
            TelemetryEvent.attributes["verdict"].as_string(),
            func.count(TelemetryEvent.id),
        )
        .where(TelemetryEvent.name == "answer_feedback", TelemetryEvent.created_at >= since)
        .group_by(TelemetryEvent.attributes["verdict"].as_string())
    ).all()
    feedback = [
        AdminFeedbackBreakdown(verdict=str(verdict), count=int(count)) for verdict, count in feedback_rows if verdict
    ]

    return AdminTelemetryResponse(window_days=days, events=events, feedback=feedback)


@router.get("/app-ratings", response_model=AdminAppRatingSummary)
def app_ratings(
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> AdminAppRatingSummary:
    """Product ratings and written beta feedback for the admin dashboard."""
    since = _window_start(days)
    base = select(AppRating).where(AppRating.created_at >= since)
    total, average = db.execute(
        select(func.count(AppRating.id), func.avg(AppRating.rating)).where(AppRating.created_at >= since)
    ).one()
    distribution_rows = db.execute(
        select(AppRating.rating, func.count(AppRating.id))
        .where(AppRating.created_at >= since)
        .group_by(AppRating.rating)
        .order_by(AppRating.rating)
    ).all()
    rows = db.scalars(base.order_by(AppRating.created_at.desc()).limit(limit)).all()
    return AdminAppRatingSummary(
        total=int(total or 0),
        average_rating=round(float(average), 2) if average is not None else None,
        distribution=[
            AdminFeedbackBreakdown(verdict=str(rating), count=int(count)) for rating, count in distribution_rows
        ],
        items=[
            AdminAppRatingRow(
                id=row.id,
                rating=row.rating,
                feedback=row.feedback or "",
                trigger=row.trigger,
                created_at=row.created_at,
            )
            for row in rows
        ],
    )
