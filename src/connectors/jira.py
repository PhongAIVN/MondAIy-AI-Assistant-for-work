from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
from dateutil import parser as dateutil_parser
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import BaseConnector, ConnectorAPIError, OnItemCallback, Source
from src.models.connection import Connection
from src.services.connections import jira as jira_oauth

logger = logging.getLogger(__name__)

API_BASE_TEMPLATE = "https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"

# Cap tổng số issue liệt kê per fetch_range, cùng tinh thần _MAX_MESSAGE_IDS
# bên gmail.py — áp ngay từ đầu, không đợi phát hiện thiếu như Gmail.
_MAX_ISSUES = 1000
_PAGE_SIZE = 100
_MAX_RATE_LIMIT_RETRIES = 5

# resolution/priority/issuetype/created thêm cho rule engine rule-based
# (src/services/jira_rules.py) — Hard Filter và Scoring cần đọc thẳng field
# có cấu trúc này, không suy luận từ text.
_ISSUE_FIELDS = [
    "summary",
    "description",
    "assignee",
    "reporter",
    "status",
    "duedate",
    "updated",
    "project",
    "resolution",
    "priority",
    "issuetype",
    "created",
    # Metadata file đính kèm — trước đây normalize() trả cứng "attachments": []
    # nên attachment_extract_node không có gì để tải, và tóm tắt Jira mất hẳn
    # phần nội dung file (đúng lỗi đã sửa cho Gmail).
    "attachment",
]

# Cùng allow-list với guardrail/attachment_safety.py. Lọc ngay từ connector để
# metadata của file không đọc được (zip, exe...) không chiếm chỗ trong
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


def _extract_attachment_metadata(fields: dict) -> list[dict]:
    """Đổi `fields.attachment[]` sang đúng shape mà attachment_extract_node đọc.

    `attachmentId` giữ nguyên id Jira; `contentUrl` lưu kèm vì Jira trả link
    tải trực tiếp chứ không có endpoint dạng `/attachments/{id}` như Gmail.
    """
    metadata: list[dict] = []
    for item in fields.get("attachment") or []:
        mime_type = item.get("mimeType") or ""
        if mime_type not in _EXTRACTABLE_MIME_TYPES:
            continue
        metadata.append(
            {
                "filename": item.get("filename") or "(không tên)",
                "mimeType": mime_type,
                "sizeBytes": int(item.get("size") or 0),
                "attachmentId": str(item.get("id") or ""),
                "contentUrl": item.get("content") or "",
            }
        )
    return metadata

# statusCategory.key chỉ có đúng 3 giá trị cố định bất kể workflow tuỳ biến
# tên status ra sao — dùng key để suy ra status_category ổn định, KHÔNG dùng
# tên status hiển thị (có thể đổi theo từng project).
_STATUS_CATEGORY_BY_KEY = {"new": "To Do", "indeterminate": "In Progress", "done": "Done"}


class JiraAPIError(ConnectorAPIError):
    """Lỗi gọi Jira API — message đã làm sạch, an toàn để lộ ra route/SSE."""


class JiraConnector(BaseConnector):
    def __init__(self, connection: Connection, db: Session) -> None:
        self._connection = connection
        self._db = db

    async def _access_token(self) -> str:
        try:
            return await jira_oauth.ensure_valid_access_token(self._db, self._connection)
        except (ValueError, httpx.HTTPError) as exc:
            raise JiraAPIError(f"Không lấy được access token Jira: {exc}") from exc

    def _api_base(self) -> str:
        cloud_id = self._connection.external_site_id
        if not cloud_id:
            raise JiraAPIError("Kết nối Jira thiếu cloud_id — cần kết nối lại.")
        return API_BASE_TEMPLATE.format(cloud_id=cloud_id)

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict | None = None) -> dict:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.get(f"{self._api_base()}{path}", params=params)
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                logger.warning(
                    "Jira API rate limit tại %s, chờ %.1fs (lần %d/%d)",
                    path,
                    wait_seconds,
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                raise JiraAPIError(f"Jira API lỗi {response.status_code} tại {path}")
            return response.json()
        raise JiraAPIError(f"Jira API vẫn rate limit sau {_MAX_RATE_LIMIT_RETRIES} lần thử tại {path}")

    async def _post(self, client: httpx.AsyncClient, path: str, json_body: dict) -> dict:
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            response = await client.post(f"{self._api_base()}{path}", json=json_body)
            if response.status_code == 429 and attempt < _MAX_RATE_LIMIT_RETRIES:
                wait_seconds = float(response.headers.get("retry-after", 1))
                logger.warning(
                    "Jira API rate limit tại %s, chờ %.1fs (lần %d/%d)",
                    path,
                    wait_seconds,
                    attempt + 1,
                    _MAX_RATE_LIMIT_RETRIES,
                )
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                raise JiraAPIError(f"Jira API lỗi {response.status_code} tại {path}")
            return response.json()
        raise JiraAPIError(f"Jira API vẫn rate limit sau {_MAX_RATE_LIMIT_RETRIES} lần thử tại {path}")

    async def list_sources(self) -> list[Source]:
        token = await self._access_token()
        sources: list[Source] = []
        start_at = 0
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while True:
                body = await self._get(client, "/project/search", params={"startAt": start_at, "maxResults": 50})
                for project in body.get("values", []):
                    sources.append(Source(id=project["key"], name=project.get("name", project["key"])))
                if body.get("isLast", True):
                    break
                start_at += len(body.get("values", []))
        return sources

    async def ensure_account_id(self) -> str | None:
        """Lấy và lưu accountId Atlassian của chính người dùng nếu còn thiếu.

        `provider_user_id` được đặt lúc kết nối OAuth, nhưng lần gọi đó có thể
        thất bại lặng lẽ — kết nối vẫn "thành công" với accountId rỗng. Hậu quả
        không nhìn thấy được: `CurrentUserContext.account_id` rỗng nên
        `jira_rules` không đối chiếu được assignee, luật "việc của tôi" nằm im
        và điểm ASSIGNED_TO_CURRENT_USER không bao giờ cộng. Bảng thật của
        người dùng có 31 issue mang tên họ mà không issue nào được nhận diện.

        Tự chữa ở đây thay vì bắt kết nối lại: chỉ đọc, chạy 1 lần rồi lưu.
        Lỗi mạng không được làm hỏng cả lần đồng bộ — trả None, lần sau thử lại.
        """
        existing = (self._connection.provider_user_id or "").strip()
        if existing:
            return existing

        try:
            token = await self._access_token()
            account_id_raw = await jira_oauth.fetch_account_id(token, self._connection.external_site_id or "")
        except Exception as exc:  # noqa: BLE001 - thiếu định danh không được sập run
            logger.warning("Không lấy được accountId Jira cho connection %s: %s", self._connection.id, exc)
            return None

        account_id = (account_id_raw or "").strip().lower()
        if not account_id:
            return None

        # Ghi bằng session RIÊNG, không commit vào `self._db`. `fetch_range`
        # chạy trong asyncio.gather cùng các nguồn khác trên CÙNG một Session
        # của pipeline; commit ở đây sẽ đẩy luôn phần dở dang của những nguồn
        # đang chạy song song, và Session của SQLAlchemy vốn không an toàn khi
        # dùng đồng thời. Giá trị này độc lập với transaction của lần đồng bộ
        # nên tách ra là đúng nghĩa.
        from src.db import SessionLocal

        try:
            with SessionLocal() as session:
                row = session.get(Connection, self._connection.id)
                if row is not None and not (row.provider_user_id or "").strip():
                    row.provider_user_id = account_id
                    session.commit()
        except Exception as exc:  # noqa: BLE001 - lưu hỏng thì lần sau lấy lại
            logger.warning("Không lưu được accountId Jira cho connection %s: %s", self._connection.id, exc)

        # Cập nhật bản trong bộ nhớ để chính lần chạy này dùng được ngay.
        self._connection.provider_user_id = account_id
        logger.info("Đã bổ sung accountId Jira cho connection %s", self._connection.id)
        return account_id

    async def fetch_range(
        self, source: Source, time_from: datetime, time_to: datetime, on_item: OnItemCallback | None = None
    ) -> list[dict]:
        token = await self._access_token()
        # Định danh người dùng phải có TRƯỚC khi rule engine chấm, nếu không
        # luật "việc của tôi" nằm im (xem ensure_account_id).
        await self.ensure_account_id()

        # Issue tracker chuyển động chậm hơn hộp thư nhiều: đo trên bảng thật,
        # cửa sổ 72 giờ của lần đồng bộ trả về 0 issue trong khi 30 ngày trả về
        # 139. Nới sàn RIÊNG cho Jira thay vì nới cửa sổ chung — nới chung thì
        # mỗi lần đồng bộ phải quét lại cả tháng mail.
        floor = time_to - timedelta(days=get_settings().jira_min_lookback_days)
        window_start = min(time_from, floor)

        jql = (
            f'project = "{source.id}" AND updated >= "{window_start:%Y-%m-%d %H:%M}" '
            # DESC, không phải ASC. Cap _MAX_ISSUES cắt phần ĐUÔI của kết
            # quả: xếp tăng dần thì phần bị cắt là issue MỚI NHẤT — đúng thứ
            # người dùng cần. Bảng của một đội thật dễ vượt 1000 issue cập nhật
            # trong 30 ngày, và sàn lookback 30 ngày càng làm dễ chạm cap hơn.
            f'AND updated <= "{time_to:%Y-%m-%d %H:%M}" ORDER BY updated DESC'
        )

        # GET /rest/api/3/search bị Atlassian khai tử (410 Gone) — chuyển sang
        # POST /search/jql, cursor pagination bằng nextPageToken, KHÔNG còn
        # startAt/total (Atlassian bỏ hẳn tổng số vì lý do hiệu năng).
        issues: list[dict] = []
        next_page_token: str | None = None
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15) as client:
            while len(issues) < _MAX_ISSUES:
                body: dict = {"jql": jql, "maxResults": _PAGE_SIZE, "fields": _ISSUE_FIELDS}
                if next_page_token:
                    body["nextPageToken"] = next_page_token
                page = await self._post(client, "/search/jql", body)
                batch = page.get("issues", [])
                if not batch:
                    break
                for issue in batch:
                    if len(issues) >= _MAX_ISSUES:
                        break
                    issues.append(issue)
                    if on_item is not None:
                        summary = (issue.get("fields") or {}).get("summary") or "(không có tiêu đề)"
                        on_item(issue, summary)
                next_page_token = page.get("nextPageToken")
                if not next_page_token:
                    break
            else:
                logger.warning(
                    "Jira issue list chạm cap %d cho JQL %r — có thể còn issue chưa liệt kê.", _MAX_ISSUES, jql
                )
        return issues[:_MAX_ISSUES]

    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Tải bytes thật của 1 file đính kèm trên issue.

        Chữ ký khớp `GmailConnector.download_attachment` để
        attachment_extract_node gọi được mà không cần biết provider nào. Jira
        trả link tải trực tiếp (`fields.attachment[].content`) chứ không có
        endpoint `/attachments/{id}`, nên phải tra lại issue để lấy link —
        link đó có hạn và không lưu lại được từ lần fetch trước.

        `follow_redirects` bắt buộc: Jira chuyển hướng sang media CDN.
        """
        token = await self._access_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            issue = await self._get(client, f"/issue/{message_id}", params={"fields": "attachment"})
            content_url = next(
                (
                    item.get("content")
                    for item in (issue.get("fields", {}).get("attachment") or [])
                    if str(item.get("id") or "") == str(attachment_id)
                ),
                None,
            )
            if not content_url:
                raise JiraAPIError(f"Không tìm thấy attachment {attachment_id} trên issue {message_id}.")
            response = await client.get(content_url)
            if response.status_code != 200:
                raise JiraAPIError(f"Tải attachment {attachment_id} thất bại: HTTP {response.status_code}")
            return response.content

    def normalize(self, raw_item: dict, source: Source) -> dict:
        fields = raw_item.get("fields", {})
        reporter = fields.get("reporter") or {}
        assignee = fields.get("assignee") or {}
        status = fields.get("status") or {}

        text = _extract_adf_text(fields.get("description")).strip()
        due_date = fields.get("duedate")
        if due_date:
            # Câu tường minh có đủ ngày/giờ/timezone để resolve_due_at() bắt
            # được nguyên vẹn, không cần sửa gì ở time_resolve.py.
            text = f"{text}\n\nHạn chót: {due_date} 00:00 (Asia/Ho_Chi_Minh)".strip()

        reporter_id = (reporter.get("accountId") or "").lower()
        assignee_id = (assignee.get("accountId") or "").lower()
        provider_user_id = (self._connection.provider_user_id or "").lower()
        is_self = bool(assignee_id) and bool(provider_user_id) and assignee_id == provider_user_id
        sent_at = _parse_jira_datetime(fields.get("updated"))

        status_category_key = ((status.get("statusCategory") or {}).get("key") or "").lower()
        status_category = _STATUS_CATEGORY_BY_KEY.get(status_category_key, status.get("name", ""))
        resolution = fields.get("resolution")
        priority = fields.get("priority") or {}
        issuetype = fields.get("issuetype") or {}
        due_date_raw = _parse_jira_date(due_date) if due_date else None
        created_at = _parse_jira_datetime(fields.get("created"))

        return {
            "id": raw_item["key"],
            "source_id": source.id,
            "provider": "jira",
            "thread_id": raw_item.get("key"),
            "author_id": reporter_id or None,
            "author_name": reporter.get("displayName") or None,
            "subject": fields.get("summary", ""),
            "to": [],
            "cc": [],
            "snippet": text[:200],
            "label_ids": [status["name"]] if status.get("name") else [],
            "is_unread": False,
            "has_thread_change": True,
            "is_self": is_self,
            "is_dm": False,
            "text": text,
            "normalized_text": _normalize_issue_text(text),
            "attachments": _extract_attachment_metadata(fields),
            "sent_at": sent_at,
            "deep_link": self.deep_link(raw_item),
            "capture_mode": "jira_api",
            # Field có cấu trúc riêng cho rule engine (src/services/jira_rules.py)
            # — Hard Filter/Scoring đọc thẳng từ đây, không suy luận từ "text".
            "jira_assignee_account_id": assignee_id or None,
            # Tên hiển thị cho dòng nguồn "[Giao cho: ...]" — accountId là
            # chuỗi hash, đọc ra không ai biết là ai.
            "jira_assignee_name": assignee.get("displayName") or None,
            "jira_status": status.get("name", ""),
            "jira_status_category": status_category,
            "jira_resolution": resolution.get("name") if isinstance(resolution, dict) else None,
            "jira_priority": priority.get("name"),
            "jira_issue_type": issuetype.get("name", ""),
            "jira_due_date": due_date_raw,
            "jira_created_at": created_at if isinstance(created_at, datetime) else None,
        }

    def deep_link(self, raw_item: dict) -> str:
        site_url = (self._connection.account_label or "").rstrip("/")
        key = raw_item.get("key", "")
        if not site_url:
            return f"https://atlassian.net/browse/{key}"
        return f"{site_url}/browse/{key}"


def _extract_adf_text(node: dict | None) -> str:
    """Bóc text thuần từ Atlassian Document Format — đệ quy theo content[],
    tương tự _extract_plain_text bên gmail.py. Không giữ định dạng, chỉ giữ
    nội dung + ranh giới đoạn."""
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")

    children = node.get("content") or []
    text = "".join(_extract_adf_text(child) for child in children)
    if node_type in {"paragraph", "heading", "codeBlock", "blockquote", "listItem"}:
        return text + "\n"
    return text


def _normalize_issue_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()


def _parse_jira_datetime(value: str | None) -> datetime | str:
    if not value:
        return "unknown"
    try:
        parsed = dateutil_parser.parse(value)
    except (ValueError, OverflowError):
        return "unknown"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_jira_date(value: str | None) -> datetime | None:
    """duedate là chuỗi "YYYY-MM-DD" (không giờ) — trả None nếu thiếu/hỏng
    thay vì sentinel "unknown" như _parse_jira_datetime, vì rule engine
    (src/services/jira_rules.py) cần Optional[datetime] sạch cho due_date."""
    if not value:
        return None
    try:
        parsed = dateutil_parser.parse(value)
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
