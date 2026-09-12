"""Công cụ tìm file Google Drive (Docs & Sheets) chỉ đọc cho agent hội thoại.

User scope do tầng gọi đặt qua ContextVar, không nằm trong schema mà model có
thể điền — model không bao giờ được tự chọn đọc Drive của ai.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from langchain_core.tools import tool
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_user_id: ContextVar[str | None] = ContextVar("drive_search_user_id", default=None)
# Xin một trang đủ lớn từ Drive rồi tự cắt hiển thị: không phân trang tiếp (không
# crawl vô hạn), nhưng vẫn phát hiện được là còn file chưa hiển thị.
_DRIVE_PAGE_SIZE = 50
_MAX_FILES_IN_CONTEXT = 20


def set_drive_search_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_drive_search_scope() -> None:
    _user_id.set(None)


@tool
async def drive_search_files(query: str = "", kind: str = "all") -> str:
    """Tìm file Google Docs/Sheets theo tên trong Google Drive của người dùng.

    Dùng khi người dùng nhắc tới một file/tài liệu/bảng tính trong Drive nhưng
    không đưa URL — ví dụ "tìm file kế hoạch Q3 trong Drive của tôi" — để lấy
    URL của file rồi (nếu cần) đọc nội dung bằng google_docs_task_proposals
    hoặc google_sheets_task_proposals. Đây là công cụ CHỈ ĐỌC METADATA (tên,
    loại, thời điểm sửa, link mở); nó không đọc nội dung file, không tạo, sửa
    hay xoá gì trong Drive.

    Args:
        query: Từ khóa trong tên file; để trống để liệt kê file gần đây nhất
        kind: 'document', 'spreadsheet' hoặc 'all' (mặc định)

    Returns:
        Danh sách file kèm loại, thời điểm sửa gần nhất và link mở trong Drive
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được đây là Drive của ai nên chưa tìm. Tầng gọi phải đặt phạm vi người dùng trước."

    from src.connectors.google_drive import DRIVE_READONLY_SCOPE, GoogleDriveConnector
    from src.db import engine
    from src.services.connections import preferred_connection

    try:
        with Session(engine) as db:
            connection = preferred_connection(db, user_id, "google")
            if connection is None:
                return "Chưa có kết nối Google. Hãy kết nối Google trong Sources trước khi tìm file Drive."
            if not connection.scopes or DRIVE_READONLY_SCOPE not in connection.scopes:
                return "Kết nối Google chưa có quyền duyệt Drive; hãy cấp lại quyền Google trong Sources."

            result = await GoogleDriveConnector(connection, db).list_files(
                search=query.strip(),
                kind=kind,
                page_size=_DRIVE_PAGE_SIZE,
            )
    except Exception as exc:  # Connector lỗi (kể cả 403 đã phân loại) phải thành câu trả lời có kiểm soát.
        logger.warning("Tìm Drive hỏng cho user %s: %s", user_id, exc)
        return f"Không tìm được file Google Drive: {exc}"

    files = result["files"]
    if not files:
        label = f" khớp '{query.strip()}'" if query.strip() else ""
        return f"Không có file Google Drive nào{label}."

    visible = files[:_MAX_FILES_IN_CONTEXT]
    lines = ["File Google Drive:"]
    for item in visible:
        lines.append(f"- {item['name']} [{item['kind']}] — sửa lúc {item['modified_time']}\n  nguồn: {item['web_view_link']}")

    if len(files) > _MAX_FILES_IN_CONTEXT:
        lines.append("Còn file khác chưa hiển thị, hãy thu hẹp từ khóa tìm kiếm.")
    return "\n".join(lines)
