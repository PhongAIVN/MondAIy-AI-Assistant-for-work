"""Dự án — lớp sắp xếp hội thoại do người dùng tự tạo.

Chỉ để gom nhóm: agent KHÔNG đọc mô tả dự án khi trả lời (quyết định của chủ
sở hữu sản phẩm, 2026-08-22). Nhờ vậy gán nhầm dự án không làm hỏng câu trả
lời, chỉ làm rối chỗ cất.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.api.rate_limit import limiter
from src.db import get_db
from src.models.conversation import Conversation, ConversationMessage
from src.models.meeting_note import MeetingNote
from src.models.project import Project
from src.models.schemas import (
    ProjectContextResponse,
    ProjectConversationSummary,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectMeetingSummary,
    ProjectOverviewResponse,
    ProjectResponse,
    ProjectSuggestionResponse,
    ProjectUpdateRequest,
)
from src.services.project_context import build_project_context
from src.services.project_matching import suggest_project
from src.services.project_summary import build_overview

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


def _owned(db: Session, project_id: int, user_id: str) -> Project:
    row = db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == str(user_id))
    ).scalar_one_or_none()
    if row is None:
        # 404 chứ không 403: không tiết lộ dự án đó có tồn tại của người khác hay không.
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    return row


def _to_response(db: Session, project: Project) -> ProjectResponse:
    count = db.scalar(
        select(func.count(Conversation.id)).where(Conversation.project_id == project.id)
    )
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        color=project.color,
        conversation_count=int(count or 0),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _meeting_summary(row: MeetingNote) -> ProjectMeetingSummary:
    return ProjectMeetingSummary.model_validate(row, from_attributes=True)


@router.get("", response_model=ProjectListResponse)
def list_projects(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectListResponse:
    rows = (
        db.execute(
            select(Project).where(Project.user_id == str(user_id)).order_by(Project.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return ProjectListResponse(projects=[_to_response(db, row) for row in rows])


@router.post("", response_model=ProjectResponse, status_code=201)
@limiter.limit("30/minute")
def create_project(
    request: Request,
    body: ProjectCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    row = Project(
        user_id=str(user_id),
        name=body.name.strip(),
        description=(body.description or "").strip(),
        color=body.color,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Ràng buộc uq_project_user_name — trả 409 để client hiện thông báo
        # đúng chỗ thay vì nuốt thành 500.
        db.rollback()
        raise HTTPException(status_code=409, detail="Bạn đã có dự án trùng tên.") from None
    db.refresh(row)
    return _to_response(db, row)


@router.patch("/{project_id}", response_model=ProjectResponse)
@limiter.limit("60/minute")
def update_project(
    request: Request,
    project_id: int,
    body: ProjectUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    row = _owned(db, project_id, user_id)
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip()
    if body.color is not None:
        row.color = body.color
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bạn đã có dự án trùng tên.") from None
    db.refresh(row)
    return _to_response(db, row)


@router.delete("/meeting-notes/{note_id}", status_code=204)
def remove_meeting_note(request: Request, note_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> None:
    note = db.execute(select(MeetingNote).where(MeetingNote.id == note_id, MeetingNote.user_id == str(user_id))).scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi chú cuộc họp.")
    note.project_id = None
    db.commit()


@router.delete("/{project_id}", status_code=204)
@limiter.limit("30/minute")
def delete_project(
    request: Request,
    project_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    row = _owned(db, project_id, user_id)
    # Xoá dự án KHÔNG xoá hội thoại — người dùng chỉ bỏ cách sắp xếp, không phải
    # bỏ nội dung. Gỡ tham chiếu để hội thoại quay về nhóm chưa xếp.
    db.execute(
        Conversation.__table__.update()
        .where(Conversation.project_id == row.id)
        .values(project_id=None)
    )
    db.execute(MeetingNote.__table__.update().where(MeetingNote.project_id == row.id).values(project_id=None))
    db.delete(row)
    db.commit()


@router.post("/{project_id}/conversations/{conversation_id}", response_model=ProjectResponse)
@limiter.limit("60/minute")
def add_conversation(
    request: Request,
    project_id: int,
    conversation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = _owned(db, project_id, user_id)
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == str(user_id)
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    conversation.project_id = project.id
    db.commit()
    db.refresh(project)
    return _to_response(db, project)


@router.post("/{project_id}/meeting-notes/{note_id}", response_model=ProjectResponse)
def add_meeting_note(request: Request, project_id: int, note_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> ProjectResponse:
    project = _owned(db, project_id, user_id)
    note = db.execute(select(MeetingNote).where(MeetingNote.id == note_id, MeetingNote.user_id == str(user_id))).scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ghi chú cuộc họp.")
    note.project_id = project.id
    db.commit()
    return _to_response(db, project)


@router.delete("/conversations/{conversation_id}", status_code=204)
@limiter.limit("60/minute")
def remove_conversation(
    request: Request,
    conversation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == str(user_id)
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    conversation.project_id = None
    db.commit()


@router.get("/{project_id}/overview", response_model=ProjectOverviewResponse)
async def get_overview(
    project_id: int,
    refresh: bool = False,
    language: str = "vi",
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectOverviewResponse:
    """Hội thoại trong dự án + tóm tắt điểm chung.

    Tóm tắt có cache khoá bằng dấu vân tay tập hội thoại (xem
    project_summary.py) nên mở lại trang không tốn thêm lượt gọi LLM. `refresh`
    ép sinh lại khi người dùng tự bấm.
    """
    project = _owned(db, project_id, user_id)
    rows = (
        db.execute(
            select(Conversation)
            .where(Conversation.project_id == project.id)
            .where(Conversation.user_id == str(user_id))
            .order_by(Conversation.updated_at.desc())
        )
        .scalars()
        .all()
    )
    counts = dict(
        db.execute(
            select(ConversationMessage.conversation_id, func.count(ConversationMessage.id))
            .where(ConversationMessage.conversation_id.in_([row.id for row in rows] or [0]))
            .group_by(ConversationMessage.conversation_id)
        ).all()
    )

    overview = await build_overview(db, project, language=language, force=refresh)
    context = build_project_context(db, project, str(user_id))

    return ProjectOverviewResponse(
        project=_to_response(db, project),
        conversations=[
            ProjectConversationSummary(
                id=row.id,
                title=row.title,
                message_count=int(counts.get(row.id, 0)),
                updated_at=row.updated_at,
            )
            for row in rows
        ],
        summary=overview.summary,
        summary_updated_at=overview.updated_at,
        meetings=[_meeting_summary(row) for row in context.meetings],
        meeting_count=len(context.meetings),
    )


@router.get("/{project_id}/context", response_model=ProjectContextResponse)
def get_project_context(project_id: int, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)) -> ProjectContextResponse:
    project = _owned(db, project_id, user_id)
    context = build_project_context(db, project, str(user_id))
    counts = dict(db.execute(select(ConversationMessage.conversation_id, func.count(ConversationMessage.id)).where(ConversationMessage.conversation_id.in_([row.id for row in context.conversations] or [0])).group_by(ConversationMessage.conversation_id)).all())
    return ProjectContextResponse(
        project_id=project.id,
        conversations=[ProjectConversationSummary(id=row.id, title=row.title, message_count=int(counts.get(row.id, 0)), updated_at=row.updated_at) for row in context.conversations],
        meetings=[_meeting_summary(row) for row in context.meetings],
    )


@router.get("/suggestion/{conversation_id}", response_model=ProjectSuggestionResponse)
def get_suggestion(
    conversation_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ProjectSuggestionResponse:
    """Dự án khớp nhất cho hội thoại này, nếu đủ chắc.

    Không bao giờ ném lỗi vì chuyện gợi ý: đây là tiện ích phụ trên màn hình
    chat, hỏng nó không được chắn đường người dùng đang trò chuyện.
    """
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == str(user_id)
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")

    try:
        suggestion = suggest_project(db, str(user_id), conversation)
    except Exception:  # noqa: BLE001 - gợi ý hỏng không được chắn màn hình chat
        logger.exception("Gợi ý dự án lỗi cho hội thoại %s", conversation_id)
        return ProjectSuggestionResponse(suggestion=None)

    if suggestion is None:
        return ProjectSuggestionResponse(suggestion=None)
    return ProjectSuggestionResponse(
        suggestion={
            "projectId": suggestion.project_id,
            "projectName": suggestion.project_name,
            "score": suggestion.score,
            "method": suggestion.method,
        }
    )
