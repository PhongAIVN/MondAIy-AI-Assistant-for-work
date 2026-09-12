"""API quản trị kho thông tin chương trình và hàng chờ người trả lời."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import require_admin
from src.db import get_db
from src.models.program_information import ProgramInformationItem, ProgramInformationRequest
from src.models.program_information_schemas import (
    AdminProgramInformationCreateRequest,
    AdminProgramInformationUpdateRequest,
    ExpectedVersionRequest,
    HumanInformationRequestList,
    HumanInformationRequestResponse,
    ProgramInformationItemResponse,
    ProgramInformationListResponse,
    ResolveHumanInformationRequest,
)
from src.models.user import User
from src.services.program_cohorts import configured_program_cohort_slug, normalize_program_cohort_slug
from src.services.program_information import (
    InvalidProgramInformationError,
    VersionConflictError,
    archive_information_item,
    create_information_item,
    get_version,
    list_admin_information,
    list_human_requests,
    publish_information_item,
    resolve_human_request,
    update_information_item,
)

router = APIRouter(
    prefix="/admin/program-information",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _configured_item(db: Session, item_id: int) -> ProgramInformationItem:
    item = db.get(ProgramInformationItem, item_id)
    if item is None or normalize_program_cohort_slug(item.cohort_slug) != configured_program_cohort_slug():
        raise HTTPException(status_code=404, detail="Thông tin chương trình không tồn tại.")
    return item


def _to_response(item: ProgramInformationItem, *, db: Session) -> ProgramInformationItemResponse:
    version = get_version(db, item, published=False)
    return ProgramInformationItemResponse(
        id=item.id,
        cohort_slug=item.cohort_slug,
        category=item.category,
        visibility=item.visibility,
        status=item.status,
        version=version.version,
        published_version=item.published_version,
        title=version.title,
        body=version.body,
        aliases=list(version.aliases or []),
        source_url=version.source_url,
        valid_from=version.valid_from,
        valid_to=version.valid_to,
        content_hash=version.content_hash,
        updated_at=version.created_at,
        published_at=item.published_at,
    )


def _conflict(exc: VersionConflictError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/human-requests", response_model=HumanInformationRequestList)
def get_human_request_queue(
    status: Literal["open", "resolved"] | None = Query(default="open"),
    db: Session = Depends(get_db),
) -> HumanInformationRequestList:
    requests = list_human_requests(db, cohort_slug=configured_program_cohort_slug(), status=status)
    # Cố ý không trả requester_id, email, profile hay lịch sử hội thoại.
    items = [
        HumanInformationRequestResponse(
            id=request.id,
            status=request.status,
            shared_question=request.shared_question,
            created_at=request.created_at,
            resolved_item_id=request.resolved_item_id,
        )
        for request in requests
    ]
    return HumanInformationRequestList(items=items, total=len(items))


@router.post(
    "/human-requests/{request_id}/resolve",
    response_model=HumanInformationRequestResponse,
)
def resolve_human_request_admin(
    request_id: int,
    payload: ResolveHumanInformationRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> HumanInformationRequestResponse:
    request = db.get(ProgramInformationRequest, request_id)
    cohort = configured_program_cohort_slug()
    if request is None or normalize_program_cohort_slug(request.cohort_slug) != cohort:
        raise HTTPException(status_code=404, detail="Yêu cầu không tồn tại.")
    item = _configured_item(db, payload.item_id)
    try:
        resolved = resolve_human_request(
            db,
            request,
            item,
            expected_version=payload.expected_version,
            actor_id=str(actor.id),
        )
    except VersionConflictError as exc:
        raise _conflict(exc) from exc
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HumanInformationRequestResponse(
        id=resolved.id,
        status=resolved.status,
        shared_question=resolved.shared_question,
        created_at=resolved.created_at,
        resolved_item_id=resolved.resolved_item_id,
    )


@router.get("", response_model=ProgramInformationListResponse)
def list_program_information_admin(
    status: Literal["draft", "published", "archived"] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ProgramInformationListResponse:
    rows = list_admin_information(db, cohort_slug=configured_program_cohort_slug(), status=status)
    items = [_to_response(item, db=db) for item, _version in rows]
    return ProgramInformationListResponse(items=items, total=len(items))


@router.post("", response_model=ProgramInformationItemResponse, status_code=201)
def create_program_information_admin(
    payload: AdminProgramInformationCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProgramInformationItemResponse:
    try:
        item = create_information_item(
            db,
            cohort_slug=configured_program_cohort_slug(),
            category=payload.category,
            visibility=payload.visibility,
            actor_id=str(actor.id),
            title=payload.title,
            body=payload.body,
            aliases=payload.aliases,
            source_url=str(payload.source_url) if payload.source_url else None,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
        )
    except InvalidProgramInformationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(item, db=db)


@router.patch("/{item_id}", response_model=ProgramInformationItemResponse)
def update_program_information_admin(
    item_id: int,
    payload: AdminProgramInformationUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProgramInformationItemResponse:
    item = _configured_item(db, item_id)
    try:
        item = update_information_item(
            db,
            item,
            expected_version=payload.expected_version,
            category=payload.category,
            visibility=payload.visibility,
            actor_id=str(actor.id),
            title=payload.title,
            body=payload.body,
            aliases=payload.aliases,
            source_url=str(payload.source_url) if payload.source_url else None,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
        )
    except VersionConflictError as exc:
        raise _conflict(exc) from exc
    except InvalidProgramInformationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(item, db=db)


@router.post("/{item_id}/publish", response_model=ProgramInformationItemResponse)
def publish_program_information_admin(
    item_id: int,
    payload: ExpectedVersionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProgramInformationItemResponse:
    try:
        item = publish_information_item(
            db,
            _configured_item(db, item_id),
            expected_version=payload.expected_version,
            actor_id=str(actor.id),
        )
    except VersionConflictError as exc:
        raise _conflict(exc) from exc
    return _to_response(item, db=db)


@router.post("/{item_id}/archive", response_model=ProgramInformationItemResponse)
def archive_program_information_admin(
    item_id: int,
    payload: ExpectedVersionRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_admin),
) -> ProgramInformationItemResponse:
    try:
        item = archive_information_item(
            db,
            _configured_item(db, item_id),
            expected_version=payload.expected_version,
            actor_id=str(actor.id),
        )
    except VersionConflictError as exc:
        raise _conflict(exc) from exc
    return _to_response(item, db=db)
