import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from src.api.adaptive_learning import router as adaptive_learning_router
from src.api.admin import router as admin_router
from src.api.admin_announcement_candidates import router as admin_announcement_candidates_router
from src.api.admin_blog import router as admin_blog_router
from src.api.admin_program_events import router as admin_program_events_router
from src.api.admin_program_information import router as admin_program_information_router
from src.api.admin_program_schedule_templates import router as admin_program_schedule_templates_router
from src.api.announcement_candidates import router as announcement_candidates_router
from src.api.auth import router as auth_router
from src.api.blog import router as blog_router
from src.api.calendar import router as calendar_router
from src.api.connections import router as connections_router
from src.api.conversations import router as conversations_router
from src.api.discord_channel import router as discord_channel_router
from src.api.excel_import import router as excel_import_router
from src.api.google_docs import router as google_docs_router
from src.api.google_drive import router as google_drive_router
from src.api.google_sheets import router as google_sheets_router
from src.api.integrations import router as integrations_router
from src.api.intent import router as intent_router
from src.api.meeting_notes import router as meeting_notes_router
from src.api.memory import router as memory_router
from src.api.messages import router as messages_router
from src.api.planner import router as planner_router
from src.api.program_information import router as program_information_router
from src.api.projects import router as projects_router
from src.api.public_ask import router as public_ask_router
from src.api.push import router as push_router
from src.api.pwa_recovery import router as pwa_recovery_router
from src.api.rate_limit import limiter
from src.api.ratings import router as ratings_router
from src.api.reminders import router as reminders_router
from src.api.routes import router
from src.api.routines import router as routines_router
from src.api.runs import router as runs_router
from src.api.schedule_conflicts import router as schedule_conflicts_router
from src.api.shared_chat import router as shared_chat_router
from src.api.storage import router as storage_router
from src.api.tasks import router as tasks_router
from src.api.telegram_channel import router as telegram_channel_router
from src.api.vision import router as vision_router
from src.config import get_settings
from src.db import Base, SessionLocal, engine, ensure_runtime_schema
from src.langsmith_tracing import configure_langsmith_client
from src.models import announcement_candidate as _announcement_candidate_model  # noqa: F401
from src.models import app_rating as _app_rating_model  # noqa: F401 - đăng ký model AppRating
from src.models import calendar_event as _calendar_event_model  # noqa: F401 - đăng ký CalendarEvent/CalendarOperation
from src.models import channel_delivery as _channel_delivery_model  # noqa: F401 - đăng ký Telegram receipt
from src.models import cluster as _cluster_model  # noqa: F401 - đăng ký Cluster/ClusterMessage
from src.models import document_read as _document_read_model  # noqa: F401 - đăng ký quota/cache đọc Docs+Sheets
from src.models import meeting_note as _meeting_note_model  # noqa: F401 - đăng ký MeetingNote/MeetingActionItem
from src.models import pipeline_audit as _pipeline_audit_model  # noqa: F401 - đăng ký schema audit CP0
from src.models import planner_preference as _planner_preference_model  # noqa: F401
from src.models import program_calendar_sync as _program_sync_model  # noqa: F401 - đăng ký ProgramCalendarSync
from src.models import program_event as _program_event_model  # noqa: F401 - đăng ký ProgramEvent
from src.models import program_event_notice as _program_event_notice_model  # noqa: F401 - đăng ký dedupe thông báo
from src.models import (
    program_information as _program_information_model,  # noqa: F401 - đăng ký kho thông tin chương trình
)
from src.models import program_schedule_template as _program_schedule_template_model  # noqa: F401 - đăng ký mẫu lịch
from src.models import project as _project_model  # noqa: F401 - đăng ký Project
from src.models import push_subscription as _push_subscription_model  # noqa: F401 - đăng ký PushSubscription
from src.models import recording_quota as _recording_quota_model  # noqa: F401 - đăng ký RecordingQuotaSlot
from src.models import routine as _routine_model  # noqa: F401 - đăng ký Routine/RoutineRun
from src.models import schedule_conflict as _schedule_conflict_model  # noqa: F401 - đăng ký ScheduleConflict
from src.models import source_scope_access as _source_scope_access_model  # noqa: F401 - đăng ký access grants
from src.models import sync_cursor as _sync_cursor_model  # noqa: F401 - đăng ký SyncCursor
from src.models import task_evidence as _task_evidence_model  # noqa: F401 - đăng ký TaskEvidence
from src.models import user as _user_model  # noqa: F401 - đăng ký model User vào Base.metadata
from src.observability import LATENCY, REQUESTS, metrics_response, route_group
from src.services.program_access import reconcile_all_discord_connections
from src.worker import run_worker

# Khong goi basicConfig thi root logger khong co handler -> log INFO cua toan
# bo src.* (sync/run/task/reminder) bien mat khi demo, chi WARNING+ hien ra
# qua lastResort handler xau format, khong timestamp. Goi som nhat co the,
# truoc khi request/embedded worker task nao chay.
logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_langsmith_client()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    # Cột Vector và index FTS cần extension bật sẵn, nếu không create_all sẽ
    # chết vì kiểu "vector" chưa tồn tại. sqlite (test/dev) bỏ qua bước này.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    # TODO: pilot scale dùng create_all, chưa có Alembic migration thật.
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    # Backfill stale C/B identities at every rollout. This is idempotent and
    # also grants channels imported since the user's last Discord OAuth flow.
    with SessionLocal() as db:
        access_counts = reconcile_all_discord_connections(db)
    logger.info("Reconciled Discord program access on startup: %s", access_counts)

    worker_task: asyncio.Task | None = None
    if settings.embed_worker:
        # Quên chạy `make worker` song song `make run` từng khiến mọi Sync
        # treo mãi ở "queued" không báo lỗi (xem config.py: embed_worker).
        # Chạy claim/execute loop ngay trong tiến trình API để `make run` một
        # mình là đủ; production giữ worker là container riêng qua biến này.
        worker_task = asyncio.create_task(run_worker())
        logger.info("Embedded worker task started (settings.embed_worker=True)")

    yield

    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    started = time.perf_counter()
    group = route_group(request.url.path)
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        REQUESTS.labels(request.method, group, str(status)).inc()
        LATENCY.labels(request.method, group).observe(time.perf_counter() - started)


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# Bat buoc de default_limits (rate_limit.py) co hieu luc tren MOI route —
# thieu dong nay thi chi route co @limiter.limit rieng moi bi gioi han, moi
# endpoint con lai (tasks.py, messages.py, calendar.py, meeting_notes.py...)
# hoan toan khong co gioi han nao du da khai default_limits.
app.add_middleware(SlowAPIMiddleware)

app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(telegram_channel_router, prefix="/api/v1")
app.include_router(discord_channel_router, prefix="/api/v1")
app.include_router(vision_router, prefix="/api/v1")
app.include_router(reminders_router, prefix="/api/v1")
app.include_router(routines_router, prefix="/api/v1")
app.include_router(push_router, prefix="/api/v1")
app.include_router(google_sheets_router, prefix="/api/v1")
app.include_router(excel_import_router, prefix="/api/v1")
app.include_router(pwa_recovery_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(schedule_conflicts_router, prefix="/api/v1")
app.include_router(shared_chat_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(adaptive_learning_router, prefix="/api/v1")
app.include_router(meeting_notes_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(public_ask_router, prefix="/api/v1")
app.include_router(google_docs_router, prefix="/api/v1")
app.include_router(google_drive_router, prefix="/api/v1")
app.include_router(intent_router, prefix="/api/v1")
app.include_router(runs_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(planner_router, prefix="/api/v1")
app.include_router(storage_router, prefix="/api/v1")
app.include_router(ratings_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(admin_blog_router, prefix="/api/v1")
app.include_router(admin_program_events_router, prefix="/api/v1")
app.include_router(admin_program_schedule_templates_router, prefix="/api/v1")
app.include_router(admin_program_information_router, prefix="/api/v1")
app.include_router(admin_announcement_candidates_router, prefix="/api/v1")
app.include_router(announcement_candidates_router, prefix="/api/v1")
app.include_router(program_information_router, prefix="/api/v1")
app.include_router(blog_router, prefix="/api/v1")


@app.get("/health")
async def health():
    # TEST: Thêm comment để test AI Log | CHECKPOINT
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    """Readiness: chỉ 'ok' khi thật sự phục vụ được, tức là còn nói chuyện được với DB.

    Cố ý KHÔNG gộp vào `/health`. `/health` là liveness và đang được
    `.github/workflows/deploy.yml`, `client/web-app/Caddyfile`, `client/web-app/vercel.json`,
    healthcheck của `docker-compose.yml` và `scripts/deploy_vm_local.sh` dùng. Cho nó trả 503
    khi DB ngủ đồng nghĩa container bị giết và deploy fail dù backend vẫn khoẻ.

    Frontend đọc endpoint này để bật banner bảo trì cho khu app; trang marketing không phụ
    thuộc DB nên vẫn phục vụ bình thường.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - mọi lỗi kết nối đều là "chưa sẵn sàng"
        # Không nuốt lỗi: đổi thành tín hiệu 503 có tên nguyên nhân để còn chẩn đoán được.
        response.status_code = 503
        return {
            "status": "degraded",
            "dependency": "database",
            "reason": type(exc).__name__,
            "env": settings.app_env,
        }
    return {"status": "ok", "dependency": "database", "env": settings.app_env}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    # This route is internal-only: minute_caddy denies /metrics before proxying
    # the public API host; Prometheus reaches it over the private Docker network.
    return metrics_response()
