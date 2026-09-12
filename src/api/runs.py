import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.agents.briefing.evidence import Evidence, fuse_and_rank
from src.agents.pipeline.graph import pipeline
from src.api.deps import get_current_user, get_current_user_id
from src.api.rate_limit import limiter
from src.config import get_settings
from src.db import SessionLocal, get_db
from src.guardrail.output import ground_candidate
from src.models.brief import Brief
from src.models.connection import Connection
from src.models.message import Message
from src.models.run import Run
from src.models.run_node_event import RunNodeEvent
from src.models.schemas import (
    AutoSyncPreferenceResponse,
    AutoSyncPreferenceUpdateRequest,
    BriefResponse,
    ChatSyncRequest,
    ChatSyncResponse,
    RunCreateRequest,
    RunLimitsResponse,
    RunResponse,
)
from src.models.task import Task
from src.models.user import User
from src.services import chat_sync
from src.services.filter_classify import has_valid_deep_link
from src.services.language import empty_result_message, summary_instruction
from src.services.llm import get_llm, response_text
from src.services.reminders import generate_evidence_conflict_notices
from src.services.work_question import asks_about_work

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])

# Field state ứng với mỗi node — đếm tiến trình mà không phải serialize
# nguyên state pipeline (có db Session/connector, không JSON hoá được).
_NODE_COUNT_FIELD = {
    "fetch": "raw_messages",
    "normalize": "normalized",
    "filter": "filtered",
    "summary": "summary_items",
    "make_batches": "batches",
    "extract_batch": "extracted",
    "resolve": "resolved",
    "cluster": "clusters",
    "reduce": "clusters",
    "persist": "tasks_persisted",
}

_TERMINAL_STATUSES = ("succeeded", "failed")


def _run_payload(run: Run) -> RunCreateRequest:
    return RunCreateRequest(
        sources=run.sources,
        time_from=run.range_from,
        time_to=run.range_to,
        timezone=run.timezone,
        language=run.language,
        idempotency_key=run.idempotency_key,
        mode=run.mode,
    )


def claim_next_run(db: Session) -> Run | None:
    """Atomically claim one durable queued run. PostgreSQL skips other workers' locks."""
    row = db.execute(
        select(Run).where(Run.status == "queued").order_by(Run.created_at).with_for_update(skip_locked=True).limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = "running"
    row.claimed_at = datetime.now(UTC)
    row.attempts += 1
    db.commit()
    db.refresh(row)
    return row


def recover_stale_runs(db: Session) -> int:
    """Make jobs claimable again after a worker crash, preserving their durable run row."""
    cutoff = datetime.now(UTC) - timedelta(minutes=get_settings().run_claim_timeout_minutes)
    rows = db.execute(select(Run).where(Run.status == "running", Run.claimed_at < cutoff)).scalars().all()
    for row in rows:
        row.status = "queued"
        row.claimed_at = None
    if rows:
        db.commit()
    return len(rows)


def _count_gmail_messages(db: Session, connection_id: int) -> int:
    """Gmail status không được tính lẫn Calendar event dùng chung connection."""
    return (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.connection_id == connection_id,
                Message.provider == "google",
            )
        )
        or 0
    )


def _to_run_response(row: Run) -> RunResponse:
    return RunResponse.model_validate(row, from_attributes=True)


def _event_payload(event: RunNodeEvent) -> dict:
    return {
        "node": event.node,
        "status": event.status,
        "count": event.count,
        "message": event.message,
        "at": event.at.isoformat(),
    }


def _evidence_items(filtered_items: list[dict]) -> list[dict]:
    """Keep only items that survived classification for the user-facing brief.

    The pipeline normally passes ``filtered`` here, but this final gate keeps
    rejected/ignored records out of evidence if a future node accidentally
    merges them back into the list.
    """
    return [
        item
        for item in filtered_items
        if item.get("importance", "relevant") != "ignore"
        and item.get("brief_section", "reference") != "ignore"
    ]


def _make_publish_progress(db: Session, run_id: int) -> Callable[[str, int, str], None]:
    """Báo tiến trình fetch theo từng item — ghi RunNodeEvent (để SSE replay
    được sau F5, giống mọi event khác) rồi bắn ngay qua SSE live."""

    def publish_progress(source_id: str, count: int, label: str) -> None:
        event = RunNodeEvent(run_id=run_id, node="fetch", status="item", count=count, message=f"[{source_id}] {label}")
        db.add(event)
        db.commit()

    return publish_progress


def _evidence_for_conflict_detection(resolved_items: list[dict]) -> list[Evidence]:
    """Đổi item đã resolve (có due_at thật) sang Evidence cho fuse_and_rank().

    Dùng `resolved` chứ không phải `filtered_items`: due_at chỉ được gắn ở
    resolve_node, filter_node chạy trước đó chưa có due_at.
    """
    items: list[Evidence] = []
    for idx, item in enumerate(resolved_items):
        message = item.get("message", {}) or {}
        content = str(item.get("title") or message.get("text") or message.get("normalized_text") or "").strip()
        if not content:
            continue
        items.append(
            Evidence(
                evidence_id=str(message.get("id") or idx),
                source=str(message.get("provider", "unknown")),
                content=content,
                importance=int(message.get("importance_score", 0) or 0),
                due_at=item.get("due_at"),
            )
        )
    return items


def _sender_line(item: dict) -> str:
    """Người gửi/người nhận thật của mail. Brief tóm tắt trước đây chỉ ghép
    subject + snippet nên bản tóm tắt không thể nêu mail đến từ ai — thông tin
    vốn có sẵn trong item đã normalize (author_name/author_id/to/cc) mà không
    nơi nào đưa vào prompt."""
    sender_name = item.get("author_name") or ""
    sender_email = item.get("author_id") or ""
    sender = f"{sender_name} <{sender_email}>".strip() if sender_email else (sender_name or "?")
    recipients = ", ".join(item.get("to") or []) or "?"
    cc = item.get("cc") or []
    cc_part = f" [Cc: {', '.join(cc)}]" if cc else ""
    return f"[Từ: {sender}] [Đến: {recipients}]{cc_part}"


def _summary_evidence_block(item: dict) -> str:
    """1 khối evidence cho brief tóm tắt: id + người gửi/nhận + tiêu đề + thân
    mail + nội dung file đính kèm đã trích (attachment_extract_node đã chạy cho
    cả nhánh summary). attachment_text đã qua sanitize_untrusted_text ở node đó."""
    body = str(item.get("snippet") or item.get("normalized_text") or item.get("text") or "")[:500]
    block = f"[{item.get('id')}] {_sender_line(item)}\n{item.get('subject', '')}: {body}"
    attachment_text = str(item.get("attachment_text") or "").strip()
    if attachment_text:
        block = f"{block}\n{attachment_text[:2500]}"
    return block


def _summary_fallback_line(item: dict) -> str:
    """Nhánh mock/không-grounded vẫn phải nêu người gửi — không thì tóm tắt trả
    về mất hẳn attribution đúng lúc người dùng cần nhất."""
    body = str(item.get("snippet") or item.get("normalized_text") or "")[:180]
    return f"{_sender_line(item)} {body}".strip()


async def _build_brief(
    db: Session,
    run_id: int,
    user_id: int,
    tasks_persisted: list[dict],
    filtered_items: list[dict],
    resolved_items: list[dict] | None = None,
    language: str | None = None,
) -> Brief:
    """`language` là ngôn ngữ GIAO DIỆN của lần Sync này, không phải ngôn ngữ
    của mail nguồn: hộp thư tiếng Anh mà giao diện để tiếng Việt thì brief
    phải là tiếng Việt. Trước đây tham số này không tồn tại ở đây nên mọi
    bản tóm tắt mail đều bị prompt ép về tiếng Việt bất kể người dùng chọn
    gì."""
    settings = get_settings()
    rows = [db.get(Task, t["task_id"]) for t in tasks_persisted]
    top = sorted((r for r in rows if r is not None), key=lambda t: t.signal_strength, reverse=True)[:3]
    top_priority = [
        {"taskId": t.id, "title": t.title, "dueAt": t.due_at.isoformat() if t.due_at else None} for t in top
    ]
    evidence = []
    for item in _evidence_items(filtered_items)[:20]:
        source_url = item.get("deep_link")
        if not source_url or not has_valid_deep_link(item):
            continue
        quote = str(item.get("snippet") or item.get("normalized_text") or item.get("text") or "").strip()
        if not quote:
            continue
        evidence.append(
            {
                "message_id": str(item.get("id")),
                "thread_id": item.get("thread_id"),
                "source": item.get("provider", "unknown"),
                "source_url": source_url,
                # Người gửi/người nhận đi kèm từng bằng chứng — UI Brief trước
                # đây chỉ có quote nên không hiển thị nổi mail đến từ ai.
                "sender_name": item.get("author_name"),
                "sender_email": item.get("author_id"),
                "recipients": item.get("to") or [],
                "subject": item.get("subject", ""),
                "has_attachment_text": bool(item.get("attachment_text")),
                "quote": quote[:500],
                "importance": item.get("importance", "relevant"),
                "importance_score": item.get("importance_score", 0),
                "reasons": item.get("classification_reasons", []),
            }
        )

    if not tasks_persisted and filtered_items:
        summary_source = filtered_items[:20]
        evidence_text = "\n\n".join(_summary_evidence_block(item) for item in summary_source)
        if settings.mock_llm:
            summary = " / ".join(_summary_fallback_line(item) for item in filtered_items[:5])
        else:
            llm = get_llm()
            response = await asyncio.wait_for(
                llm.ainvoke(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Tóm tắt nội dung các email dưới đây trong 3-5 câu. Đây là yêu cầu tóm tắt nội dung, "
                                "không phải trích xuất task. Mỗi email có dòng [Từ:]/[Đến:] nêu người gửi và người "
                                "nhận thật — với MỖI email phải nêu rõ mail đến từ ai trước khi tóm nội dung, không "
                                "suy diễn tên khác. Nếu email có phần [Đính kèm: tên file] thì đó là nội dung file "
                                "đính kèm, phải tóm tắt luôn các điểm chính trong đó chứ không chỉ nhắc là có file. "
                                "Chỉ dùng thông tin có trong evidence; không suy đoán. "
                                f"{summary_instruction(language)}"
                            ),
                        },
                        {"role": "user", "content": evidence_text},
                    ]
                ),
                timeout=25,
            )
            candidate = response_text(response)
            # Nguồn chấm grounding phải khớp đúng nguồn đã đưa vào prompt: chấm
            # theo mỗi snippet thì phần người gửi và phần nội dung file đính kèm
            # (vừa được yêu cầu nêu ra) không có token nào để đối chiếu, tóm tắt
            # càng làm đúng yêu cầu càng bị đánh trượt về nhánh fallback.
            grounded = ground_candidate(
                candidate,
                {str(item.get("id")): _summary_evidence_block(item) for item in summary_source},
            )
            summary = (
                candidate
                if grounded.status == "grounded"
                else "\n".join(_summary_fallback_line(item) for item in filtered_items[:5])
            )
    elif not tasks_persisted:
        summary = empty_result_message(language)
    elif settings.mock_llm:
        summary = f"Tìm thấy {len(tasks_persisted)} việc cần làm."
    else:
        llm = get_llm()
        titles = "\n".join(f"- {t['title']}" for t in tasks_persisted)
        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": (
                        "Viết 1 đoạn ngắn (2-3 câu) tóm tắt các việc cần làm dưới đây, chỉ dựa trên "
                        "tiêu đề đã cho, không thêm chi tiết mới. "
                        f"{summary_instruction(language)}"
                    ),
                },
                {"role": "user", "content": titles},
            ]
        )
        summary = response_text(response)

    # fuse_and_rank() gộp evidence theo topic, flag conflict khi 2+ nguồn nêu
    # ngày khác nhau cho cùng chủ đề — thuật toán có sẵn (tests/test_agents/
    # test_briefing_foundation.py) nhưng trước đây không nơi nào gọi tới,
    # schedule_conflicts luôn rỗng dù UI/mock từng giả vờ có dữ liệu.
    clusters = fuse_and_rank(_evidence_for_conflict_detection(resolved_items or []), now=datetime.now(UTC))
    conflicting_clusters = [c for c in clusters if c.conflict]
    schedule_conflicts = [
        {
            "topic": cluster.topic,
            "items": [
                {"source": item.source, "content": item.content[:300], "dueAt": item.due_at.isoformat() if item.due_at else None}
                for item in cluster.items
            ],
        }
        for cluster in conflicting_clusters
    ]
    if conflicting_clusters:
        generate_evidence_conflict_notices(db, str(user_id), conflicting_clusters)

    brief = Brief(
        run_id=run_id,
        user_id=user_id,
        summary=summary,
        top_priority=top_priority,
        schedule_conflicts=schedule_conflicts,
        evidence=evidence,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief


def _csv_setting(raw: str) -> list[str]:
    """Danh sách tin cậy cấu hình dạng chuỗi ngăn cách dấu phẩy (giống
    cors_origins). Chuẩn hoá về chữ thường vì filter_classify.py so khớp với
    địa chỉ/domain đã lower ở normalize()."""
    return [part.strip().lower() for part in (raw or "").split(",") if part.strip()]


async def execute_run(run_id: int, user_id: int, body: RunCreateRequest) -> None:
    """Chạy pipeline 9 node cho 1 run, persist từng event + brief cuối. Lỗi
    giữa chừng không được rơi ra ngoài — ghi vào run.status='failed' + event lỗi."""
    db = SessionLocal()
    settings = get_settings()
    try:
        run = db.get(Run, run_id)
        run.status = "running"
        db.commit()

        pipeline_state = {
            "db": db,
            "run_id": run_id,
            "user_id": str(user_id),
            "sources": [{"connection_id": s.connection_id, "source_id": s.source_id} for s in body.sources],
            "time_from": body.time_from,
            "time_to": body.time_to,
            "timezone": body.timezone,
            "language": body.language,
            "user_email": (db.get(User, user_id).email if db.get(User, user_id) else None),
            "trusted_senders": _csv_setting(settings.trusted_senders),
            "trusted_sender_domains": _csv_setting(settings.trusted_sender_domains),
            "program_domains": _csv_setting(settings.program_domains),
            "mode": body.mode,
            "errors": [],
            "publish_progress": _make_publish_progress(db, run_id),
        }

        final_state: dict = {}
        try:
            async for chunk in pipeline.astream(pipeline_state, stream_mode="updates"):
                node_name, payload = next(iter(chunk.items()))
                final_state.update(payload)
                errors = payload.get("errors", [])
                count_field = _NODE_COUNT_FIELD.get(node_name)
                count = len(payload.get(count_field, [])) if count_field else None

                event = RunNodeEvent(
                    run_id=run_id,
                    node=node_name,
                    status="error" if errors else "ok",
                    count=count,
                    message="; ".join(errors) if errors else None,
                )
                db.add(event)
                db.commit()
                db.refresh(event)
        except Exception as exc:  # noqa: BLE001 - lỗi giữa chừng pipeline, không sập worker
            logger.warning("Run %s lỗi giữa chừng: %s", run_id, exc)
            # Session có thể đang ở trạng thái pending-rollback nếu exception đến
            # từ 1 lệnh DB (vd. IntegrityError trong node) — phải rollback trước
            # khi commit tiếp, nếu không db.commit() dưới đây tự ném lỗi khác,
            # thoát khỏi task nền mà không set được status='failed' (run treo mãi).
            db.rollback()
            run.status = "failed"
            run.error_message = str(exc)[:1024]
            db.commit()
            for source in body.sources:
                connection = db.get(Connection, source.connection_id)
                if connection is not None and connection.provider == "google":
                    connection.status = "error"
                    connection.last_error = str(exc)[:1024]
            db.commit()
            error_event = RunNodeEvent(run_id=run_id, node="error", status="error", message=str(exc)[:500])
            db.add(error_event)
            db.commit()
            db.refresh(error_event)
            return

        tasks_persisted = final_state.get("tasks_persisted", [])
        try:
            await _build_brief(
                db,
                run_id,
                user_id,
                tasks_persisted,
                final_state.get("filtered", []),
                final_state.get("resolved", []),
                language=body.language,
            )
        except Exception as exc:  # noqa: BLE001 - final LLM failure must close the run
            logger.warning("Run %s brief generation failed: %s", run_id, exc)
            run.status = "failed"
            run.error_message = f"brief_generation_failed: {str(exc)[:900]}"
            db.commit()
            error_event = RunNodeEvent(run_id=run_id, node="brief", status="error", message=str(exc)[:500])
            db.add(error_event)
            db.commit()
            db.refresh(error_event)
            return

        user = db.get(User, user_id)
        if user is not None:
            user.last_synced_at = datetime.now(UTC)

        synced_at = datetime.now(UTC)
        for connection_id in {source.connection_id for source in body.sources}:
            connection = db.get(Connection, connection_id)
            if connection is None or connection.provider != "google":
                continue
            connection.status = "connected_ready"
            connection.initial_sync_completed = True
            connection.last_synced_at = synced_at
            connection.last_error = None
            connection.email_count = _count_gmail_messages(db, connection.id)

        run.status = "succeeded"
        db.commit()

        done_event = RunNodeEvent(run_id=run_id, node="done", status="ok", count=len(tasks_persisted))
        db.add(done_event)
        db.commit()
        db.refresh(done_event)
    finally:
        db.close()


class RunEnqueueBlockedError(Exception):
    """Một Run hợp lệ nhưng chưa được nhận vào hàng đợi lúc này.

    Tách riêng khỏi HTTPException vì cùng bộ luật hạn mức phải phục vụ hai chỗ
    gọi khác nhau: API trả lỗi cho người đang ngồi chờ, còn scheduler nền
    (src/services/auto_sync.py) chỉ ghi log rồi bỏ qua tới vòng sau. `status`
    là mã HTTP mà lớp API nên trả nếu chính người dùng gây ra.
    """

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def enqueue_run(db: Session, user_id: int, body: RunCreateRequest) -> Run:
    """Kiểm mọi hạn mức rồi ghi một Run trạng thái `queued`; worker sẽ tự claim.

    Cơ chế: khoá dòng users bằng SELECT ... FOR UPDATE để nối tiếp các lần
    enqueue của cùng tài khoản giữa nhiều API replica — thiếu khoá này thì hai
    idempotency key khác nhau đều thấy "đang có 0 run" và cùng lọt qua trần
    per-user. Sau đó tra idempotency_key: trùng thì trả lại chính run cũ chứ
    không chạy lần hai. Cuối cùng mới kiểm trần per-user và trần toàn hệ thống.
    Ném RunEnqueueBlockedError nếu vướng bất kỳ hạn mức nào.
    """
    settings = get_settings()
    if len(body.sources) > settings.max_sync_sources:
        raise RunEnqueueBlockedError(422, f"Chỉ được Sync tối đa {settings.max_sync_sources} nguồn mỗi lần.")
    if body.time_to - body.time_from > timedelta(days=settings.max_sync_range_days):
        raise RunEnqueueBlockedError(422, f"Khoảng Sync tối đa {settings.max_sync_range_days} ngày.")

    db.execute(select(User.id).where(User.id == user_id).with_for_update()).scalar_one()
    existing = db.execute(
        select(Run).where(Run.user_id == user_id, Run.idempotency_key == body.idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        # Bấm Force Sync 2 lần với cùng idempotencyKey -> trả lại run cũ, không chạy lại.
        return existing

    active_for_user = (
        db.scalar(select(func.count(Run.id)).where(Run.user_id == user_id, Run.status.in_(("queued", "running")))) or 0
    )
    if active_for_user >= settings.max_runs_per_user:
        raise RunEnqueueBlockedError(429, "Bạn đã có một Sync đang chờ hoặc đang chạy.")
    active_global = db.scalar(select(func.count(Run.id)).where(Run.status.in_(("queued", "running")))) or 0
    if active_global >= settings.max_concurrent_runs:
        raise RunEnqueueBlockedError(429, "Hệ thống đang bận, vui lòng thử lại sau.")

    run = Run(
        user_id=user_id,
        sources=[s.model_dump() for s in body.sources],
        range_from=body.time_from,
        range_to=body.time_to,
        idempotency_key=body.idempotency_key,
        timezone=body.timezone,
        language=body.language,
        mode=body.mode,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.post("/chat-trigger", response_model=ChatSyncResponse)
@limiter.limit("30/minute")
async def trigger_sync_for_chat(
    request: Request,
    body: ChatSyncRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSyncResponse:
    """Kéo đồng bộ hộ người dùng khi họ chat, thay cho nút Sync tay đã ẩn.

    Không bao giờ ném lỗi vì chuyện đồng bộ: người dùng đang hỏi một câu chat,
    việc Jira sập hay chưa nối nguồn nào không được biến thành 5xx chắn ngang
    câu trả lời. Mọi nhánh hỏng đều trả `triggered=False` kèm lý do.
    """
    settings = get_settings()
    if not settings.chat_sync_enabled:
        return ChatSyncResponse(triggered=False, reason="disabled")

    decision = chat_sync.decide(
        db,
        user.id,
        asks_about_work=asks_about_work(body.message),
        timezone=body.timezone,
    )
    if not decision.should_sync:
        return ChatSyncResponse(triggered=False, reason=decision.reason)

    try:
        payload = await chat_sync.build_chat_run_request(
            db, user.id, decision, language=body.language, timezone=body.timezone
        )
    except Exception:  # noqa: BLE001 - khám phá nguồn hỏng không được chắn câu chat
        logger.exception("chat-trigger: dựng payload thất bại cho user %s", user.id)
        return ChatSyncResponse(triggered=False, reason="source_discovery_failed")

    if payload is None:
        return ChatSyncResponse(triggered=False, reason="no_sources")

    try:
        run = enqueue_run(db, user.id, payload)
    except RunEnqueueBlockedError as blocked:
        # Vướng trần không phải lỗi của người dùng đang chat — trả lời bằng dữ
        # liệu sẵn có, lần sau thử lại.
        logger.info("chat-trigger bị chặn cho user %s: %s", user.id, blocked.detail)
        return ChatSyncResponse(triggered=False, reason="rate_limited")

    # KHÔNG tự gọi execute_run ở đây. `POST /runs` cũng chỉ enqueue rồi để
    # worker `claim_next_run()` nhặt — claim dùng SELECT ... FOR UPDATE SKIP
    # LOCKED nên đúng một tiến trình chạy một run. Thêm background task song
    # song sẽ đua với worker trên cùng hàng "queued": cùng một run chạy hai
    # lượt, tốn gấp đôi LLM và sinh task trùng.
    return ChatSyncResponse(
        triggered=True,
        reason=decision.reason,
        run=RunResponse.model_validate(run, from_attributes=True),
    )


@router.get("/limits", response_model=RunLimitsResponse)
def get_run_limits(user: User = Depends(get_current_user)) -> RunLimitsResponse:
    """Cho FE biết hạn mức Sync để chặn ngay tại chỗ tick nguồn.

    Trước đây FE không biết trần nào cả: người dùng tick bao nhiêu nguồn cũng
    được, bấm Sync rồi mới ăn 422 và phải tự đoán phải bỏ bớt cái nào.
    """
    settings = get_settings()
    return RunLimitsResponse(
        max_sync_sources=settings.max_sync_sources,
        max_sync_range_days=settings.max_sync_range_days,
        auto_sync_enabled=settings.auto_sync_enabled and user.auto_sync_enabled,
        auto_sync_interval_minutes=settings.auto_sync_interval_minutes,
    )


def _auto_sync_preference_response(user: User) -> AutoSyncPreferenceResponse:
    """Không để client phải đoán công tắc tổng hay ghi đè lựa chọn người dùng."""
    settings = get_settings()
    return AutoSyncPreferenceResponse(
        auto_sync_enabled=settings.auto_sync_enabled and user.auto_sync_enabled,
        user_auto_sync_enabled=user.auto_sync_enabled,
        auto_sync_interval_minutes=settings.auto_sync_interval_minutes,
    )


@router.get("/auto-sync-preference", response_model=AutoSyncPreferenceResponse)
def get_auto_sync_preference(user: User = Depends(get_current_user)) -> AutoSyncPreferenceResponse:
    """Đọc lựa chọn auto-sync của caller, không nhận hoặc lộ user id khác."""
    return _auto_sync_preference_response(user)


@router.patch("/auto-sync-preference", response_model=AutoSyncPreferenceResponse)
@limiter.limit("10/minute")
def update_auto_sync_preference(
    request: Request,
    body: AutoSyncPreferenceUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AutoSyncPreferenceResponse:
    """Lưu rút lại/khôi phục đồng ý của chính caller trước vòng worker kế tiếp."""
    user.auto_sync_enabled = body.auto_sync_enabled
    db.commit()
    db.refresh(user)
    return _auto_sync_preference_response(user)


@router.post("", response_model=RunResponse, status_code=201)
@limiter.limit("3/minute")
async def create_run(
    request: Request,
    body: RunCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    try:
        return _to_run_response(enqueue_run(db, user.id, body))
    except RunEnqueueBlockedError as blocked:
        raise HTTPException(status_code=blocked.status, detail=blocked.detail) from blocked


def _get_owned_run(db: Session, run_id: int, user_id: str) -> Run:
    row = db.execute(select(Run).where(Run.id == run_id, Run.user_id == int(user_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy run.")
    return row


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> RunResponse:
    return _to_run_response(_get_owned_run(db, run_id, user_id))


@router.get("/{run_id}/brief", response_model=BriefResponse)
def get_run_brief(
    run_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> BriefResponse:
    _get_owned_run(db, run_id, user_id)
    brief = db.execute(select(Brief).where(Brief.run_id == run_id)).scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=404, detail="Run chưa có brief (chưa chạy xong hoặc đã lỗi).")
    return BriefResponse.model_validate(brief, from_attributes=True)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_events(run_id: int, user_id: str):
    db = SessionLocal()
    try:
        run = db.execute(select(Run).where(Run.id == run_id, Run.user_id == int(user_id))).scalar_one_or_none()
        if run is None:
            yield _sse({"node": "error", "status": "error", "message": "Không tìm thấy run."})
            return

        last_id = 0
        while True:
            # Run events are the cross-process source of truth. The API and
            # worker do not share memory, so an in-process asyncio.Queue would
            # leave SSE clients hanging after deployment.
            db.expire_all()
            events = (
                db.execute(
                    select(RunNodeEvent)
                    .where(RunNodeEvent.run_id == run_id, RunNodeEvent.id > last_id)
                    .order_by(RunNodeEvent.id)
                )
                .scalars()
                .all()
            )
            for event in events:
                last_id = event.id
                yield _sse(_event_payload(event))

            db.refresh(run)
            if run.status in _TERMINAL_STATUSES:
                return
            await asyncio.sleep(get_settings().sse_poll_seconds)
    finally:
        db.close()


@router.get("/{run_id}/events")
@limiter.limit("30/minute")
async def stream_run_events(
    request: Request,
    run_id: int,
    user_id: str = Depends(get_current_user_id),
) -> StreamingResponse:
    return StreamingResponse(_stream_events(run_id, user_id), media_type="text/event-stream")
