"""API đọc Google Sheets và trả đề xuất task cho người dùng xác nhận."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.api.rate_limit import limiter
from src.config import get_settings
from src.connectors.google_http import GoogleResponseTooLargeError
from src.connectors.google_sheets import GoogleSheetsAPIError, GoogleSheetsConnector, extract_spreadsheet_id
from src.db import get_db
from src.models.schemas import (
    GoogleSheetsTaskProposalRequest,
    GoogleSheetsTaskProposalResponse,
)
from src.models.user import User
from src.services import document_read_quota
from src.services.connections import preferred_connection
from src.services.google_sheet_task_extraction import (
    google_sheet_extraction_contract,
)

router = APIRouter(prefix="/google-sheets", tags=["google-sheets"])


@router.post("/task-proposals", response_model=GoogleSheetsTaskProposalResponse)
@limiter.limit("10/minute")
async def read_google_sheet_task_proposals(
    request: Request,
    payload: GoogleSheetsTaskProposalRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoogleSheetsTaskProposalResponse:
    connection = preferred_connection(db, str(user.id), "google")
    if connection is None:
        raise HTTPException(status_code=409, detail="Hãy đăng nhập/kết nối Google để đọc Google Sheets.")
    if not connection.scopes or "spreadsheets.readonly" not in connection.scopes:
        raise HTTPException(
            status_code=409, detail="Kết nối Google chưa có quyền đọc Sheets; hãy cấp lại quyền Google."
        )
    try:
        # spreadsheetId đến thẳng từ picker Drive; vẫn đi qua cùng một hàm
        # kiểm tra để id rác không lọt xuống Google API.
        spreadsheet_id = extract_spreadsheet_id(payload.spreadsheet_id or payload.spreadsheet_url or "")
        connector = GoogleSheetsConnector(connection, db)
        selected_sheet_name, available_sheet_names = await connector.select_sheet(
            spreadsheet_id,
            payload.sheet_name,
        )
        snapshot = await connector.read_sheet(spreadsheet_id, selected_sheet_name)
        cache_key = document_read_quota.build_cache_key(
            user_id=str(user.id),
            file_id=spreadsheet_id,
            revision=snapshot.revision,
            extractor_version=google_sheet_extraction_contract(),
            sheet_name=selected_sheet_name,
        )
        cached = document_read_quota.read_cache(db, user_id=str(user.id), cache_key=cache_key)
        if cached is not None:
            proposals, truncated = cached
            # Trúng cache: không phân tích lại, không trừ lượt.
            remaining = document_read_quota.quota_remaining(db, str(user.id))
        else:
            remaining = document_read_quota.consume_document_read(db, str(user.id))
            proposals = await connector.task_proposals(
                spreadsheet_id=spreadsheet_id,
                sheet_name=selected_sheet_name,
                display_name=user.display_name or "",
                values=snapshot.values,
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
    except GoogleSheetsAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return GoogleSheetsTaskProposalResponse(
        spreadsheet_id=spreadsheet_id,
        sheet_name=selected_sheet_name,
        timezone=get_settings().app_timezone,
        available_sheet_names=available_sheet_names,
        proposals=proposals,
        truncated=truncated,
        quota_remaining=remaining,
    )
