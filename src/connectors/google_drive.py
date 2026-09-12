"""Connector chỉ đọc Google Drive: liệt kê/tìm file Docs & Sheets của người dùng.

Chỉ trả metadata (id, tên, thời điểm sửa, link mở), không đọc nội dung — nội
dung là việc của `google_docs.py` / `google_sheets.py` và phải đi qua tầng
quota/cache. Nhờ vậy thao tác duyệt file không tốn token và không trừ hạn mức.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from src.connectors.base import ConnectorAPIError
from src.models.connection import Connection
from src.services.connections import google

API_BASE = "https://www.googleapis.com/drive/v3/files"
DRIVE_READONLY_SCOPE = "drive.readonly"

MIME_DOCUMENT = "application/vnd.google-apps.document"
MIME_SPREADSHEET = "application/vnd.google-apps.spreadsheet"
_KIND_BY_MIME = {MIME_DOCUMENT: "document", MIME_SPREADSHEET: "spreadsheet"}
_MIME_BY_KIND = {"document": MIME_DOCUMENT, "spreadsheet": MIME_SPREADSHEET}


class GoogleDriveAPIError(ConnectorAPIError):
    """Lỗi Google Drive đã được làm sạch, an toàn để trả về API."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


_RECONNECT_REASONS = {"insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}
_SERVICE_DISABLED_REASONS = {"accessNotConfigured", "SERVICE_DISABLED"}
_RATE_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "RATE_LIMIT_EXCEEDED"}
_DOMAIN_POLICY_REASONS = {"domainPolicy", "DOMAIN_POLICY"}


def _google_error_reasons(response: httpx.Response) -> set[str]:
    """Lấy mã nguyên nhân 403 từ cả payload Drive cũ và google.rpc mới.

    Chỉ đọc trường ``reason`` đã định danh; không đưa message/metadata của
    Google ra ngoài vì chúng có thể chứa project ID hoặc chi tiết nội bộ.
    """
    try:
        body = response.json()
    except ValueError:
        return set()
    if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
        return set()

    error = body["error"]
    reasons: set[str] = set()
    reason = error.get("reason")
    if isinstance(reason, str):
        reasons.add(reason)
    for field in ("errors", "details"):
        entries = error.get(field)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("reason"), str):
                reasons.add(entry["reason"])
    return reasons


def _list_files_error(response: httpx.Response) -> GoogleDriveAPIError:
    """Chuyển lỗi Drive thành hướng xử lý an toàn, có thể hiện cho người dùng."""
    if response.status_code != 403:
        return GoogleDriveAPIError(f"Google Drive API lỗi {response.status_code} khi liệt kê file.")

    reasons = _google_error_reasons(response)
    if reasons & _RECONNECT_REASONS:
        return GoogleDriveAPIError(
            "Kết nối Google không còn quyền duyệt Drive; hãy cấp lại quyền Google.",
            status_code=409,
        )
    if reasons & _SERVICE_DISABLED_REASONS:
        return GoogleDriveAPIError(
            "Google Drive API chưa được bật cho dự án Google Cloud; quản trị hệ thống cần bật API rồi thử lại.",
            status_code=503,
        )
    if reasons & _RATE_LIMIT_REASONS:
        return GoogleDriveAPIError(
            "Google Drive đang giới hạn yêu cầu tạm thời; hãy chờ một chút rồi thử lại.",
            status_code=503,
        )
    if reasons & _DOMAIN_POLICY_REASONS:
        return GoogleDriveAPIError(
            "Quản trị viên Google Workspace đang chặn ứng dụng truy cập Drive.",
            status_code=403,
        )
    return GoogleDriveAPIError("Google Drive từ chối quyền liệt kê file (403).")


def _escape_query_literal(value: str) -> str:
    """Thoát chuỗi người dùng nhập trước khi ghép vào cú pháp `q` của Drive.

    Không thoát thì một dấu nháy đơn trong từ khoá đủ làm hỏng biểu thức và
    (tệ hơn) cho phép ghép thêm mệnh đề vào truy vấn của người khác.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def build_query(*, search: str | None, kind: str) -> str:
    """Dựng biểu thức `q`: chỉ Docs/Sheets, bỏ file đã vào thùng rác."""
    if kind not in ("document", "spreadsheet", "all"):
        raise ValueError("kind phải là 'document', 'spreadsheet' hoặc 'all'.")
    if kind == "all":
        mime_clause = f"(mimeType='{MIME_DOCUMENT}' or mimeType='{MIME_SPREADSHEET}')"
    else:
        mime_clause = f"mimeType='{_MIME_BY_KIND[kind]}'"
    clauses = [mime_clause, "trashed=false"]
    if search:
        clauses.append(f"name contains '{_escape_query_literal(search.strip())}'")
    return " and ".join(clauses)


class GoogleDriveConnector:
    """Duyệt/tìm file Docs & Sheets trong Drive của người dùng đã cấp quyền."""

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await google.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise GoogleDriveAPIError(f"Không lấy được access token Google Drive: {exc}") from exc

    async def list_files(
        self,
        *,
        search: str | None = None,
        kind: str = "all",
        page_token: str | None = None,
        page_size: int = 20,
    ) -> dict:
        token = await self._access_token()
        params: dict[str, object] = {
            "q": build_query(search=search, kind=kind),
            "pageSize": page_size,
            "orderBy": "modifiedTime desc",
            "fields": "nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
            # File trong Shared drive cũng là file của người dùng; thiếu 2 cờ
            # này Drive im lặng chỉ trả My Drive và người dùng tưởng mất file.
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            response = await client.get(API_BASE, params=params)
        if response.status_code != 200:
            raise _list_files_error(response)
        body = response.json()
        raw_files = body.get("files")
        if not isinstance(raw_files, list):
            raise GoogleDriveAPIError("Google Drive trả về dữ liệu không hợp lệ.")

        files: list[dict] = []
        for item in raw_files:
            if not isinstance(item, dict):
                continue
            file_kind = _KIND_BY_MIME.get(item.get("mimeType"))
            if file_kind is None:
                continue
            file_id = item.get("id")
            modified_time = item.get("modifiedTime")
            if not file_id or not modified_time:
                continue
            files.append(
                {
                    "id": file_id,
                    "name": item.get("name") or "(không có tên)",
                    "kind": file_kind,
                    "modified_time": modified_time,
                    "web_view_link": item.get("webViewLink") or _default_link(file_kind, file_id),
                }
            )
        return {"files": files, "next_page_token": body.get("nextPageToken")}


def _default_link(kind: str, file_id: str) -> str:
    """Link mở file khi Drive không trả webViewLink (hiếm, nhưng frontend cần có link)."""
    segment = "document" if kind == "document" else "spreadsheets"
    return f"https://docs.google.com/{segment}/d/{file_id}/edit"
