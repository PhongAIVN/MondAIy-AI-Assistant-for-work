from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.services.connections import microsoft

logger = logging.getLogger(__name__)

API_BASE = "https://graph.microsoft.com/v1.0/me"

# P0 chỉ đọc Inbox — ADR-013 không xin scope rộng hơn Mail.Read, và Outlook
# không có khái niệm nhãn Promotions/Social như Gmail để tách thêm nguồn.
_INBOX_SOURCE = Source(id="inbox", name="Hộp thư chính")

# Cùng bộ từ khoá evidence với gmail.py (song song có chủ đích — 2 connector
# độc lập, không share module private của nhau).
_EVIDENCE_HINTS = re.compile(
    r"(?i)urgent|action required|deadline|due|submit|reply|respond|review|confirm|"
    r"mentor|course|class|assignment|project|milestone|demo|vlearn|canvas|jira|"
    r"hạn|nộp|phản hồi|yêu cầu|cần làm|thứ [2-7]"
)
# Cap tổng số message liệt kê per fetch_range, cùng tinh thần _MAX_MESSAGE_IDS
# bên gmail.py.
_MAX_MESSAGE_IDS = 1000
_MAX_METADATA_CANDIDATES = 80
_PAGE_SIZE = 100
_MAX_RATE_LIMIT_RETRIES = 5

# $select tối thiểu để tính signal — không kéo `body` (nặng) cho message
# chưa xác định có tín hiệu, cùng triết lý evidence-first của gmail.py.
_METADATA_SELECT = "id,subject,from,receivedDateTime,isRead,importance,bodyPreview,conversationId,webLink"
_FULL_SELECT = "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,isRead,importance,conversationId,webLink,hasAttachments"


class OutlookAPIError(ConnectorAPIError):
    """Lỗi gọi Microsoft Graph API — message đã làm sạch, an toàn để lộ ra route/SSE."""


# Cùng allow-list với guardrail/attachment_safety.py — lọc ngay ở connector
# để file không đọc được (zip, exe...) không chiếm chỗ trong
# attachment_max_per_message rồi bị node loại sau.
_EXTRACTABLE_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "image/png",
        "image/jpeg",
    }
)


def _extract_attachment_metadata(raw_item: dict) -> list[dict]:
    """Đổi `attachments[]` của Graph sang đúng shape attachment_extract_node đọc.

    Bỏ `isInline` — ảnh chèn trong chữ ký/thân mail không phải tài liệu đính
    kèm, trích chúng chỉ sinh nhiễu.
    """
    metadata: list[dict] = []
    for item in raw_item.get("attachments") or []:
        if item.get("isInline"):
            continue
        content_type = item.get("contentType") or ""
        if content_type not in _EXTRACTABLE_MIME_TYPES:
            continue
        metadata.append(
            {
                "filename": item.get("name") or "(không tên)",
                "mimeType": content_type,
                "sizeBytes": int(item.get("size") or 0),
                "attachmentId": str(item.get("id") or ""),
            }
        )
    return metadata


class OutlookConnector(BaseConnector):
    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await microsoft.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise OutlookAPIError(f"Không lấy được access token Outlook: {exc}") from exc

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.get(url, params=params)
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                logger.warning(
                    "Graph API rate limit tại %s, chờ %.1fs (lần %d/%d)",
                    url,
                    wait_seconds,
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                raise OutlookAPIError(f"Graph API lỗi {response.status_code} tại {url}")
            return response.json()
        raise OutlookAPIError(f"Graph API vẫn rate limit sau {_MAX_RATE_LIMIT_RETRIES} lần thử tại {url}")

    async def list_sources(self) -> list[Source]:
        # P0 không cho chọn folder — trả thẳng nguồn cố định duy nhất, tránh
        # UI hiện danh sách chọn cho một tính năng chưa hỗ trợ.
        return [_INBOX_SOURCE]

    async def fetch_range(
        self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None
    ) -> list[dict]:
        token = await self._access_token()
        filter_query = (
            f"receivedDateTime ge {time_from.strftime('%Y-%m-%dT%H:%M:%SZ')} "
            f"and receivedDateTime le {time_to.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        )

        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            # Evidence-first: liệt kê $select nhẹ trước, chỉ tải `body` đầy đủ
            # cho message có tín hiệu — cùng lý do gmail.py tách metadata/full.
            metadata_candidates: list[dict] = []
            skipped_no_signal = 0
            truncated_by_cap = False
            seen = 0
            url = f"{API_BASE}/mailFolders/{source.id}/messages"
            params: dict | None = {
                "$filter": filter_query,
                "$select": _METADATA_SELECT,
                "$top": _PAGE_SIZE,
                "$orderby": "receivedDateTime desc",
            }
            while url and seen < _MAX_MESSAGE_IDS:
                page = await self._get(client, url, params=params)
                params = None  # nextLink đã mang theo mọi query param
                for item in page.get("value", []):
                    seen += 1
                    if len(metadata_candidates) >= _MAX_METADATA_CANDIDATES:
                        truncated_by_cap = True
                        break
                    hint_text = " ".join(
                        [
                            item.get("subject", "") or "",
                            (item.get("from") or {}).get("emailAddress", {}).get("address", "") or "",
                            item.get("bodyPreview", "") or "",
                        ]
                    )
                    signalled = (
                        not item.get("isRead", True)
                        or item.get("importance") == "high"
                        or bool(_EVIDENCE_HINTS.search(hint_text))
                    )
                    if signalled:
                        metadata_candidates.append(item)
                    else:
                        skipped_no_signal += 1
                if truncated_by_cap:
                    break
                url = page.get("@odata.nextLink")
            if seen >= _MAX_MESSAGE_IDS:
                logger.warning(
                    "Outlook list message chạm cap %d cho folder %s — có thể còn message chưa liệt kê.",
                    _MAX_MESSAGE_IDS,
                    source.id,
                )
            if truncated_by_cap:
                logger.warning(
                    "Outlook metadata candidates chạm cap %d — phần message còn lại chưa được xét.",
                    _MAX_METADATA_CANDIDATES,
                )
            logger.info(
                "Outlook fetch_range %s: %d message -> %d candidate (%d bỏ qua không tín hiệu)",
                source.id,
                seen,
                len(metadata_candidates),
                skipped_no_signal,
            )

            raw_messages: list[dict] = []
            skipped_full_fetch = 0
            for metadata in metadata_candidates:
                message_id = metadata["id"]
                try:
                    # $expand=attachments lấy kèm metadata file trong CÙNG
                    # lượt gọi — tách ra thành request riêng cho mỗi mail sẽ
                    # nhân đôi số lần gọi Graph chỉ để biết tên file.
                    # $select bên trong giới hạn field để không kéo cả
                    # contentBytes (base64 toàn bộ file) về đây.
                    raw = await self._get(
                        client,
                        f"{API_BASE}/messages/{message_id}",
                        params={
                            "$select": _FULL_SELECT,
                            "$expand": "attachments($select=id,name,contentType,size,isInline)",
                        },
                    )
                except OutlookAPIError as exc:
                    skipped_full_fetch += 1
                    logger.warning("Bỏ qua message %s (lỗi lấy full body): %s", message_id, exc)
                    continue
                raw_messages.append(raw)
                if on_item is not None:
                    on_item(raw, raw.get("subject") or "(không có tiêu đề)")
            if skipped_full_fetch:
                logger.warning(
                    "Outlook fetch_range %s: %d message bị bỏ qua khi lấy full body (batch vẫn tiếp tục).",
                    source.id,
                    skipped_full_fetch,
                )
        return raw_messages

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Tải bytes thật của 1 file đính kèm. Chữ ký khớp GmailConnector để
        attachment_extract_node gọi được mà không cần biết provider.

        Graph trả `contentBytes` dạng base64 trong JSON (giống Gmail), không
        stream — caller tự lo giới hạn kích thước.
        """
        token = await self._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
            body = await self._get(client, f"{API_BASE}/messages/{message_id}/attachments/{attachment_id}")
        data = body.get("contentBytes")
        if not data:
            raise OutlookAPIError(f"Attachment {attachment_id} không có contentBytes (có thể là item đính kèm).")
        return base64.b64decode(data)

    def normalize(self, raw_item: dict, source: Source) -> dict:
        from_address = ((raw_item.get("from") or {}).get("emailAddress") or {})
        from_email = (from_address.get("address") or "").lower()
        from_name = from_address.get("name") or from_email or None

        to_addresses = [
            (r.get("emailAddress") or {}).get("address", "").lower()
            for r in raw_item.get("toRecipients", []) or []
            if (r.get("emailAddress") or {}).get("address")
        ]
        cc_addresses = [
            (r.get("emailAddress") or {}).get("address", "").lower()
            for r in raw_item.get("ccRecipients", []) or []
            if (r.get("emailAddress") or {}).get("address")
        ]

        text = _extract_body_text(raw_item.get("body") or {})
        sent_at = _received_datetime(raw_item.get("receivedDateTime"))

        provider_user_id = (self._connection.provider_user_id or "").lower()
        is_self = bool(from_email) and bool(provider_user_id) and from_email == provider_user_id

        return {
            "id": raw_item["id"],
            "source_id": source.id,
            "provider": "outlook",
            "thread_id": raw_item.get("conversationId"),
            "author_id": from_email or None,
            "author_name": from_name,
            "subject": raw_item.get("subject") or "",
            "to": to_addresses,
            "cc": cc_addresses,
            # Xem comment tương ứng trong src/connectors/gmail.py — mailbox
            # thật của connection, khác User.email đăng nhập app.
            "mailbox_email": provider_user_id or None,
            "snippet": raw_item.get("bodyPreview", ""),
            # Outlook không có nhãn kiểu Gmail — hasAttachments là field duy
            # nhất còn lại đáng lưu ở vị trí tương đương.
            "label_ids": [],
            "is_unread": not raw_item.get("isRead", True),
            "has_thread_change": True,
            "is_self": is_self,
            "is_dm": False,
            "text": text,
            "normalized_text": _normalize_email_text(text),
            "attachments": _extract_attachment_metadata(raw_item),
            "sent_at": sent_at,
            "deep_link": self.deep_link(raw_item),
            "capture_mode": "outlook_graph_api",
        }

    def deep_link(self, raw_item: dict) -> str:
        # Graph trả sẵn webLink — không cần tự dựng URL như Gmail.
        return raw_item.get("webLink") or ""


def _extract_body_text(body: dict) -> str:
    content = body.get("content") or ""
    if body.get("contentType") == "html":
        content = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", content)
        return re.sub(r"(?s)<[^>]+>", " ", html.unescape(content))
    return content


def _normalize_email_text(text: str) -> str:
    """Stable display/search text; raw ``text`` remains available for evidence."""
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()


def _received_datetime(value: str | None) -> datetime | str:
    if not value:
        return "unknown"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (TypeError, ValueError):
        return "unknown"
