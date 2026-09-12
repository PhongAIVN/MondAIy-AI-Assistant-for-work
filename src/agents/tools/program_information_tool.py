"""Tool đọc thông tin chương trình đã phát hành trong phạm vi backend cấp."""

from __future__ import annotations

import json
from contextvars import ContextVar

from langchain_core.tools import tool

_access_level: ContextVar[str | None] = ContextVar("program_information_level", default=None)
_cohort_slug: ContextVar[str | None] = ContextVar("program_information_cohort", default=None)
_scope_applied: ContextVar[bool] = ContextVar("program_information_scope_applied", default=False)


def set_program_information_scope(access_level: str | None, cohort_slug: str | None) -> None:
    """Đặt quyền và cohort ở tầng tin cậy trước khi agent chạy."""
    _access_level.set((access_level or "").strip().upper() or None)
    _cohort_slug.set((cohort_slug or "").strip() or None)
    _scope_applied.set(True)


def reset_program_information_scope() -> None:
    """Xóa phạm vi để lượt sau mặc định từ chối đọc."""
    _access_level.set(None)
    _cohort_slug.set(None)
    _scope_applied.set(False)


@tool
def program_information_search(query: str = "", category: str = "", limit: int = 8) -> str:
    """Tra thông tin chính thức của chương trình do đội ngũ đã biên tập và phát hành.

    Dùng cho câu hỏi về tổng quan, quy định, cách nộp bài, hỗ trợ và các câu hỏi
    thường gặp. Với lịch workshop/deadline theo thời gian, dùng program_schedule.
    Cohort và quyền không nằm trong tham số nên nội dung prompt không thể đổi
    chúng. Kết quả kèm nguồn, phiên bản và thời điểm cập nhật để trích dẫn.

    Args:
        query: Từ khóa hoặc câu hỏi của người dùng
        category: overview, schedule, policy, submission, support hoặc other
        limit: Số kết quả tối đa
    """
    if not _scope_applied.get():
        return "Chưa đặt phạm vi thông tin chương trình; tầng gọi phải đặt quyền trước."
    if not _cohort_slug.get() or _access_level.get() not in {"A", "B", "C"}:
        return "Tài khoản chưa có phạm vi đọc thông tin sản phẩm/chương trình."
    allowed_categories = {"overview", "schedule", "policy", "submission", "support", "other"}
    normalized_category = category.strip().lower()
    if normalized_category and normalized_category not in allowed_categories:
        return "Loại thông tin không hợp lệ."

    from src.db import SessionLocal
    from src.services.program_information import search_published_information

    with SessionLocal() as db:
        records = search_published_information(
            db,
            cohort_slug=_cohort_slug.get() or "",
            # Public product docs dùng được cho mọi user đã đăng nhập; nội
            # dung chương trình chỉ mở cho user type A.
            allowed_visibilities=frozenset({"public", "program"})
            if _access_level.get() == "A"
            else frozenset({"public"}),
            query=query,
            category=normalized_category or None,
            limit=max(1, min(limit, 20)),
        )
    if not records:
        return "Chưa có thông tin đã phát hành phù hợp. Có thể đề nghị đội ngũ trả lời."

    evidence = [
        {
            "id": record.item.id,
            "category": record.version.category,
            "title": record.version.title,
            "body": record.version.body,
            "source": record.version.source_url,
            "version": record.version.version,
            "updatedAt": record.version.created_at.isoformat(),
            "contentHash": record.version.content_hash,
        }
        for record in records
    ]
    return json.dumps({"evidence": evidence}, ensure_ascii=False)
