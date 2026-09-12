"""API duyệt/tìm file Google Docs & Sheets để người dùng chọn thay vì dán URL."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
from src.config import get_settings
from src.connectors.google_drive import DRIVE_READONLY_SCOPE, GoogleDriveAPIError, GoogleDriveConnector
from src.db import get_db
from src.models.schemas import GoogleDriveFileListResponse
from src.models.user import User
from src.services.connections import preferred_connection

router = APIRouter(prefix="/google-drive", tags=["google-drive"])


@router.get("/files", response_model=GoogleDriveFileListResponse)
@limiter.limit("30/minute")
async def list_google_drive_files(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    kind: str = Query(default="all", pattern="^(document|spreadsheet|all)$"),
    page_token: str | None = Query(default=None, alias="pageToken", max_length=2000),
    page_size: int = Query(default=20, ge=1, alias="pageSize"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoogleDriveFileListResponse:
    # Liệt kê file KHÔNG trừ hạn mức đọc tài liệu: nó chỉ lấy metadata, không
    # tốn token nào. Hạn mức chỉ dành cho lượt đọc nội dung (Docs/Sheets).
    settings = get_settings()
    if page_size > settings.google_drive_page_size_max:
        raise HTTPException(
            status_code=422,
            detail=f"pageSize tối đa là {settings.google_drive_page_size_max}.",
        )
    connection = preferred_connection(db, str(user.id), "google")
    if connection is None:
        raise HTTPException(status_code=409, detail="Hãy đăng nhập/kết nối Google để duyệt file Google Drive.")
    if not connection.scopes or DRIVE_READONLY_SCOPE not in connection.scopes:
        raise HTTPException(
            status_code=409,
            detail="Kết nối Google chưa có quyền duyệt Drive; hãy cấp lại quyền Google.",
        )
    try:
        result = await GoogleDriveConnector(connection, db).list_files(
            search=q,
            kind=kind,
            page_token=page_token,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GoogleDriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return GoogleDriveFileListResponse(files=result["files"], next_page_token=result["next_page_token"])
