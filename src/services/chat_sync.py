"""Đồng bộ tự bật từ trang chat (thay cho việc người dùng phải bấm Sync tay).

Người dùng trước đây phải vào Thư viện nguồn bấm Đồng bộ thì mới thấy task mới.
Module này chuyển việc đó sang trang chat, nhưng CHỈ cho câu chat đang hỏi về
task/lịch/công việc/Gmail/Jira (`asks_about_work`) — câu chào hỏi hay hỏi
chung chung không kéo đồng bộ, trả lời ngay cho nhanh. Trong số câu hỏi việc
đó: câu đầu tiên trong ngày tự kéo một lần đồng bộ; các câu sau chỉ ép đồng bộ
lại nếu dữ liệu đã quá `chat_sync_stale_minutes`.

Khác `auto_sync.py` ở hai điểm cốt lõi:

* `auto_sync` chạy nền theo nhịp phút và TUYỆT ĐỐI không tự chọn nguồn — nó sao
  chép nguyên bộ nguồn của lần Sync tay gần nhất. Ở đây nút Sync tay bị ẩn nên
  ràng buộc đó sẽ khoá chết người dùng mới: không có run tay nào để sao chép.
  Nên đường này tự khám phá TOÀN BỘ nguồn đang kết nối (quyết định của chủ sở
  hữu sản phẩm, 2026-08-21). Vẫn không đụng tới provider mà người dùng chưa tự
  tay nối — kết nối OAuth vẫn là hành động có ý thức của họ.
* `auto_sync` chạy trong worker nền; đường này chạy đồng bộ ngay trong request
  chat, người dùng ngồi chờ và xem tiến trình.

Quyết định "có đồng bộ hay không" tách hẳn khỏi phần thực thi để kiểm chứng
được bằng test thuần, không cần mạng.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.connectors.base import ConnectorAPIError, Source
from src.connectors.registry import bindings_for_provider, public_source
from src.models.connection import Connection
from src.models.run import Run
from src.models.schemas import RunCreateRequest, SyncSourceRef

logger = logging.getLogger(__name__)

# Trạng thái kết nối coi như không dùng được — giống bộ lọc ở gmail_tools.py.
_DEAD_CONNECTION_STATUSES = ("disconnected", "error", "expired", "revoked")

# Gmail trả về mọi label (kể cả label người dùng tự tạo). Quét hết là quét lại
# cùng một mail nhiều lần và ăn sạch trần max_sync_sources — chỉ lấy hộp thư
# chính, đúng như trang briefing vẫn làm.
_GMAIL_PRIMARY_SOURCE_IDS = frozenset({"INBOX"})


@dataclass(frozen=True)
class SyncDecision:
    """Có nên kéo đồng bộ cho câu chat này không, và vì sao."""

    should_sync: bool
    reason: str
    # Khoá idempotency: cùng khoá thì enqueue_run() trả lại run cũ thay vì chạy
    # lần hai. None khi không đồng bộ.
    idempotency_key: str | None = None


def _local_day(moment: datetime, timezone: str) -> str:
    """Ngày theo múi giờ NGƯỜI DÙNG, không phải UTC.

    "Câu chat đầu tiên trong ngày" phải theo lịch người dùng đang nhìn; chốt
    theo UTC thì người ở GMT+7 sẽ thấy mốc ngày nhảy vào lúc 7 giờ sáng.
    """
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = UTC
    return moment.astimezone(zone).date().isoformat()


def _latest_run(db: Session, user_id: int, statuses: tuple[str, ...] | None = None) -> Run | None:
    stmt = select(Run).where(Run.user_id == user_id)
    if statuses is not None:
        stmt = stmt.where(Run.status.in_(statuses))
    return db.execute(stmt.order_by(Run.created_at.desc()).limit(1)).scalar_one_or_none()


def _as_utc(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def decide(
    db: Session,
    user_id: int,
    *,
    asks_about_work: bool,
    timezone: str = "UTC",
    now: datetime | None = None,
) -> SyncDecision:
    """Quyết định cho ĐÚNG một câu chat.

    Thứ tự xét, rẻ tiền trước:

    1. Đang có run `queued`/`running` -> không chen ngang. Câu trả lời vẫn dựng
       được từ dữ liệu sẵn có, và enqueue thêm chỉ đâm vào trần per-user.
    2. Câu chat KHÔNG hỏi về task/lịch/công việc/Gmail/Jira (chào hỏi, hỏi
       chung chung...) -> không đồng bộ, trả lời ngay cho nhanh. Trước đây câu
       chat đầu tiên trong ngày luôn kéo đồng bộ bất kể nội dung — kể cả một
       câu "hi" cũng phải chờ hết lượt discover_sync_sources() rồi mới trả
       lời, chậm vô lý cho phần lớn lượt chat không liên quan tới dữ liệu.
    3. Hôm nay (theo múi giờ người dùng) chưa có run nào -> đồng bộ. Đây là
       "câu hỏi việc đầu tiên trong ngày".
    4. Câu hỏi thẳng về công việc mà run gần nhất đã quá `chat_sync_stale_minutes`
       -> đồng bộ lại. Hỏi "tôi có task gì" mà trả lời bằng dữ liệu từ sáng thì
       vô nghĩa.
    5. Còn lại -> không đồng bộ, trả lời từ dữ liệu đang có.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)
    day = _local_day(now, timezone)

    if _latest_run(db, user_id, ("queued", "running")) is not None:
        return SyncDecision(False, "run_in_progress")

    if not asks_about_work:
        return SyncDecision(False, "not_a_work_question")

    last = _latest_run(db, user_id)
    last_at = _as_utc(last.created_at) if last is not None else None

    if last_at is None or _local_day(last_at, timezone) != day:
        return SyncDecision(True, "first_work_question_of_day", f"chat-{user_id}-{day}")

    stale_after = timedelta(minutes=settings.chat_sync_stale_minutes)
    if now - last_at >= stale_after:
        # Ô thời gian, không phải thời điểm gọi: hai câu hỏi cách nhau vài
        # giây rơi vào cùng ô -> cùng khoá -> không chạy hai lần.
        bucket = int(now.timestamp()) // (settings.chat_sync_stale_minutes * 60)
        return SyncDecision(True, "stale_work_question", f"chat-{user_id}-{day}-{bucket}")

    return SyncDecision(False, "recent_enough")


def _by_priority(ref: SyncSourceRef, mailbox_by_connection: dict[int, str]) -> tuple[int, str]:
    """Thứ tự giữ lại khi vượt trần `max_sync_sources`.

    Không phải nguồn nào cũng đáng giá như nhau. Tài khoản Google có thể mang
    theo hàng chục lịch được chia sẻ (Classroom, lịch nhóm...) mà người dùng
    chưa từng chọn; để chúng chen lên trước thì hộp thư chính và dự án Jira bị
    đẩy ra ngoài — lỗi thật đã gặp: 9 lịch Classroom chiếm trọn trần 10.

    Bậc ưu tiên:
      0. Hộp thư chính — nguồn việc đậm đặc nhất.
      1. Nguồn không phải lịch (dự án Jira, thư mục Outlook...) — mỗi kết nối
         chỉ có vài cái, không có nguy cơ tràn.
      2. Lịch CHÍNH của người dùng (id trùng địa chỉ mailbox).
      3. Lịch được chia sẻ và mọi thứ còn lại.
    """
    source_id = ref.source_id
    if source_id == "INBOX":
        return (0, source_id)
    if not source_id.startswith("calendar:"):
        return (1, source_id)
    mailbox = (mailbox_by_connection.get(ref.connection_id) or "").lower()
    if mailbox and source_id.lower() == f"calendar:{mailbox}":
        return (2, source_id)
    return (3, source_id)


async def discover_sync_sources(db: Session, user_id: str) -> list[SyncSourceRef]:
    """Toàn bộ nguồn thuộc các kết nối đang sống của user.

    Một connector lỗi (token hết hạn, provider 5xx) không được làm hỏng cả lần
    đồng bộ — bỏ qua đúng connector đó, giữ phần còn lại. Trả về rỗng nghĩa là
    không có gì để quét, caller tự xử lý chứ không raise: người dùng hỏi một
    câu chat mà nhận lại lỗi 502 vì Jira sập là vô lý.
    """
    connections = (
        db.execute(
            select(Connection).where(
                Connection.user_id == str(user_id),
                Connection.status.notin_(_DEAD_CONNECTION_STATUSES),
            )
        )
        .scalars()
        .all()
    )

    refs: list[SyncSourceRef] = []
    for connection in connections:
        bindings = bindings_for_provider(connection.provider)
        namespaced = len(bindings) > 1
        for binding in bindings:
            try:
                found: list[Source] = await binding.connector_cls(connection, db).list_sources()
            except ConnectorAPIError as exc:
                logger.info(
                    "chat_sync bỏ qua %s/%s của connection %s: %s",
                    connection.provider,
                    binding.namespace,
                    connection.id,
                    exc,
                )
                continue
            except Exception:  # noqa: BLE001 - 1 connector hỏng không được giết cả lần đồng bộ
                logger.exception(
                    "chat_sync lỗi ngoài dự kiến khi liệt kê %s/%s", connection.provider, binding.namespace
                )
                continue

            for source in found:
                if binding.connector_cls.__name__ == "GmailConnector" and source.id not in _GMAIL_PRIMARY_SOURCE_IDS:
                    continue
                source_id, _ = public_source(binding, source.id, source.name, namespaced=namespaced)
                refs.append(SyncSourceRef(connection_id=connection.id, source_id=source_id))

    # KHÔNG cắt trần ở đây. Cắt trước khi xếp ưu tiên là cắt mù: một tài khoản
    # có 9 lịch Google Classroom sẽ ăn sạch trần và đẩy văng chính hộp thư
    # INBOX lẫn dự án Jira. Caller cắt sau khi đã xếp — xem `_by_priority`.
    return refs


async def build_chat_run_request(
    db: Session,
    user_id: int,
    decision: SyncDecision,
    *,
    language: str,
    timezone: str,
    now: datetime | None = None,
) -> RunCreateRequest | None:
    """Payload Run cho lần đồng bộ do chat kích hoạt. None khi không có nguồn.

    HỢP của (nguồn khám phá được từ mọi kết nối đang sống) và (nguồn của lần
    Sync thành công gần nhất).

    Bản đầu ưu tiên run cũ và CHỈ khám phá khi chưa từng có run nào. Nghe thì
    rẻ, nhưng nó khoá chết người dùng vào bộ nguồn họ lỡ chọn một lần: tài
    khoản đã có vài run Gmail từ trước rồi nối thêm Jira sẽ không bao giờ quét
    Jira, vì nhánh khám phá không còn chạy. Đúng lỗi thật đã gặp.

    Vẫn giữ nguồn của run cũ trong phép hợp để không đánh rơi lựa chọn tường
    minh của người dùng (vd một label Gmail cụ thể mà `discover` bỏ qua), và để
    một provider đang lỗi tạm thời không làm co bộ nguồn lại.
    """
    settings = get_settings()
    now = now or datetime.now(UTC)

    discovered = await discover_sync_sources(db, str(user_id))

    last_ok = _latest_run(db, user_id, ("succeeded",))
    previous: list[SyncSourceRef] = []
    if last_ok is not None and last_ok.sources:
        previous = [SyncSourceRef.model_validate(item) for item in last_ok.sources]

    seen: set[tuple[int, str]] = set()
    merged: list[SyncSourceRef] = []
    for ref in [*discovered, *previous]:
        key = (ref.connection_id, ref.source_id)
        if key in seen:
            continue
        seen.add(key)
        merged.append(ref)

    if not merged:
        return None

    mailbox_by_connection = {
        row.id: (row.provider_user_id or "")
        for row in db.execute(select(Connection).where(Connection.user_id == str(user_id))).scalars()
    }
    # Xếp ưu tiên RỒI mới cắt: cắt theo thứ tự connector trả về sẽ đánh rơi
    # hộp thư chính vì hàng chục lịch chia sẻ chen lên trước.
    merged.sort(key=lambda ref: _by_priority(ref, mailbox_by_connection))
    sources = merged[: settings.max_sync_sources]

    return RunCreateRequest(
        sources=sources,
        time_from=now - timedelta(hours=settings.chat_sync_range_hours),
        time_to=now,
        timezone=timezone,
        language=language,
        idempotency_key=decision.idempotency_key or f"chat-{user_id}-{int(now.timestamp())}",
        # Chat hỏi việc thì cần task, không phải bản tóm tắt — luồng tóm tắt
        # mail vẫn đi đường mode="summary" riêng của nó, không đổi.
        mode="task_extraction",
    )
