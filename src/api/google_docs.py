"""API đọc Google Docs và trả đề xuất task cho người dùng xác nhận."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
from src.config import get_settings
from src.connectors.google_docs import (
    GOOGLE_DOCS_EXTRACTION_CONTRACT,
    GoogleDocsAPIError,
    GoogleDocsConnector,
    extract_document_id,
)
from src.connectors.google_http import GoogleResponseTooLargeError
from src.db import get_db
from src.models.schemas import GoogleDocsTaskProposalRequest, GoogleDocsTaskProposalResponse
from src.models.user import User
from src.services import document_read_quota
from src.services.connections import preferred_connection

router = APIRouter(prefix="/google-docs", tags=["google-docs"])


@router.post("/task-proposals", response_model=GoogleDocsTaskProposalResponse)
@limiter.limit("10/minute")
async def read_google_doc_task_proposals(
    request: Request,
    payload: GoogleDocsTaskProposalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoogleDocsTaskProposalResponse:
    connection = preferred_connection(db, str(user.id), "google")
    if connection is None:
        raise HTTPException(status_code=409, detail="Hãy đăng nhập/kết nối Google để đọc Google Docs.")
    if not connection.scopes or "documents.readonly" not in connection.scopes:
        raise HTTPException(status_code=409, detail="Kết nối Google chưa có quyền đọc Docs; hãy cấp lại quyền Google.")
    try:
        # documentId đến thẳng từ picker Drive nên không cần bóc URL; vẫn đi
        # qua cùng một hàm kiểm tra để id rác không lọt xuống Google API.
        document_id = extract_document_id(payload.document_id or payload.document_url or "")
        connector = GoogleDocsConnector(connection, db)
        snapshot = await connector.read_document(document_id)
        cache_key = document_read_quota.build_cache_key(
            user_id=str(user.id),
            file_id=document_id,
            revision=snapshot.revision,
            extractor_version=GOOGLE_DOCS_EXTRACTION_CONTRACT,
        )
        cached = document_read_quota.read_cache(db, user_id=str(user.id), cache_key=cache_key)
        if cached is not None:
            proposals, truncated = cached
            # Trúng cache: không gọi LLM, không trừ lượt.
            remaining = document_read_quota.quota_remaining(db, str(user.id))
        else:
            remaining = document_read_quota.consume_document_read(db, str(user.id))
            proposals = await connector.task_proposals(
                document_id=document_id,
                display_name=user.display_name or "",
                document_text=snapshot.text,
            )
            truncated = snapshot.truncated
            document_read_quota.write_cache(
                db,
                user_id=str(user.id),
                cache_key=cache_key,
                proposals=proposals,
                truncated=truncated,
            )
    except GoogleResponseTooLargeError as exc:
        # File quá lớn là lỗi đầu vào, không phải Google hỏng -> 422 như contract,
        # không thêm mã mới để lane frontend khỏi phải chạy lại một vòng.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GoogleDocsAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GoogleDocsTaskProposalResponse(
        document_id=document_id,
        timezone=get_settings().app_timezone,
        proposals=proposals,
        truncated=truncated,
        quota_remaining=remaining,
    )
