"""Công cụ chỉ đọc Google Sheets/Docs cho agent hội thoại."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime

from fastapi import HTTPException
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from src.connectors.google_docs import (
    GOOGLE_DOCS_EXTRACTION_CONTRACT,
    GoogleDocsAPIError,
    GoogleDocsConnector,
    extract_document_id,
)
from src.connectors.google_http import GoogleResponseTooLargeError
from src.connectors.google_sheets import GoogleSheetsAPIError, GoogleSheetsConnector, extract_spreadsheet_id
from src.models.connection import Connection
from src.models.user import User
from src.services import document_read_quota
from src.services.connections import preferred_connection
from src.services.google_sheet_task_extraction import (
    google_sheet_extraction_contract,
)

_user_id: ContextVar[str | None] = ContextVar("google_document_user_id", default=None)
_MAX_PROPOSALS_IN_CONTEXT = 30


def set_google_document_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_google_document_scope() -> None:
    _user_id.set(None)


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _google_context(db: Session, required_scope: str) -> tuple[str, User, Connection] | str:
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được người dùng nên chưa thể đọc tài liệu Google."
    user = db.get(User, int(user_id))
    if user is None:
        return "Không tìm thấy tài khoản đang yêu cầu đọc tài liệu Google."
    connection = preferred_connection(db, user_id, "google")
    if connection is None:
        return "Chưa có kết nối Google. Hãy kết nối Google trong Sources trước khi đọc tài liệu."
    if not connection.scopes or required_scope not in connection.scopes:
        return f"Kết nối Google chưa có quyền {required_scope}; hãy cấp lại quyền Google trong Sources."
    return user_id, user, connection


def _error(source: str, exc: Exception) -> dict:
    detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
    return {"source": source, "error": detail, "proposals": []}


async def _read_google_sheets(
    db: Session,
    *,
    user_id: str,
    user: User,
    connection: Connection,
    spreadsheet_url: str,
    sheet_name: str,
) -> dict:
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    connector = GoogleSheetsConnector(connection, db)
    extractor_version = google_sheet_extraction_contract()

    if sheet_name.strip():
        descriptors = await connector.list_sheets(spreadsheet_id)
        selected_sheet_name, available_sheet_names = await connector.select_sheet(
            spreadsheet_id, sheet_name
        )
        descriptor = next(
            item for item in descriptors if item.title == selected_sheet_name
        )
        snapshot = await connector.read_sheet(spreadsheet_id, selected_sheet_name)
        cache_key = document_read_quota.build_cache_key(
            user_id=user_id,
            file_id=spreadsheet_id,
            revision=snapshot.revision,
            extractor_version=extractor_version,
            sheet_name=selected_sheet_name,
        )
        cached = document_read_quota.read_cache(
            db, user_id=user_id, cache_key=cache_key
        )
        if cached is None:
            remaining = document_read_quota.consume_document_read(db, user_id)
            proposals = await connector.task_proposals(
                spreadsheet_id=spreadsheet_id,
                sheet_name=selected_sheet_name,
                display_name=user.display_name or "",
                values=snapshot.values,
                sheet_id=descriptor.sheet_id,
            )
            truncated = snapshot.truncated
            document_read_quota.write_cache(
                db,
                user_id=user_id,
                cache_key=cache_key,
                proposals=proposals,
                truncated=truncated,
            )
        else:
            proposals, truncated = cached
            remaining = document_read_quota.quota_remaining(db, user_id)
        scanned_sheet_names = [selected_sheet_name]
        coverage_complete = True
        result_sheet_name = selected_sheet_name
    else:
        descriptors = await connector.list_sheets(spreadsheet_id)
        workbook = await connector.read_workbook(spreadsheet_id, descriptors)
        available_sheet_names = workbook.available_sheet_names
        cache_key = document_read_quota.build_cache_key(
            user_id=user_id,
            file_id=spreadsheet_id,
            revision=workbook.revision,
            extractor_version=extractor_version,
            sheet_name="*workbook*",
        )
        cached = document_read_quota.read_cache(
            db, user_id=user_id, cache_key=cache_key
        )
        if cached is None:
            remaining = document_read_quota.consume_document_read(db, user_id)
            proposals = await connector.workbook_task_proposals(
                spreadsheet_id=spreadsheet_id,
                display_name=user.display_name or "",
                snapshot=workbook,
            )
            truncated = workbook.truncated
            document_read_quota.write_cache(
                db,
                user_id=user_id,
                cache_key=cache_key,
                proposals=proposals,
                truncated=truncated,
            )
        else:
            proposals, truncated = cached
            remaining = document_read_quota.quota_remaining(db, user_id)
        scanned_sheet_names = workbook.scanned_sheet_names
        coverage_complete = not workbook.truncated
        result_sheet_name = ""

    visible = _json_safe(proposals[:_MAX_PROPOSALS_IN_CONTEXT])
    return {
        "source": "Google Sheets",
        "spreadsheet_url": spreadsheet_url,
        "sheet_name": result_sheet_name,
        "available_sheet_names": available_sheet_names,
        "scanned_sheet_names": scanned_sheet_names,
        "coverage_complete": coverage_complete,
        "proposals": visible,
        "proposal_count": len(proposals),
        "truncated": truncated or len(proposals) > _MAX_PROPOSALS_IN_CONTEXT,
        "quota_remaining": remaining,
    }


@tool
async def google_sheets_task_proposals(spreadsheet_url: str, sheet_name: str = "") -> dict | str:
    """Đọc workbook Google Sheets và trích các task liên quan tới người dùng.

    Đây là read-only. Không tạo task và không sửa bảng. Để trống `sheet_name`
    để quét toàn bộ workbook trong hard cap; truyền tên để chỉ đọc đúng tab đó.
    """
    from src.db import engine

    with Session(engine) as db:
        context = _google_context(db, "spreadsheets.readonly")
        if isinstance(context, str):
            return context
        user_id, user, connection = context
        try:
            return await _read_google_sheets(
                db,
                user_id=user_id,
                user=user,
                connection=connection,
                spreadsheet_url=spreadsheet_url,
                sheet_name=sheet_name,
            )
        except (HTTPException, GoogleResponseTooLargeError, GoogleSheetsAPIError, ValueError) as exc:
            return _error("Google Sheets", exc)


@tool
async def google_docs_task_proposals(document_url: str) -> dict | str:
    """Đọc URL Google Docs người dùng vừa gửi và trích các task liên quan tới họ.

    Đây là read-only. Không tạo task và không sửa tài liệu.
    """
    from src.db import engine

    with Session(engine) as db:
        context = _google_context(db, "documents.readonly")
        if isinstance(context, str):
            return context
        user_id, user, connection = context
        try:
            document_id = extract_document_id(document_url)
            connector = GoogleDocsConnector(connection, db)
            snapshot = await connector.read_document(document_id)
            cache_key = document_read_quota.build_cache_key(
                user_id=user_id,
                file_id=document_id,
                revision=snapshot.revision,
                extractor_version=GOOGLE_DOCS_EXTRACTION_CONTRACT,
            )
            cached = document_read_quota.read_cache(db, user_id=user_id, cache_key=cache_key)
            if cached is None:
                remaining = document_read_quota.consume_document_read(db, user_id)
                proposals = await connector.task_proposals(
                    document_id=document_id,
                    display_name=user.display_name or "",
                    document_text=snapshot.text,
                )
                truncated = snapshot.truncated
                document_read_quota.write_cache(
                    db,
                    user_id=user_id,
                    cache_key=cache_key,
                    proposals=proposals,
                    truncated=truncated,
                )
            else:
                proposals, truncated = cached
                remaining = document_read_quota.quota_remaining(db, user_id)
            visible = _json_safe(proposals[:_MAX_PROPOSALS_IN_CONTEXT])
            return {
                "source": "Google Docs",
                "document_url": document_url,
                "proposals": visible,
                "proposal_count": len(proposals),
                "truncated": truncated or len(proposals) > _MAX_PROPOSALS_IN_CONTEXT,
                "quota_remaining": remaining,
            }
        except (HTTPException, GoogleResponseTooLargeError, GoogleDocsAPIError, ValueError) as exc:
            return _error("Google Docs", exc)
