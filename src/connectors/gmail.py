from __future__ import annotations

import asyncio
import base64
import html
import logging
import re
from datetime import UTC, datetime
from email.utils import getaddresses, parseaddr
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.services.connections import google

logger = logging.getLogger(__name__)

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Chỉ 3 nhãn hệ thống có ý nghĩa ở bản đầu — nhãn user tự tạo bỏ qua, mở
# rộng sau nếu cần (xem prompt TAPB-121).
_KNOWN_LABELS = {
    "INBOX": "Hộp thư chính",
    "CATEGORY_PROMOTIONS": "Quảng cáo",
    "CATEGORY_SOCIAL": "Mạng xã hội",
}

_EVIDENCE_HINTS = re.compile(
    r"(?i)urgent|action required|deadline|due|submit|reply|respond|review|confirm|"
    r"mentor|course|class|assignment|project|milestone|demo|vlearn|canvas|jira|"
    r"hạn|nộp|phản hồi|yêu cầu|cần làm|thứ [2-7]"
)
_MAX_METADATA_CANDIDATES = 80
# Chặn vòng phân trang list id phình vô hạn trên hộp thư lớn — 1000 id là
# dư so với _MAX_METADATA_CANDIDATES (80), đủ biên độ để lọc rồi vẫn đủ 80.
_MAX_MESSAGE_IDS = 1000
_MAX_RATE_LIMIT_RETRIES = 5


class GmailAPIError(ConnectorAPIError):
    """Lỗi gọi Gmail API — message đã làm sạch, an toàn để lộ ra route/SSE."""


class GmailConnector(BaseConnector):
    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await google.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise GmailAPIError(f"Không lấy được access token Gmail: {exc}") from exc

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.get(f"{API_BASE}{path}", params=params)
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                logger.warning(
                    "Gmail API rate limit tại %s, chờ %.1fs (lần %d/%d)",
                    path,
                    wait_seconds,
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                raise GmailAPIError(f"Gmail API lỗi {response.status_code} tại {path}")
            return response.json()
        raise GmailAPIError(f"Gmail API vẫn rate limit sau {_MAX_RATE_LIMIT_RETRIES} lần thử tại {path}")

    async def list_sources(self) -> list[Source]:
        token = await self._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            body = await self._get(client, "/labels")

        by_id = {label["id"]: label for label in body.get("labels", [])}
        sources: list[Source] = []
        for label_id, display_name in _KNOWN_LABELS.items():
            label = by_id.get(label_id)
            if label is None:
                continue
            sources.append(Source(id=label_id, name=display_name, item_count=label.get("messagesTotal")))
        return sources

    async def fetch_range(
        self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None
    ) -> list[dict]:
        token = await self._access_token()
        after_ts = int(time_from.timestamp())
        before_ts = int(time_to.timestamp())
        query = f"label:{source.id} after:{after_ts} before:{before_ts}"

        message_ids: list[str] = []
        page_token: str | None = None
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while len(message_ids) < _MAX_MESSAGE_IDS:
                params: dict = {"q": query, "maxResults": 100}
                if page_token:
                    params["pageToken"] = page_token
                page = await self._get(client, "/messages", params=params)
                message_ids.extend(m["id"] for m in page.get("messages", []))
                page_token = page.get("nextPageToken")
                if not page_token:
                    break
            else:
                logger.warning(
                    "Gmail list id chạm cap %d cho query %r — có thể còn id chưa liệt kê.",
                    _MAX_MESSAGE_IDS,
                    query,
                )
            message_ids = message_ids[:_MAX_MESSAGE_IDS]

            # Evidence-first fetch: inspect cheap headers/snippets first and
            # only download full MIME bodies for messages with an actionable
            # signal. This prevents the LLM path from ingesting the mailbox.
            metadata_candidates: list[dict] = []
            skipped_no_signal = 0
            skipped_error = 0
            truncated_by_cap = False
            for message_id in message_ids:
                if len(metadata_candidates) >= _MAX_METADATA_CANDIDATES:
                    truncated_by_cap = True
                    break
                try:
                    metadata = await self._get(
                        client,
                        f"/messages/{message_id}",
                        params={
                            "format": "metadata",
                            "metadataHeaders": ["From", "To", "Cc", "Subject", "Date"],
                        },
                    )
                except GmailAPIError as exc:
                    skipped_error += 1
                    logger.warning("Bỏ qua message %s (lỗi lấy metadata): %s", message_id, exc)
                    continue
                labels = set(metadata.get("labelIds", []))
                headers = {
                    header.get("name", "").lower(): header.get("value", "")
                    for header in metadata.get("payload", {}).get("headers", [])
                }
                hint_text = " ".join([headers.get("subject", ""), headers.get("from", ""), metadata.get("snippet", "")])
                signalled = bool(labels.intersection({"UNREAD", "IMPORTANT", "STARRED"})) or bool(
                    _EVIDENCE_HINTS.search(hint_text)
                )
                if signalled:
                    metadata_candidates.append(metadata)
                else:
                    skipped_no_signal += 1
            if truncated_by_cap:
                logger.warning(
                    "Gmail metadata candidates chạm cap %d — phần id còn lại chưa được xét.",
                    _MAX_METADATA_CANDIDATES,
                )
            logger.info(
                "Gmail fetch_range %s: %d id -> %d candidate (%d bỏ qua không tín hiệu, %d lỗi metadata)",
                source.id,
                len(message_ids),
                len(metadata_candidates),
                skipped_no_signal,
                skipped_error,
            )

            raw_messages: list[dict] = []
            skipped_full_fetch = 0
            for metadata in metadata_candidates:
                message_id = metadata["id"]
                try:
                    raw = await self._get(client, f"/messages/{message_id}", params={"format": "full"})
                except GmailAPIError as exc:
                    skipped_full_fetch += 1
                    logger.warning("Bỏ qua message %s (lỗi lấy full body): %s", message_id, exc)
                    continue
                raw_messages.append(raw)
                if on_item is not None:
                    subject = next(
                        (
                            h.get("value", "")
                            for h in metadata.get("payload", {}).get("headers", [])
                            if h.get("name", "").lower() == "subject"
                        ),
                        "(không có tiêu đề)",
                    )
                    on_item(raw, subject)
            if skipped_full_fetch:
                logger.warning(
                    "Gmail fetch_range %s: %d message bị bỏ qua khi lấy full body (batch vẫn tiếp tục).",
                    source.id,
                    skipped_full_fetch,
                )
        return raw_messages

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Tải bytes thật của 1 attachment — `_get`/`normalize` chỉ có
        metadata, không tự tải nội dung (chi phí/rủi ro chỉ chấp nhận khi
        caller (attachment_extract_node) đã quyết định cần đọc file này).

        Trả BYTES thô, không phải str — khác `_decode_base64url` (dùng cho
        thân mail dạng text, decode UTF-8). Caller tự lo giới hạn kích thước
        (Gmail vẫn trả JSON dù response gồm base64 nặng, không stream)."""
        token = await self._access_token()
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
            body = await self._get(client, f"/messages/{message_id}/attachments/{attachment_id}")
        data = body.get("data", "")
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded)

    def normalize(self, raw_item: dict, source: Source) -> dict:
        payload = raw_item.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        from_name, from_email = parseaddr(headers.get("from", ""))
        from_email = (from_email or "").lower()

        plain_text_raw = _extract_plain_text(payload)
        html_text_raw = "" if plain_text_raw else _extract_html_text(payload, strip=False)
        has_marketing_boilerplate = _has_marketing_boilerplate(plain_text_raw or html_text_raw)
        text = _strip_boilerplate(plain_text_raw) or _strip_boilerplate(html_text_raw)
        attachments = _extract_attachment_metadata(payload)
        to_addresses = [email.lower() for _, email in getaddresses([headers.get("to", "")]) if email]
        cc_addresses = [email.lower() for _, email in getaddresses([headers.get("cc", "")]) if email]
        sent_at = _internal_date_to_datetime(raw_item.get("internalDate"))

        provider_user_id = (self._connection.provider_user_id or "").lower()
        is_self = bool(from_email) and bool(provider_user_id) and from_email == provider_user_id

        return {
            "id": raw_item["id"],
            "source_id": source.id,
            "provider": "google",
            "thread_id": raw_item.get("threadId"),
            "author_id": from_email or None,
            "author_name": from_name or from_email or None,
            "subject": headers.get("subject", ""),
            "to": to_addresses,
            "cc": cc_addresses,
            # Địa chỉ mailbox THẬT SỰ đang đồng bộ — khác User.email (đăng nhập
            # app) khi user connect 1 Gmail account khác tài khoản app. Dùng
            # cái này để check "mail có gửi cho mình không" (filter_classify.py),
            # không dùng config.user_email vì nó là identity app, không phải
            # mailbox nguồn.
            "mailbox_email": provider_user_id or None,
            # Tín hiệu unsubscribe/preferences chấm TRƯỚC khi _strip_boilerplate
            # xoá nó khỏi "text" — filter_classify.py dùng cái này để không mất
            # dấu hiệu newsletter khi text hiển thị đã được làm sạch.
            "has_marketing_boilerplate": has_marketing_boilerplate,
            "snippet": raw_item.get("snippet", ""),
            "label_ids": list(raw_item.get("labelIds", [])),
            "is_unread": "UNREAD" in raw_item.get("labelIds", []),
            "has_thread_change": True,
            "is_self": is_self,
            "is_dm": False,
            "text": text,
            "normalized_text": _normalize_email_text(text),
            "attachments": attachments,
            "sent_at": sent_at,
            "deep_link": self.deep_link(raw_item),
            "capture_mode": "gmail_api",
        }

    def deep_link(self, raw_item: dict) -> str:
        source_url = raw_item.get("sourceUrl")
        if source_url:
            return source_url
        # /u/0/ chỉ là slot 0 mặc định — nếu trình duyệt đăng nhập nhiều Google
        # account và account đã kết nối không nằm ở slot 0, Gmail mở account
        # khác, không tìm thấy message, rồi rơi về Inbox thay vì vào thẳng nội
        # dung. authuser ép đúng account bất kể slot, cùng cách calendar.py
        # dùng cho Google Calendar (build_authuser_link).
        authuser = getattr(self._connection, "provider_user_id", None)
        query = f"?authuser={quote(authuser)}" if authuser else ""
        return f"https://mail.google.com/mail/u/0/{query}#all/{raw_item['id']}"


def _extract_plain_text(payload: dict) -> str:
    """Đệ quy tìm phần text/plain đầu tiên trong MIME tree, giải base64url."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return _decode_base64url(data)
        # Some Gmail fixtures/API responses put the actual MIME body in
        # parts even when the parent mimeType is text/plain.
        for part in payload.get("parts", []) or []:
            text = _extract_plain_text(part)
            if text:
                return text
        return ""

    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    return ""


_HIDDEN_BLOCK_RE = re.compile(
    r'(?is)<(div|span|td|p)\b[^>]*style\s*=\s*(["\']).*?'
    r'(?:display\s*:\s*none|visibility\s*:\s*hidden).*?\2[^>]*>.*?</\1>'
)

# Giọng văn boilerplate/footer tự động — không phải nội dung thư thật, nhưng
# bị _extract_html_text cũ nối lẫn vào text vì chỉ strip tag, không phân biệt
# nội dung chính với footer pháp lý/preheader ẩn. Cắt theo cụm tới hết câu
# (dấu . hoặc xuống dòng) để không phụ thuộc việc HTML nguồn có xuống dòng
# thật hay bị minify thành 1 dòng.
_BOILERPLATE_RE = re.compile(
    r"(?i)("
    r"unsubscribe[^.\n]*[.\n]?|"
    r"view (?:this|in) (?:the )?browser[^.\n]*[.\n]?|"
    r"update (?:your )?(?:email )?preferences[^.\n]*[.\n]?|"
    r"manage (?:your )?(?:email )?preferences[^.\n]*[.\n]?|"
    r"copyright\s*©[^.\n]*[.\n]?|"
    r"all rights reserved[^.\n]*[.\n]?|"
    r"do not reply to this email[^.\n]*[.\n]?|"
    r"vui lòng không (?:trả lời|phản hồi)[^.\n]*[.\n]?|"
    r"email này (?:được gửi )?tự động[^.\n]*[.\n]?|"
    r"bản quyền thuộc về[^.\n]*[.\n]?"
    r")"
)


# Chỉ phần lõi thật sự là tín hiệu "mail quảng cáo/hàng loạt" trong
# _BOILERPLATE_RE ở trên — dùng để chấm điểm TRƯỚC khi _strip_boilerplate xoá
# nó khỏi text hiển thị. Nếu không, filter_classify.py mất tín hiệu newsletter
# đúng lúc cần nhất: mail marketing (vd Font Awesome, Cursor...) lọt qua vòng
# lọc chỉ vì phần "unsubscribe"/"preferences" đã bị cắt sạch trước khi tới
# NEWSLETTER_FOLDED_TERMS.
_MARKETING_BOILERPLATE_RE = re.compile(
    r"(?i)unsubscribe|update (?:your )?(?:email )?preferences|manage (?:your )?(?:email )?preferences"
)


def _strip_boilerplate(text: str) -> str:
    return _BOILERPLATE_RE.sub(" ", text)


def _has_marketing_boilerplate(text: str) -> bool:
    return bool(_MARKETING_BOILERPLATE_RE.search(text))


def _extract_html_text(payload: dict, *, strip: bool = True) -> str:
    """Fallback for HTML-only mail; keeps text, removes markup and scripts."""
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data")
        if not data:
            return ""
        source = _decode_base64url(data)
        source = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", source)
        # display:none/visibility:hidden block: preheader text ẩn chỉ để hiện
        # preview trong inbox, không phải nội dung thư — cắt trước khi tag bị
        # strip phẳng, nếu không nó lẫn vào giữa nội dung thật.
        source = _HIDDEN_BLOCK_RE.sub(" ", source)
        text = re.sub(r"(?s)<[^>]+>", " ", html.unescape(source))
        return _strip_boilerplate(text) if strip else text
    return " ".join(_extract_html_text(part, strip=strip) for part in payload.get("parts", []) or []).strip()


def _extract_attachment_metadata(payload: dict) -> list[dict]:
    attachments: list[dict] = []
    for part in payload.get("parts", []) or []:
        filename = part.get("filename")
        body = part.get("body", {})
        if filename:
            attachments.append(
                {
                    "filename": filename,
                    "mimeType": part.get("mimeType", "application/octet-stream"),
                    "sizeBytes": int(body.get("size", 0) or 0),
                    # Cần để tải bytes thật qua messages/{id}/attachments/{attachmentId} —
                    # attachment nhỏ (<~3KB) đôi khi được Gmail nhúng thẳng body.data thay
                    # vì attachmentId; attachmentId None thì bỏ qua, không tải được.
                    "attachmentId": body.get("attachmentId"),
                }
            )
        attachments.extend(_extract_attachment_metadata(part))
    return attachments


def _normalize_email_text(text: str) -> str:
    """Stable display/search text; raw ``text`` remains available for evidence."""
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()


def _decode_base64url(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _internal_date_to_datetime(internal_date_ms: str | None) -> datetime | str:
    if not internal_date_ms:
        return "unknown"
    try:
        return datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return "unknown"
