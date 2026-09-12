"""API tra cứu thông tin chương trình và chuyển câu hỏi cho đội ngũ."""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db import get_db
from src.models.program_information_schemas import (
    Category,
    HumanInformationRequestCreate,
    HumanInformationRequestResponse,
    ProgramInformationItemResponse,
    ProgramInformationListResponse,
)
from src.models.user import User
from src.services import auth as auth_service
from src.services.program_cohorts import configured_program_cohort_slug, resolve_program_cohort_slug
from src.services.program_information import (
    InvalidProgramInformationError,
    create_human_request,
    search_published_information,
)

router = APIRouter(prefix="/program-information", tags=["program-information"])


def _optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User | None:
    if authorization is None:
        return None
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authorization không hợp lệ.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        user_id = auth_service.decode_token(token, "access")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User không tồn tại.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khoá.")
    return user


def _to_response(record) -> ProgramInformationItemResponse:
    item, version = record.item, record.version
    return ProgramInformationItemResponse(
        id=item.id,
        cohort_slug=item.cohort_slug,
        category=version.category,
        visibility=version.visibility,
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


def _assigned_cohort(user: User) -> str:
    try:
        return resolve_program_cohort_slug(user.program_cohort_slug)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Cohort chương trình cấu hình không hợp lệ.") from exc


@router.get("", response_model=ProgramInformationListResponse)
def search_program_information(
    query: str = Query(default="", max_length=500),
    category: Category | None = Query(default=None),
    scope: Literal["public", "program", "all"] = Query(default="public"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User | None = Depends(_optional_user),
) -> ProgramInformationListResponse:
    """Tra bản phát hành hiện hành; cohort luôn do server quyết định."""
    visibilities = frozenset({"public"})
    if scope in {"program", "all"}:
        if user is None:
            raise HTTPException(status_code=401, detail="Cần đăng nhập để đọc thông tin chương trình.")
        if user.program_access_level != "A":
            raise HTTPException(
                status_code=403,
                detail="Tài khoản chưa khớp danh tính chương trình.",
            )
        cohort = _assigned_cohort(user)
        visibilities = frozenset({"program"}) if scope == "program" else frozenset({"public", "program"})
    else:
        cohort = _assigned_cohort(user) if user else configured_program_cohort_slug()
    records = search_published_information(
        db,
        cohort_slug=cohort,
        allowed_visibilities=visibilities,
        query=query,
        category=category,
        limit=limit,
    )
    items = [_to_response(record) for record in records]
    return ProgramInformationListResponse(items=items, total=len(items))


@router.post(
    "/human-requests",
    response_model=HumanInformationRequestResponse,
    status_code=201,
)
def request_human_answer(
    payload: HumanInformationRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> HumanInformationRequestResponse:
    """Chỉ chia sẻ đúng câu người dùng đã sửa và đồng ý gửi."""
    if not payload.consent_to_share:
        raise HTTPException(
            status_code=422,
            detail="Cần đồng ý rõ ràng trước khi gửi câu hỏi cho đội ngũ.",
        )
    if user.program_access_level != "A":
        raise HTTPException(status_code=403, detail="Tài khoản chưa khớp danh tính chương trình.")
    try:
        request = create_human_request(
            db,
            cohort_slug=_assigned_cohort(user),
            requester_id=user.id,
            shared_question=payload.shared_question,
        )
    except InvalidProgramInformationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return HumanInformationRequestResponse(
        id=request.id,
        status=request.status,
        shared_question=request.shared_question,
        created_at=request.created_at,
        resolved_item_id=request.resolved_item_id,
    )
