"""Connector chỉ đọc Google Docs, dùng LLM để trích task/mốc thời gian từ văn bản tự do."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import ConnectorAPIError
from src.connectors.google_http import fetch_json_capped
from src.connectors.google_sheets import _name_matches, _parse_due
from src.models.connection import Connection
from src.services.connections import google
from src.services.document_extraction import (
    DocumentExtractionError,
    DocumentExtractionUnavailableError,
    extract_task_candidates_from_text,
)

API_BASE = "https://docs.googleapis.com/v1/documents"
_DOCUMENT_ID = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
GOOGLE_DOCS_EXTRACTION_CONTRACT = "google-docs:task-candidates-v1"

# Ngưỡng cắt văn bản trước khi gửi LLM khai ở src/config.py
# (`google_document_max_chars`) — cùng một khái niệm với cap của Sheets, nên
# chỉ có một chỗ định nghĩa, không giữ thêm hằng số riêng ở module này.


class GoogleDocsAPIError(ConnectorAPIError):
    """Lỗi Google Docs đã được làm sạch, an toàn để trả về API."""


@dataclass(frozen=True)
class DocumentSnapshot:
    """Nội dung Doc đã cắt theo cap, kèm revision để làm khoá cache."""

    text: str
    truncated: bool
    revision: str


def extract_document_id(value: str) -> str:
    """Nhận URL Google Docs hoặc ID, không chấp nhận URL ngoài Google Docs."""
    candidate = value.strip()
    match = _DOCUMENT_ID.search(candidate)
    if match:
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or parsed.hostname != "docs.google.com":
            raise ValueError("documentUrl phải trỏ tới docs.google.com.")
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9_-]{20,200}", candidate):
        return candidate
    raise ValueError("documentUrl phải là URL Google Docs hoặc document ID hợp lệ.")


def _paragraph_text(paragraph: dict) -> str:
    parts: list[str] = []
    for element in paragraph.get("elements") or []:
        text_run = element.get("textRun")
        if isinstance(text_run, dict):
            content = text_run.get("content")
            if isinstance(content, str):
                parts.append(content)
    return "".join(parts)


class GoogleDocsConnector:
    """Đọc nội dung một Google Doc do người dùng đã cấp quyền, đề xuất task/lịch."""

    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await google.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise GoogleDocsAPIError(f"Không lấy được access token Google Docs: {exc}") from exc

    async def read_document(self, document_id: str) -> DocumentSnapshot:
        """Đọc văn bản Doc, đã cắt theo cap, kèm revisionId để làm khoá cache."""
        token = await self._access_token()
        url = f"{API_BASE}/{document_id}"
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            status_code, body = await fetch_json_capped(client, url, source="Google Docs")
        if status_code != 200:
            raise GoogleDocsAPIError(f"Google Docs API lỗi {status_code} khi đọc tài liệu.")
        content = ((body.get("body") or {}).get("content")) or []
        if not isinstance(content, list):
            raise GoogleDocsAPIError("Google Docs trả về dữ liệu không hợp lệ.")
        paragraphs: list[str] = []
        for item in content:
            paragraph = item.get("paragraph") if isinstance(item, dict) else None
            if not isinstance(paragraph, dict):
                continue
            text = _paragraph_text(paragraph)
            if text.strip():
                paragraphs.append(text.rstrip("\n"))
        full_text = "\n".join(paragraphs)
        max_chars = get_settings().google_document_max_chars
        truncated = len(full_text) > max_chars
        revision = body.get("revisionId")
        if not isinstance(revision, str) or not revision:
            # Doc chia sẻ ở vài chế độ không trả revisionId; băm nội dung là
            # định danh revision thay thế, chặt hơn chứ không lỏng hơn.
            revision = "sha256:" + hashlib.sha256(full_text.encode("utf-8")).hexdigest()
        return DocumentSnapshot(text=full_text[:max_chars], truncated=truncated, revision=revision)

    async def read_document_text(self, document_id: str) -> str:
        """Giữ cho caller cũ chỉ cần văn bản (đã cắt theo cap)."""
        return (await self.read_document(document_id)).text

    async def task_proposals(self, *, document_id: str, display_name: str, document_text: str | None = None) -> list[dict]:
        """Sinh đề xuất task từ văn bản Doc.

        `document_text` cho phép caller đã đọc sẵn nội dung (để tính khoá cache
        và cap) truyền lại, tránh gọi Google Docs API hai lần cho một lượt.
        """
        if document_text is None:
            document_text = await self.read_document_text(document_id)
        timezone_name = get_settings().app_timezone or "Asia/Ho_Chi_Minh"
        try:
            candidates = await extract_task_candidates_from_text(document_text)
        except DocumentExtractionUnavailableError as exc:
            raise GoogleDocsAPIError(str(exc)) from exc
        except DocumentExtractionError as exc:
            raise GoogleDocsAPIError(str(exc)) from exc

        proposals: list[dict] = []
        for index, candidate in enumerate(candidates):
            title = (candidate.title or "").strip()
            if not title:
                continue
            assignee = (candidate.assignee or "").strip()
            raw_due = (candidate.due_at or "").strip()
            due_at, all_day, date_ambiguous = _parse_due(raw_due, timezone_name)
            matched = _name_matches(assignee, display_name) if assignee else False
            name_ambiguous = bool(assignee) and not matched
            clarification_parts: list[str] = []
            if name_ambiguous:
                clarification_parts.append(
                    f"Việc “{title}” ghi người phụ trách là “{assignee}”. Đây có phải là việc của bạn không?"
                )
            if date_ambiguous and due_at is not None:
                clarification_parts.append(
                    f"Việc “{title}”: hạn chót '{raw_due}' không rõ năm, hệ thống đang hiểu là {due_at.isoformat()}. Bạn xác nhận lại nhé."
                )
            needs_confirmation = name_ambiguous or (date_ambiguous and due_at is not None)
            clarification = " ".join(clarification_parts) or None
            source_url = f"https://docs.google.com/document/d/{document_id}/edit"
            proposals.append(
                {
                    "paragraph_index": index,
                    "title": title,
                    "detail": candidate.detail or "",
                    "assignee": assignee or None,
                    "due_at": due_at,
                    "all_day": all_day,
                    "date_ambiguous": date_ambiguous and due_at is not None,
                    "matched_user": matched,
                    "needs_confirmation": needs_confirmation,
                    "clarification_question": clarification,
                    "source": "Google Docs",
                    "source_url": source_url,
                }
            )
        return proposals
