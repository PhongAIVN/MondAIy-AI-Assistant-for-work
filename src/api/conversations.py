"""Phiên chat lưu phía server, tách riêng theo từng user.

Mọi endpoint ở đây đều lọc theo user_id lấy từ token. Không có đường nào đọc
được hội thoại của người khác, kể cả khi biết đúng id — xem `_lay_hoi_thoai`.
"""

import asyncio
import hashlib
import json
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.agents.graph import agent
from src.agents.tools.productivity_tool import execute_productivity_action
from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.config import get_settings
from src.db import SessionLocal, get_db
from src.models.conversation import Conversation, ConversationMessage
from src.models.learning import AssistantContextRef
from src.models.schemas import (
    AppendTurnRequest,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationFavoriteRequest,
    ConversationListResponse,
    ConversationSummary,
    ConversationTurn,
    FeedbackRequest,
    GoogleSheetsTaskProposal,
    RenameConversationRequest,
    SendMessageRequest,
    SendMessageResponse,
    ShareConversationRequest,
    ShareConversationResponse,
    TaskDraftActionResponse,
    TaskSuggestionAction,
)
from src.models.task import Task
from src.models.task_evidence import TaskEvidence
from src.services import reminders as reminders_service
from src.services import schedule_conflicts as schedule_conflicts_service
from src.services.agent_stream import stream_agent_execution
from src.services.attribution import provider_label
from src.services.connections import preferred_connection
from src.services.conversation_title import suggest_conversation_title
from src.services.memory_capture import (
    aenrich_long_term_memory,
    capture_long_term_memory,
    capture_regex_facts,
)
from src.services.memory_store import (
    arecall,
    backfill_memory_embeddings,
    embed_memory_text,
    expand_related_memories,
    recall,
    to_prompt_payload,
)
from src.services.profile_memory import load_user_profile
from src.services.scope import apply_search_scope, reset_agent_scope
from src.services.task_ownership import personal_task_ids
from src.services.task_planning import build_task_planning_reply, is_task_planning_request
from src.services.usage_quota import consume_llm_question
from src.services.working_memory import (
    VERBATIM_TURNS,
    build_working_memory,
    load_recent_turns,
    refresh_conversation_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Tiêu đề lấy từ câu hỏi đầu tiên, cắt cho vừa cột danh sách.
_DAI_TIEU_DE = 60

# Số fact dài hạn kèm vào mỗi lượt. Ít hơn thì agent quên, nhiều hơn thì phần
# trí nhớ lấn chỗ của bằng chứng thật trong ngân sách prompt.
_SO_MEMORY_DAI_HAN = 8
_TASK_CONFIRMATION = re.compile(
    r"(?i)^\s*(?:ok|oke|okay|ừ|uh|được|đồng ý|xác nhận|confirm|yes|chuẩn|làm đi)\s*[.!]?\s*$"
)
_TASK_CARD_LIMIT = 8
_TASK_STALE_AFTER = timedelta(days=7)
_CALENDAR_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}
_CALENDAR_DRAFT_REQUEST = re.compile(
    r"(?i)(?:tạo|thêm|đặt|lên\s+lịch|schedule|create|add)"
    r".*(?:lịch|calendar|sự kiện|cuộc hẹn|meeting|event|nhắc(?:\s+việc)?|reminder)"
)


def _persist_assistant_context_ref(
    db: Session,
    assistant_message: ConversationMessage,
    *,
    memory_version_ids: list[int] | None = None,
) -> None:
    """Ghi provenance phiên bản cùng transaction với lượt assistant.

    S1b mới có long-term memory; style và skill sẽ được nối vào cùng contract
    khi S3/S4 có version store. Không lưu prompt đã compile hay raw context.
    """
    db.add(
        AssistantContextRef(
            assistant_message_id=assistant_message.id,
            memory_version_ids=memory_version_ids or [],
            style_version_ids=[],
            skill_version_ids=[],
        )
    )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _pending_productivity_action(history: list[dict]) -> dict | None:
    """Only the immediately preceding assistant clarification remains active."""
    if not history or history[-1].get("role") != "assistant":
        return None
    action = (history[-1].get("extras") or {}).get("productivityAction")
    if isinstance(action, dict) and action.get("status") == "needs_clarification":
        return action
    return None


def _pending_approval_from_confirmation(
    query: str,
    history: list[ConversationMessage],
) -> dict | None:
    """Giữ câu "oke" khỏi rơi sang Discord khi action đang chờ nút duyệt.

    Nút là ranh giới xác nhận có chủ đích; một câu đồng ý ngắn không tự
    thực hiện side effect. Thay vì gọi agent và bị lưới an toàn đẩy sang
    Discord, API lặp lại đúng action đã ký để giao diện hiện nút lại.
    """
    if not _TASK_CONFIRMATION.fullmatch(query) or not history:
        return None
    previous = history[-1]
    if previous.role != "assistant":
        return None
    action = (previous.extras or {}).get("productivityAction")
    if isinstance(action, dict) and action.get("status") == "pending_approval":
        return action
    return None


async def _bao_tri_bo_nho(conversation_id: int, user_id: str) -> None:
    """Nén tóm tắt và nhúng memory mới, chạy sau khi đã trả lời xong.

    Cơ chế: mở session riêng vì session của request đã đóng khi background task
    chạy, rồi làm hai việc nền của lớp bộ nhớ. Nhúng đẩy sang worker thread vì
    `backfill_memory_embeddings` gọi HTTP có chặn (ADR-006 §5).

    Hai việc tách try riêng: nén hỏng không được kéo theo nhúng, và ngược lại.
    Lỗi ở đây không nổi lên người dùng — câu trả lời đã gửi đi rồi.
    """
    db = SessionLocal()
    try:
        try:
            await refresh_conversation_summary(db, conversation_id, user_id)
        except Exception:
            logger.exception("Không nén được tóm tắt hội thoại %s", conversation_id)
        try:
            await asyncio.to_thread(backfill_memory_embeddings, db, user_id)
        except Exception:
            logger.exception("Không nhúng được memory của user %s", user_id)
    finally:
        db.close()


async def _lam_giau_bo_nho(
    user_id: str,
    text: str,
    conversation_id: int,
    message_id: int,
    skip_predicates: frozenset[str],
) -> None:
    """Làm giàu bộ nhớ dài hạn bằng LLM nhỏ, chạy sau khi phản hồi đã tới user.

    Cơ chế: mở session riêng vì session của request đã đóng khi task chạy
    (cùng mẫu với `_bao_tri_bo_nho`). Provider chậm chỉ làm trễ việc ghi fact,
    không bao giờ cộng độ trễ vào lượt chat. Mọi lỗi chỉ log — enrichment là
    best-effort.
    """
    db = SessionLocal()
    try:
        await aenrich_long_term_memory(
            db,
            user_id,
            text,
            skip_predicates=frozenset(skip_predicates),
            source_conversation_id=conversation_id,
            source_message_id=message_id,
        )
    except Exception:
        logger.exception("Không làm giàu được bộ nhớ dài hạn cho user %s", user_id)
    finally:
        db.close()


def _google_sheet_proposals_from_agent_result(
    result: dict,
) -> list[tuple[str, GoogleSheetsTaskProposal]]:
    """Return validated Sheet proposals together with their workbook identity."""
    proposals: list[tuple[str, GoogleSheetsTaskProposal]] = []
    for observation in result.get("observations") or []:
        if observation.get("name") != "google_sheets_task_proposals":
            continue
        raw_output = observation.get("output") or {}
        try:
            output = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
        except json.JSONDecodeError:
            continue
        if not isinstance(output, dict) or output.get("error"):
            continue
        workbook = str(output.get("spreadsheet_url") or "").strip()
        if not workbook:
            continue
        for raw in output.get("proposals") or []:
            try:
                proposals.append((workbook, GoogleSheetsTaskProposal.model_validate(raw)))
            except ValidationError:
                continue
    return proposals


def _google_sheet_workbook_identity(spreadsheet_url: str) -> str:
    """Keep idempotency stable across edit/share/gid variants of one URL."""
    match = re.search(r"/spreadsheets/d/([^/?#]+)", spreadsheet_url)
    return match.group(1) if match else spreadsheet_url


def _task_suggestions_from_agent_result(result: dict) -> list[dict]:
    """Đọc observation của suggest_tasks thành hợp đồng thẻ gợi ý cho giao diện.

    Không chạm DB, khác hẳn `_task_drafts_from_agent_result`: suggest_tasks
    không tạo dòng nào nên ở đây cũng không có `id` để tra. Chuẩn hoá lại một
    lần nữa qua `TaskSuggestionAction` để dữ liệu model sinh ra không đi thẳng
    xuống giao diện mà chưa qua schema.
    """
    sheet_titles = {proposal.title.casefold() for _, proposal in _google_sheet_proposals_from_agent_result(result)}
    suggestions: list[dict] = []
    seen: set[str] = set()
    for observation in result.get("observations") or []:
        if observation.get("name") != "suggest_tasks":
            continue
        try:
            output = json.loads(observation.get("output") or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        if output.get("status") != "suggested":
            continue
        for raw in output.get("suggestions") or []:
            try:
                item = TaskSuggestionAction.model_validate(raw)
            except ValidationError:
                continue
            # Google Sheet proposals are persisted as proposed Mondaiy tasks
            # in this same response. Do not also render the generic Add-task
            # suggestion generated by the model for the same row.
            if item.title.casefold() in sheet_titles:
                continue
            # Vòng agent có thể gọi suggest_tasks nhiều lượt (mail rồi Jira);
            # khử trùng theo tiêu đề để người dùng không thấy hai thẻ y hệt.
            key = item.title.casefold()
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(item.model_dump(by_alias=True, mode="json"))
    return suggestions


def _message_extras(
    result: dict,
    task_drafts: list[dict] | None = None,
    task_suggestions: list[dict] | None = None,
    task_backlog_count: int = 0,
) -> dict | None:
    """Gói phần dữ liệu kèm câu trả lời để lưu và trả về cho giao diện.

    Nguồn được lưu cùng lượt trả lời chứ không dựng lại lúc đọc, vì kho dữ liệu
    có thể đã đổi: mở lại hội thoại cũ phải thấy đúng những nguồn đã dùng lúc
    trả lời, không phải nguồn tốt nhất của hôm nay.
    """
    metadata = result.get("metadata") or {}
    extras: dict = {}
    action = metadata.get("productivity_action")
    if isinstance(action, dict):
        extras["productivityAction"] = action
    sources = metadata.get("sources")
    if isinstance(sources, list) and sources:
        extras["sources"] = sources
    routing = metadata.get("conversational_route")
    if isinstance(routing, dict):
        extras["routing"] = routing
    grounding_status = metadata.get("grounding_status")
    if grounding_status in {"grounded", "uncertain", "abstain", "reject"}:
        # Giữ tín hiệu thiếu bằng chứng cùng lượt trả lời để giao diện có thể
        # mời người dùng chủ động chuyển đúng câu hỏi cho đội ngũ chương trình.
        extras["groundingStatus"] = grounding_status
        used_tools = metadata.get("tool_calls") or []
        program_tools = {"program_information_search", "program_schedule"}
        extras["programQuestionHandoffEligible"] = grounding_status in {"uncertain", "abstain", "reject"} and any(
            tool in program_tools for tool in used_tools if isinstance(tool, str)
        )
    if task_drafts:
        extras["taskDrafts"] = task_drafts
    if task_backlog_count:
        extras["taskBacklogCount"] = task_backlog_count
    if task_suggestions:
        extras["taskSuggestions"] = task_suggestions
    return extras or None


def _owned_productivity_action_message(
    db: Session,
    *,
    conversation_id: int,
    message_id: int,
    user_id: str,
) -> tuple[ConversationMessage, dict]:
    conversation = _lay_hoi_thoai(db, conversation_id, user_id)
    message = db.get(ConversationMessage, message_id)
    if message is None or message.conversation_id != conversation.id or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Không tìm thấy action cần duyệt.")
    action = (message.extras or {}).get("productivityAction")
    if not isinstance(action, dict):
        raise HTTPException(status_code=404, detail="Tin nhắn này không có action cần duyệt.")
    return message, action


def _calendar_write_ready(db: Session, user_id: str) -> bool:
    connection = preferred_connection(db, user_id, "google")
    scopes = set((connection.scopes or "").split()) if connection else set()
    return bool(scopes.intersection(_CALENDAR_WRITE_SCOPES))


def _task_source_label(db: Session, task: Task) -> str:
    """Nhãn nguồn cho 1 task, dựng từ chính bằng chứng đã lưu.

    Nhiều nguồn cùng xác nhận thì gộp thành một nhãn thay vì liệt kê — thẻ chỉ
    có một dòng nhỏ, và "được 2 nguồn xác nhận" mới là điều đáng nói, không
    phải tên từng nền tảng.
    """
    providers = (
        db.execute(select(TaskEvidence.provider).where(TaskEvidence.task_id == task.id).distinct()).scalars().all()
    )
    labels = sorted({provider_label(provider) for provider in providers if provider})
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return f"{len(labels)} nguồn · {', '.join(labels)}"


def _task_draft_payload(db: Session, user_id: str, task: Task, *, calendar_requested: bool = False) -> dict:
    if task.user_id != user_id:
        raise ValueError("Task không thuộc người dùng hiện tại.")
    return TaskDraftActionResponse(
        source_label=_task_source_label(db, task),
        id=task.id,
        title=task.title,
        detail=task.detail,
        due_at=task.due_at,
        all_day=task.all_day,
        status=task.status,
        calendar_write_ready=_calendar_write_ready(db, user_id),
        calendar_event_id=task.calendar_event_id,
        calendar_requested=calendar_requested,
    ).model_dump(by_alias=True, mode="json")


@dataclass(frozen=True)
class _TaskDraftSelection:
    drafts: list[dict]
    backlog_count: int


def _task_drafts_from_agent_result(
    db: Session, user_id: str, result: dict, *, calendar_requested: bool = False
) -> _TaskDraftSelection:
    """Chọn card cần quyết định và đếm chính xác phần backlog bị ẩn.

    ``draft_task`` mang ID vừa tạo nên luôn được ưu tiên. ``list_tasks`` chỉ
    mở tập ``proposed`` thuộc user; task cũ hoặc vượt trần được gộp vào count
    thay vì biến thành một luồng card dài.
    """
    candidate_ids: list[int] = []
    forced_ids: list[int] = []
    include_listed_proposed = False
    for workbook, proposal in _google_sheet_proposals_from_agent_result(result):
        identity = f"{_google_sheet_workbook_identity(workbook)}\n{proposal.external_key}"
        cluster_key = f"gsheet:{hashlib.sha256(identity.encode()).hexdigest()[:56]}"
        task = db.scalar(select(Task).where(Task.user_id == user_id, Task.cluster_key == cluster_key))
        if task is None:
            # Chính sách tin cậy 2026-08-25: proposal có ngày rõ + người nhận
            # khớp (needs_confirmation=False) thì đưa thẳng vào danh sách;
            # còn lại proposed đợi người dùng duyệt.
            task = Task(
                user_id=user_id,
                cluster_key=cluster_key,
                title=proposal.title,
                detail=proposal.detail,
                due_at=proposal.due_at,
                all_day=proposal.all_day,
                ambiguous=proposal.date_ambiguous,
                assignee=proposal.assignee,
                assignee_ambiguous=proposal.match_kind in {"close", "possible"},
                status="proposed" if proposal.needs_confirmation else "confirmed",
                source_count=1,
                signal_strength=1.0,
            )
            db.add(task)
            db.flush()
            if task.status == "confirmed":
                # Cùng side effect với confirm thủ công: nhắc mặc định + phát
                # hiện trùng giờ. Không đụng Google Calendar ở đây.
                reminders_service.generate_default_reminders(db, task)
                reminders_service.detect_schedule_conflicts(db, task)
                schedule_conflicts_service.detect_for_task(db, task)
            db.add(
                TaskEvidence(
                    task_id=task.id,
                    provider="google_sheets",
                    evidence_quote=(proposal.detail or proposal.title).strip(),
                    deep_link=proposal.source_url,
                )
            )
        if task.status == "proposed" and task.id not in candidate_ids:
            candidate_ids.append(task.id)

    for observation in result.get("observations") or []:
        if observation.get("name") == "list_tasks":
            args = observation.get("args") or {}
            status = args.get("status") or "proposed"
            if not args.get("due_before") and not args.get("due_after"):
                include_listed_proposed = include_listed_proposed or status in {"all", "proposed"}
            continue
        if observation.get("name") != "draft_task":
            continue
        try:
            output = json.loads(observation.get("output") or "{}")
            task_id = int(output.get("task_id"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if output.get("status") == "draft_created" and task_id not in forced_ids:
            forced_ids.append(task_id)

    forced_tasks = (
        list(
            db.scalars(
                select(Task).where(
                    Task.id.in_(forced_ids),
                    Task.user_id == user_id,
                    Task.status == "proposed",
                )
            ).all()
        )
        if forced_ids
        else []
    )
    forced_by_id = {task.id: task for task in forced_tasks}
    personal_forced_ids = personal_task_ids(db, user_id, forced_tasks)
    forced = [forced_by_id[task_id] for task_id in forced_ids if task_id in personal_forced_ids]

    candidate_stmt = select(Task).where(Task.user_id == user_id, Task.status == "proposed")
    if not include_listed_proposed and not candidate_ids:
        candidate_tasks = []
    else:
        if not include_listed_proposed:
            candidate_stmt = candidate_stmt.where(Task.id.in_(candidate_ids))
        candidate_tasks = list(
            db.scalars(
                candidate_stmt.order_by(
                    Task.due_at.is_(None),
                    Task.due_at.asc(),
                    Task.signal_strength.desc(),
                    Task.id.asc(),
                )
            ).all()
        )

    personal_candidate_ids = personal_task_ids(db, user_id, candidate_tasks)
    forced_id_set = {task.id for task in forced}
    candidates = [
        task
        for task in candidate_tasks
        if task.id in personal_candidate_ids and task.id not in forced_id_set
    ]
    cutoff = datetime.now(UTC) - _TASK_STALE_AFTER

    def is_stale(task: Task) -> bool:
        due_at = task.due_at
        if due_at is None:
            return False
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        return due_at < cutoff

    eligible = [task for task in candidates if not is_stale(task)]
    selected = eligible[:_TASK_CARD_LIMIT]
    backlog_count = len(candidates) - len(selected)
    drafts = [
        _task_draft_payload(db, user_id, task, calendar_requested=calendar_requested)
        for task in [*forced, *selected]
    ]
    return _TaskDraftSelection(drafts=drafts, backlog_count=backlog_count)


def _task_from_confirmation_context(
    db: Session,
    user_id: str,
    query: str,
    history: list[ConversationMessage],
) -> tuple[Task, ConversationMessage] | None:
    """Resolve a short acknowledgement only against the immediately pending draft."""
    if not _TASK_CONFIRMATION.fullmatch(query) or not history:
        return None
    previous = history[-1]
    if previous.role != "assistant":
        return None

    for draft in reversed((previous.extras or {}).get("taskDrafts") or []):
        try:
            task_id = int(draft.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
        if task is not None and task.status in {"proposed", "confirmed"}:
            return task, previous

    # Backward-compatible repair for replies created before taskDrafts was
    # persisted. Only accept exactly one recent proposed task and only when the
    # previous assistant turn explicitly said it had created a draft.
    previous_text = previous.content.casefold()
    if "bản nháp" not in previous_text and "draft" not in previous_text:
        return None
    last_user = next((turn for turn in reversed(history[:-1]) if turn.role == "user"), None)
    if last_user is None:
        return None
    candidates = list(
        db.scalars(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == "proposed",
                Task.created_at >= last_user.created_at,
            )
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(2)
        ).all()
    )
    return (candidates[0], previous) if len(candidates) == 1 else None


def _confirm_task_from_conversation(
    db: Session,
    user_id: str,
    query: str,
    history: list[ConversationMessage],
) -> tuple[str, list[dict]] | None:
    resolved = _task_from_confirmation_context(db, user_id, query, history)
    if resolved is None:
        return None
    task, previous = resolved
    changed = task.status == "proposed"
    if changed:
        task.status = "confirmed"

    previous_extras = dict(previous.extras or {})
    previous_drafts = list(previous_extras.get("taskDrafts") or [])
    calendar_requested = any(
        str(draft.get("id")) == str(task.id) and bool(draft.get("calendarRequested"))
        for draft in previous_drafts
        if isinstance(draft, dict)
    )
    payload = _task_draft_payload(db, user_id, task, calendar_requested=calendar_requested)
    replaced = False
    for index, draft in enumerate(previous_drafts):
        if str(draft.get("id")) == str(task.id):
            previous_drafts[index] = payload
            replaced = True
    if not replaced:
        previous_drafts.append(payload)
    previous.extras = {**previous_extras, "taskDrafts": previous_drafts}

    if changed:
        response = f"Đã xác nhận task #{task.id} “{task.title}”."
    else:
        response = f"Task #{task.id} “{task.title}” đã được xác nhận trước đó."
    if task.calendar_event_id:
        response += " Task này đã được đồng bộ Google Calendar."
    elif task.due_at is None:
        response += " Task chưa có hạn chót rõ ràng nên chưa thể đồng bộ lịch."
    elif payload["calendarWriteReady"]:
        response += " Bạn có thể bấm “Đồng bộ Google Calendar” ngay bên dưới."
    else:
        response += " Hãy kết nối lại Google để cấp quyền ghi Calendar rồi đồng bộ."
    return response, [payload]


def _lay_hoi_thoai(db: Session, conversation_id: int, user_id: str) -> Conversation:
    """Lấy hội thoại và kiểm chủ sở hữu.

    Hội thoại của người khác trả 404 chứ không phải 403: 403 xác nhận id đó có
    tồn tại, đủ để dò xem người khác đã chat bao nhiêu phiên.
    """
    hoi_thoai = db.get(Conversation, conversation_id)
    if hoi_thoai is None or hoi_thoai.user_id != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    return hoi_thoai


@router.post("", response_model=ConversationDetailResponse, status_code=201)
async def tao_hoi_thoai(
    payload: ConversationCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    """Mở một phiên chat rỗng."""
    title = payload.title
    if not title and payload.initial_question:
        title = await suggest_conversation_title(payload.initial_question)
    hoi_thoai = Conversation(user_id=user_id, title=title or "Hội thoại mới")
    db.add(hoi_thoai)
    db.commit()
    db.refresh(hoi_thoai)
    return ConversationDetailResponse(
        id=hoi_thoai.id,
        title=hoi_thoai.title,
        is_favorite=hoi_thoai.is_favorite,
        created_at=hoi_thoai.created_at,
        updated_at=hoi_thoai.updated_at,
        messages=[],
    )


@router.get("", response_model=ConversationListResponse)
def liet_ke_hoi_thoai(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    """Danh sách phiên chat của chính user này, mới nhất trước."""
    dem = (
        select(
            ConversationMessage.conversation_id.label("conversation_id"),
            func.count(ConversationMessage.id).label("so_luot"),
        )
        .group_by(ConversationMessage.conversation_id)
        .subquery()
    )
    dong = db.execute(
        select(Conversation, func.coalesce(dem.c.so_luot, 0))
        .outerjoin(dem, dem.c.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    ).all()

    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=hoi_thoai.id,
                title=hoi_thoai.title,
                message_count=so_luot,
                project_id=hoi_thoai.project_id,
                is_favorite=hoi_thoai.is_favorite,
                created_at=hoi_thoai.created_at,
                updated_at=hoi_thoai.updated_at,
            )
            for hoi_thoai, so_luot in dong
        ]
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def xem_hoi_thoai(
    conversation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    """Toàn bộ lượt nói trong một phiên."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    luot = (
        db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == hoi_thoai.id)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
        .scalars()
        .all()
    )
    return ConversationDetailResponse(
        id=hoi_thoai.id,
        title=hoi_thoai.title,
        is_favorite=hoi_thoai.is_favorite,
        created_at=hoi_thoai.created_at,
        updated_at=hoi_thoai.updated_at,
        messages=[
            ConversationTurn(
                id=m.id,
                role=m.role,
                content=m.content,
                extras=m.extras,
                feedback=m.feedback,
                created_at=m.created_at,
            )
            for m in luot
        ],
    )


@router.patch("/{conversation_id}/favorite", response_model=ConversationSummary)
def dat_ghim_hoi_thoai(
    conversation_id: int,
    payload: ConversationFavoriteRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationSummary:
    """Lưu trạng thái session được ghim trong Sidebar."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    hoi_thoai.is_favorite = payload.is_favorite
    db.commit()
    db.refresh(hoi_thoai)
    so_luot = db.scalar(
        select(func.count(ConversationMessage.id)).where(ConversationMessage.conversation_id == hoi_thoai.id)
    )
    return ConversationSummary(
        id=hoi_thoai.id,
        title=hoi_thoai.title,
        message_count=so_luot or 0,
        project_id=hoi_thoai.project_id,
        is_favorite=hoi_thoai.is_favorite,
        created_at=hoi_thoai.created_at,
        updated_at=hoi_thoai.updated_at,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def doi_ten_hoi_thoai(
    conversation_id: int,
    payload: RenameConversationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationSummary:
    """Đổi tên một phiên chat."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    hoi_thoai.title = payload.title
    db.commit()
    db.refresh(hoi_thoai)
    so_luot = db.scalar(
        select(func.count(ConversationMessage.id)).where(ConversationMessage.conversation_id == hoi_thoai.id)
    )
    return ConversationSummary(
        id=hoi_thoai.id,
        title=hoi_thoai.title,
        message_count=so_luot or 0,
        project_id=hoi_thoai.project_id,
        is_favorite=hoi_thoai.is_favorite,
        created_at=hoi_thoai.created_at,
        updated_at=hoi_thoai.updated_at,
    )


@router.post("/{conversation_id}/share", response_model=ShareConversationResponse)
def share_hoi_thoai(
    conversation_id: int,
    payload: ShareConversationRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ShareConversationResponse:
    """Set private/public visibility and issue a revocable public token."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    hoi_thoai.share_visibility = payload.visibility
    hoi_thoai.share_token = secrets.token_urlsafe(32) if payload.visibility == "public" else None
    db.commit()
    if payload.visibility == "private":
        return ShareConversationResponse(visibility="private")
    settings = get_settings()
    public_origin = (settings.web_app_public_url or settings.app_public_url).rstrip("/")
    public_url = f"{public_origin}/shared-chat/{hoi_thoai.share_token}"
    return ShareConversationResponse(
        visibility="public",
        public_url=public_url,
        public_token=hoi_thoai.share_token,
    )


@router.post("/{conversation_id}/turns", response_model=ConversationTurn, status_code=201)
def ghi_luot(
    conversation_id: int,
    payload: AppendTurnRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ConversationTurn:
    """Ghi một lượt đã dựng sẵn vào phiên, không gọi agent."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)

    bay_gio = datetime.now(UTC)
    luot = ConversationMessage(
        conversation_id=hoi_thoai.id,
        role=payload.role,
        content=payload.content,
        extras=payload.extras,
        created_at=bay_gio,
    )
    db.add(luot)
    if payload.role == "user":
        db.flush()
        capture_long_term_memory(
            db,
            user_id,
            payload.content,
            source_conversation_id=hoi_thoai.id,
            source_message_id=luot.id,
        )
    elif payload.role == "assistant":
        db.flush()
        _persist_assistant_context_ref(db, luot)
    hoi_thoai.updated_at = bay_gio
    db.commit()
    db.refresh(luot)

    return ConversationTurn(
        id=luot.id,
        role=luot.role,
        content=luot.content,
        extras=luot.extras,
        feedback=luot.feedback,
        created_at=luot.created_at,
    )


@router.patch("/{conversation_id}/messages/{message_id}/feedback", status_code=204)
def danh_gia_luot(
    conversation_id: int,
    message_id: int,
    payload: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    """Ghi nhận người dùng thấy câu trả lời thế nào (FR-035)."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    luot = db.get(ConversationMessage, message_id)
    if luot is None or luot.conversation_id != hoi_thoai.id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt nói.")
    luot.feedback = payload.feedback
    db.commit()


@router.post("/{conversation_id}/messages/{message_id}/productivity-action/approve")
async def approve_productivity_action(
    conversation_id: int,
    message_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Execute the exact server-stored draft after the user presses Approve."""
    message, action = _owned_productivity_action_message(
        db,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if action.get("status") == "created":
        return action
    if action.get("status") == "rejected":
        raise HTTPException(status_code=409, detail="Action này đã bị từ chối.")
    if action.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail="Action chưa sẵn sàng để duyệt.")

    try:
        result = await execute_productivity_action(user_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("status") != "created":
        detail = str(result.get("message") or "Không thực hiện được action.")
        status_code = 409 if "kết nối" in detail.casefold() or "quyền" in detail.casefold() else 502
        raise HTTPException(status_code=status_code, detail=detail)

    updated = {**action, **result, "approved_at": datetime.now(UTC).isoformat()}
    message.extras = {**(message.extras or {}), "productivityAction": updated}
    db.commit()
    return updated


@router.post("/{conversation_id}/messages/{message_id}/productivity-action/reject")
def reject_productivity_action(
    conversation_id: int,
    message_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Reject a proposal without executing any side effect."""
    message, action = _owned_productivity_action_message(
        db,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=user_id,
    )
    if action.get("status") == "rejected":
        return action
    if action.get("status") == "created":
        raise HTTPException(status_code=409, detail="Action đã được thực hiện nên không thể từ chối.")
    if action.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail="Action chưa sẵn sàng để từ chối.")

    updated = {
        **action,
        "status": "rejected",
        "message": "Đã từ chối action. Không có thay đổi nào được thực hiện.",
        "rejected_at": datetime.now(UTC).isoformat(),
    }
    message.extras = {**(message.extras or {}), "productivityAction": updated}
    db.commit()
    return updated


@router.delete("/{conversation_id}", status_code=204)
def xoa_hoi_thoai(
    conversation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    """Xoá hẳn một phiên chat cùng toàn bộ lượt nói của nó."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    # Xoá tay thay vì dựa vào ON DELETE CASCADE: bảng được tạo bằng create_all
    # nên tuỳ lúc mà ràng buộc có thật hay không.
    db.execute(
        delete(AssistantContextRef).where(
            AssistantContextRef.assistant_message_id.in_(
                select(ConversationMessage.id).where(ConversationMessage.conversation_id == hoi_thoai.id)
            )
        )
    )
    db.execute(ConversationMessage.__table__.delete().where(ConversationMessage.conversation_id == hoi_thoai.id))
    db.delete(hoi_thoai)
    db.commit()


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
@limiter.limit("20/minute")
async def gui_tin_nhan(
    request: Request,
    conversation_id: int,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    """Gửi một câu hỏi vào phiên chat và lưu cả câu hỏi lẫn câu trả lời."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)

    cau_hoi = payload.message.strip()
    if not cau_hoi:
        raise HTTPException(status_code=422, detail="Câu hỏi rỗng.")

    # Bộ nhớ ngắn hạn phải dựng trước khi ghi lượt mới, không thì câu vừa hỏi
    # lọt vào phần lịch sử và model thấy nó hai lần.
    bo_nho_ngan_han = build_working_memory(db, hoi_thoai)
    lich_su = bo_nho_ngan_han.turns
    confirmation_history = load_recent_turns(db, hoi_thoai.id, VERBATIM_TURNS)
    pending_approval = _pending_approval_from_confirmation(cau_hoi, confirmation_history)
    confirmation = (
        None
        if pending_approval is not None
        else _confirm_task_from_conversation(db, user_id, cau_hoi, confirmation_history)
    )
    if confirmation is None and pending_approval is None:
        # Câu xác nhận task là một UI action có ngữ cảnh, không gọi LLM và
        # không trừ hạn mức hỏi trong ngày.
        consume_llm_question(db, user_id)

    # Ghi mốc thời gian tường minh. Đọc `.created_at` của một object vừa add mà
    # chưa flush thì vẫn là None, vì default nằm phía Python và chỉ chạy lúc ghi.
    luc_hoi = datetime.now(UTC)
    luot_nguoi = ConversationMessage(conversation_id=hoi_thoai.id, role="user", content=cau_hoi, created_at=luc_hoi)
    db.add(luot_nguoi)
    action_request_id = f"conversation:{hoi_thoai.id}:{uuid.uuid4()}"

    # Phiên chưa có tên thì lấy câu hỏi đầu tiên làm tên.
    if not lich_su and hoi_thoai.title == "Hội thoại mới":
        hoi_thoai.title = cau_hoi[:_DAI_TIEU_DE]

    if pending_approval is not None:
        response = "Action này đang chờ duyệt. Hãy kiểm tra thông tin và bấm Chấp nhận để thực hiện."
        luot_tra_loi = ConversationMessage(
            conversation_id=hoi_thoai.id,
            role="assistant",
            content=response,
            extras={"productivityAction": pending_approval},
            created_at=datetime.now(UTC),
        )
        db.add(luot_tra_loi)
        db.flush()
        _persist_assistant_context_ref(db, luot_tra_loi)
        hoi_thoai.updated_at = luot_tra_loi.created_at
        db.commit()
        db.refresh(luot_tra_loi)
        return SendMessageResponse(
            conversation_id=hoi_thoai.id,
            message_id=luot_tra_loi.id,
            response=response,
            productivity_action=pending_approval,
        )

    if confirmation is not None:
        response, task_drafts = confirmation
        luc_tra_loi = datetime.now(UTC)
        luot_tra_loi = ConversationMessage(
            conversation_id=hoi_thoai.id,
            role="assistant",
            content=response,
            extras={"taskDrafts": task_drafts},
            created_at=luc_tra_loi,
        )
        db.add(luot_tra_loi)
        db.flush()
        _persist_assistant_context_ref(db, luot_tra_loi)
        hoi_thoai.updated_at = luc_tra_loi
        db.commit()
        db.refresh(luot_tra_loi)
        return SendMessageResponse(
            conversation_id=hoi_thoai.id,
            message_id=luot_tra_loi.id,
            response=response,
            task_drafts=[TaskDraftActionResponse.model_validate(item) for item in task_drafts],
        )

    # Chốt lượt của người dùng trước khi gọi agent. Lỗi của trợ lý
    # không được làm câu hỏi vừa gửi biến mất khi transaction rollback.
    db.commit()
    db.refresh(luot_nguoi)

    user_profile = load_user_profile(db, user_id)
    # Trí nhớ dài hạn lấy theo chính câu hỏi, nên mỗi lượt chỉ mang theo phần
    # liên quan thay vì đổ cả kho vào prompt (memory-lifecycle §1). Endpoint này
    # là async nên phải dùng `arecall`: nó đẩy bước nhúng sang worker thread thay
    # vì giữ event loop suốt thời gian chờ HTTP.
    scored_memories = await arecall(db, user_id, cau_hoi, limit=_SO_MEMORY_DAI_HAN, include_candidates=False)
    bo_nho_dai_han = to_prompt_payload(
        scored_memories,
        expand_related_memories(db, user_id, scored_memories),
    )
    memory_version_ids = [item.memory.id for item in scored_memories if item.memory.status in {"confirmed", "disputed"}]
    pending_action = _pending_productivity_action(lich_su)
    apply_search_scope(
        user_id,
        db,
        action_request_id=action_request_id,
        current_query=cau_hoi,
        pending_action=pending_action,
    )
    try:
        ket_qua = await agent.ainvoke(
            {
                "query": cau_hoi,
                "image_data": payload.image_data,
                "history": lich_su,
                "conversation_summary": bo_nho_ngan_han.summary,
                "long_term_memories": bo_nho_dai_han,
                "user_profile": user_profile,
                "pending_productivity_action": pending_action,
            }
        )
    finally:
        reset_agent_scope()

    loi = ket_qua.get("error")
    if loi:
        # Không lưu lượt trả lời hỏng, và không nuốt lỗi thành câu trả lời rỗng.
        # Lượt của người dùng đã commit ở trên nên rollback này chỉ bỏ phần dở
        # dang của lượt trả lời, câu hỏi vẫn còn nguyên trong hội thoại.
        db.rollback()
        logger.warning("Agent hỏng ở hội thoại %s: %s", hoi_thoai.id, loi)
        raise HTTPException(status_code=502, detail=f"Trợ lý chưa trả lời được: {loi}")

    task_selection = _task_drafts_from_agent_result(
        db,
        user_id,
        ket_qua,
        calendar_requested=bool(_CALENDAR_DRAFT_REQUEST.search(cau_hoi)),
    )
    task_drafts = task_selection.drafts
    task_suggestions = _task_suggestions_from_agent_result(ket_qua)
    luc_tra_loi = datetime.now(UTC)
    luot_tra_loi = ConversationMessage(
        conversation_id=hoi_thoai.id,
        role="assistant",
        content=ket_qua.get("response", ""),
        analysis=ket_qua.get("analysis") or None,
        extras=_message_extras(
            ket_qua,
            task_drafts,
            task_suggestions,
            task_backlog_count=task_selection.backlog_count,
        ),
        created_at=luc_tra_loi,
    )
    db.add(luot_tra_loi)
    # Ghi trí nhớ dài hạn từ chính lượt của người dùng. Flush trước để bằng
    # chứng trỏ được về đúng id của lượt đó chứ không chỉ về cả hội thoại.
    # Chỉ chạy phần regex deterministic inline; phần LLM đẩy xuống background
    # vì provider chậm từng cộng thẳng 6s vào lượt chat (sự cố 24/08).
    db.flush()
    _persist_assistant_context_ref(db, luot_tra_loi, memory_version_ids=memory_version_ids)
    _, skip_predicates = capture_regex_facts(
        db,
        user_id,
        cau_hoi,
        source_conversation_id=hoi_thoai.id,
        source_message_id=luot_nguoi.id,
    )
    hoi_thoai.updated_at = luc_tra_loi
    db.commit()
    db.refresh(luot_tra_loi)

    # Enrichment LLM và nén đều chạy sau khi response đã đi, nên không cộng
    # độ trễ vào câu trả lời. Enrichment đứng trước để nén nhúng luôn cả fact
    # mới ghi được trong lượt này.
    background_tasks.add_task(
        _lam_giau_bo_nho,
        user_id,
        cau_hoi,
        hoi_thoai.id,
        luot_nguoi.id,
        skip_predicates,
    )
    background_tasks.add_task(_bao_tri_bo_nho, hoi_thoai.id, user_id)

    return SendMessageResponse(
        conversation_id=hoi_thoai.id,
        message_id=luot_tra_loi.id,
        response=luot_tra_loi.content,
        analysis=luot_tra_loi.analysis or "",
        productivity_action=(luot_tra_loi.extras or {}).get("productivityAction"),
        sources=(luot_tra_loi.extras or {}).get("sources") or [],
        task_drafts=[TaskDraftActionResponse.model_validate(item) for item in task_drafts],
        task_backlog_count=task_selection.backlog_count,
        task_suggestions=[TaskSuggestionAction.model_validate(item) for item in task_suggestions],
    )


@router.post("/{conversation_id}/messages/stream")
@limiter.limit("20/minute")
def gui_tin_nhan_stream(
    request: Request,
    conversation_id: int,
    payload: SendMessageRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream câu trả lời qua SSE và lưu cùng contract với endpoint thường."""
    hoi_thoai = _lay_hoi_thoai(db, conversation_id, user_id)
    cau_hoi = payload.message.strip()
    if not cau_hoi:
        raise HTTPException(status_code=422, detail="Câu hỏi rỗng.")

    bo_nho_ngan_han = build_working_memory(db, hoi_thoai)
    lich_su = bo_nho_ngan_han.turns
    confirmation_history = load_recent_turns(db, hoi_thoai.id, VERBATIM_TURNS)
    pending_approval = _pending_approval_from_confirmation(cau_hoi, confirmation_history)
    confirmation = (
        None
        if pending_approval is not None
        else _confirm_task_from_conversation(db, user_id, cau_hoi, confirmation_history)
    )
    if confirmation is None and pending_approval is None:
        consume_llm_question(db, user_id)

    luc_hoi = datetime.now(UTC)
    luot_nguoi = ConversationMessage(
        conversation_id=hoi_thoai.id,
        role="user",
        content=cau_hoi,
        created_at=luc_hoi,
    )
    db.add(luot_nguoi)
    action_request_id = f"conversation:{hoi_thoai.id}:{uuid.uuid4()}"
    if not lich_su and hoi_thoai.title == "Hội thoại mới":
        hoi_thoai.title = cau_hoi[:_DAI_TIEU_DE]

    if pending_approval is not None:
        response = "Action này đang chờ duyệt. Hãy kiểm tra thông tin và bấm Chấp nhận để thực hiện."
        luot_tra_loi = ConversationMessage(
            conversation_id=hoi_thoai.id,
            role="assistant",
            content=response,
            extras={"productivityAction": pending_approval},
            created_at=datetime.now(UTC),
        )
        db.add(luot_tra_loi)
        db.flush()
        _persist_assistant_context_ref(db, luot_tra_loi)
        hoi_thoai.updated_at = luot_tra_loi.created_at
        db.commit()
        db.refresh(luot_tra_loi)

        async def pending_generate():
            yield _sse("progress", {"phase": "responding"})
            yield _sse("token", {"delta": response})
            yield _sse(
                "done",
                {
                    "conversationId": hoi_thoai.id,
                    "messageId": luot_tra_loi.id,
                    "response": response,
                    "analysis": "",
                    "productivityAction": pending_approval,
                    "taskDrafts": [],
                    "taskBacklogCount": 0,
                },
            )

        return StreamingResponse(
            pending_generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    if confirmation is not None:
        response, task_drafts = confirmation
        luc_tra_loi = datetime.now(UTC)
        luot_tra_loi = ConversationMessage(
            conversation_id=hoi_thoai.id,
            role="assistant",
            content=response,
            extras={"taskDrafts": task_drafts},
            created_at=luc_tra_loi,
        )
        db.add(luot_tra_loi)
        db.flush()
        _persist_assistant_context_ref(db, luot_tra_loi)
        hoi_thoai.updated_at = luc_tra_loi
        db.commit()
        db.refresh(luot_tra_loi)

        async def confirm_generate():
            yield _sse("progress", {"phase": "responding"})
            yield _sse("token", {"delta": response})
            yield _sse(
                "done",
                {
                    "conversationId": hoi_thoai.id,
                    "messageId": luot_tra_loi.id,
                    "response": response,
                    "analysis": "",
                    "taskDrafts": task_drafts,
                    "taskBacklogCount": 0,
                },
            )

        return StreamingResponse(
            confirm_generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    # Chốt lượt người dùng trước khi stream để lỗi trong generator không
    # rollback và làm mất câu hỏi đã hiển thị trên giao diện.
    db.commit()
    db.refresh(luot_nguoi)

    user_profile = load_user_profile(db, user_id)
    # Endpoint này khai báo sync nên FastAPI đã chạy nó trong threadpool: nhúng
    # có chặn ở đây không giữ event loop, khác với endpoint async bên trên.
    scored_memories = recall(
        db,
        user_id,
        cau_hoi,
        limit=_SO_MEMORY_DAI_HAN,
        include_candidates=False,
        query_embedding=embed_memory_text(cau_hoi),
    )
    bo_nho_dai_han = to_prompt_payload(
        scored_memories,
        expand_related_memories(db, user_id, scored_memories),
    )
    memory_version_ids = [item.memory.id for item in scored_memories if item.memory.status in {"confirmed", "disputed"}]
    pending_action = _pending_productivity_action(lich_su)

    async def generate():
        if is_task_planning_request(cau_hoi):
            try:
                yield _sse("progress", {"phase": "thinking"})
                ket_qua = await build_task_planning_reply(db, user_id)
                response = ket_qua["response"]
                yield _sse("progress", {"phase": "responding"})
                yield _sse("token", {"delta": response})
                luc_tra_loi = datetime.now(UTC)
                luot_tra_loi = ConversationMessage(
                    conversation_id=hoi_thoai.id,
                    role="assistant",
                    content=response,
                    analysis=ket_qua.get("analysis") or None,
                    extras={"groundingStatus": "grounded"},
                    created_at=luc_tra_loi,
                )
                db.add(luot_tra_loi)
                db.flush()
                _persist_assistant_context_ref(db, luot_tra_loi, memory_version_ids=memory_version_ids)
                hoi_thoai.updated_at = luc_tra_loi
                db.commit()
                yield _sse("done", {
                    "conversationId": hoi_thoai.id, "messageId": luot_tra_loi.id,
                    "response": response, "analysis": luot_tra_loi.analysis or "",
                    "taskDrafts": [], "taskSuggestions": [], "groundingStatus": "grounded",
                })
            except Exception as exc:
                db.rollback()
                logger.exception("Task planning hỏng ở hội thoại %s", hoi_thoai.id)
                yield _sse("error", {"message": "Trợ lý chưa lập được kế hoạch.", "code": type(exc).__name__})
            return

        apply_search_scope(
            user_id,
            db,
            action_request_id=action_request_id,
            current_query=cau_hoi,
            pending_action=pending_action,
        )
        try:
            ket_qua: dict = {}
            async for item in stream_agent_execution(
                agent,
                {
                    "query": cau_hoi,
                    "image_data": payload.image_data,
                    "history": lich_su,
                    "conversation_summary": bo_nho_ngan_han.summary,
                    "long_term_memories": bo_nho_dai_han,
                    "user_profile": user_profile,
                    "pending_productivity_action": pending_action,
                },
            ):
                if item["event"] in {"progress", "token"}:
                    yield _sse(item["event"], item["data"])
                elif item["event"] == "result":
                    ket_qua = item["data"]

            loi = ket_qua.get("error")
            if loi:
                db.rollback()
                logger.warning("Agent hỏng ở stream hội thoại %s: %s", hoi_thoai.id, loi)
                yield _sse("error", {"message": f"Trợ lý chưa trả lời được: {loi}"})
                return

            response = ket_qua.get("response", "")
            task_selection = _task_drafts_from_agent_result(
                db,
                user_id,
                ket_qua,
                calendar_requested=bool(_CALENDAR_DRAFT_REQUEST.search(cau_hoi)),
            )
            task_drafts = task_selection.drafts
            task_suggestions = _task_suggestions_from_agent_result(ket_qua)
            luc_tra_loi = datetime.now(UTC)
            luot_tra_loi = ConversationMessage(
                conversation_id=hoi_thoai.id,
                role="assistant",
                content=response,
                analysis=ket_qua.get("analysis") or None,
                extras=_message_extras(
                    ket_qua,
                    task_drafts,
                    task_suggestions,
                    task_backlog_count=task_selection.backlog_count,
                ),
                created_at=luc_tra_loi,
            )
            db.add(luot_tra_loi)
            db.flush()
            _persist_assistant_context_ref(db, luot_tra_loi, memory_version_ids=memory_version_ids)
            # Chỉ phần regex chạy inline trước commit; LLM enrichment chờ sau
            # `done` với session riêng để không giữ stream thêm khi provider
            # chậm (sự cố 24/08).
            _, skip_predicates = capture_regex_facts(
                db,
                user_id,
                cau_hoi,
                source_conversation_id=hoi_thoai.id,
                source_message_id=luot_nguoi.id,
            )
            hoi_thoai.updated_at = luc_tra_loi
            db.commit()
            db.refresh(luot_tra_loi)
            yield _sse(
                "done",
                {
                    "conversationId": hoi_thoai.id,
                    "messageId": luot_tra_loi.id,
                    "response": response,
                    "analysis": luot_tra_loi.analysis or "",
                    "productivityAction": (luot_tra_loi.extras or {}).get("productivityAction"),
                    "sources": (luot_tra_loi.extras or {}).get("sources") or [],
                    "groundingStatus": (luot_tra_loi.extras or {}).get("groundingStatus"),
                    "programQuestionHandoffEligible": (luot_tra_loi.extras or {}).get(
                        "programQuestionHandoffEligible", False
                    ),
                    "taskDrafts": task_drafts,
                    "taskBacklogCount": task_selection.backlog_count,
                    "taskSuggestions": task_suggestions,
                },
            )
            # Nén sau khi đã bắn `done`: client coi như xong, phần này chỉ dọn
            # bộ nhớ ngắn hạn cho lượt sau. Enrichment LLM chạy trước nén để
            # fact mới được nhúng luôn trong lượt này.
            await _lam_giau_bo_nho(
                user_id,
                cau_hoi,
                hoi_thoai.id,
                luot_nguoi.id,
                skip_predicates,
            )
            await _bao_tri_bo_nho(hoi_thoai.id, user_id)
        except Exception as exc:
            db.rollback()
            logger.exception("Streaming agent hỏng ở hội thoại %s", hoi_thoai.id)
            yield _sse("error", {"message": "Trợ lý chưa trả lời được.", "code": type(exc).__name__})
        finally:
            reset_agent_scope()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
