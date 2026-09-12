"""Đọc danh sách việc đã trích ra từ các nguồn (UC-01).

Vì sao không dùng discord_search_program cho việc này: truy hồi xếp hạng theo độ liên
quan ngữ nghĩa, nên "việc nào tới hạn tuần này" sẽ ra vài đoạn chat nói về hạn
chót chứ không ra danh sách việc. Câu hỏi có tiêu chí rõ ràng thì đọc thẳng bảng
`tasks`, sắp theo hạn, đếm được và không bỏ sót.

Phạm vi người dùng nằm ngoài chữ ký công cụ, giống bộ tool Discord: bảng
`tasks` phân theo `user_id`, để model tự truyền user_id nghĩa là cho nó đọc việc
của người khác chỉ bằng cách đoán một chuỗi.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from json import JSONDecodeError, dumps, loads
from uuid import uuid4

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.services.attribution import provider_label
from src.services.task_retention import purge_expired_completed_tasks

logger = logging.getLogger(__name__)

# Chủ nhân của lượt chạy hiện tại, do tầng gọi đặt chứ không phải LLM sinh ra.
_user_id: ContextVar[str | None] = ContextVar("task_user_id", default=None)

_VALID_STATUS = ("proposed", "confirmed", "dismissed", "completed")

# Trần cứng để một câu hỏi rộng không kéo cả bảng vào ngữ cảnh model.
_MAX_ROWS = 30
_MAX_EVIDENCE_LINKS_PER_TASK = 3
# Trần thẻ gợi ý cho một lượt trả lời. Một hộp thư bận có thể sinh ra hàng chục
# việc; đổ hết xuống chat thì người dùng không đọc nổi và không bấm được cái nào.
_MAX_SUGGESTIONS = 6
# Nhãn cụm cho việc được NHIỀU nguồn cùng xác nhận — đứng đầu danh sách vì
# đó là việc đáng tin nhất, và là thứ người dùng khó tự đối chiếu nhất.
_MULTI_SOURCE_BUCKET = "Nhiều nguồn cùng xác nhận"
# Việc không còn bằng chứng nào (nguồn đã bị gỡ kết nối, hoặc task do người
# dùng tự tạo tay) — nói thẳng thay vì gán bừa vào một nền tảng.
_UNKNOWN_SOURCE_BUCKET = "Chưa rõ nguồn"


def _urgency_label(due_at, now: datetime) -> str:
    """Nhãn gấp/không đặt ngay ĐẦU dòng.

    Hạn chót vẫn được in ra ở phần trong ngoặc, nhưng người đọc (và mô hình
    tóm tắt lại) phải quét cả dòng mới biết việc nào gấp. Nhãn ở đầu dòng cho
    phép nhìn cột trái là thấy ngay thứ tự cần làm.
    """
    if due_at is None:
        return "[chưa có hạn]"
    moment = due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=UTC)
    days = (moment.date() - now.astimezone(moment.tzinfo).date()).days
    if days < 0:
        return "[QUÁ HẠN]"
    if days == 0:
        return "[hôm nay]"
    if days == 1:
        return "[ngày mai]"
    if days <= 7:
        return f"[còn {days} ngày]"
    return "[sau này]"


def _count_tasks(entries: list[str]) -> int:
    """Mỗi việc là 1 dòng bắt đầu bằng "- "; các dòng còn lại là link nguồn."""
    return sum(1 for line in entries if line.startswith("- "))


def _ordered_buckets(grouped: dict[str, list[str]]) -> list[str]:
    """Nhiều-nguồn trước, rồi tới từng nền tảng theo bảng chữ cái, "chưa rõ
    nguồn" xuống cuối. Thứ tự cố định để hai lần hỏi giống nhau không cho ra
    hai bố cục khác nhau."""
    head = [name for name in (_MULTI_SOURCE_BUCKET,) if name in grouped]
    tail = [name for name in (_UNKNOWN_SOURCE_BUCKET,) if name in grouped]
    middle = sorted(name for name in grouped if name not in {*head, *tail})
    return [*head, *middle, *tail]


_CALENDAR_WRITE_SCOPES = {
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
}


def set_task_scope(user_id: str) -> None:
    """Đặt chủ nhân của lượt chạy hiện tại.

    Không có nhánh "không giới hạn" như `set_search_scope`: mỗi dòng trong
    `tasks` thuộc về đúng một người, nên đọc không giới hạn nghĩa là đọc việc
    của tất cả mọi người. Cờ demo_unscoped_search cũng không mở được chỗ này.
    """
    _user_id.set(user_id or None)


def reset_task_scope() -> None:
    """Xoá chủ nhân đã đặt, đưa công cụ về trạng thái từ chối đọc."""
    _user_id.set(None)


def _format_due(due_at: datetime | None, ambiguous: bool) -> str:
    """Mô tả hạn chót theo múi giờ người dùng, nói thẳng khi chưa đủ bằng chứng."""
    if due_at is None:
        # BR-05: thiếu bằng chứng thì để trống chứ không đoán. Hiển thị cũng
        # phải giữ đúng như vậy, đừng lấp bằng "chưa rõ" nghe như đã có hạn.
        return "chưa có hạn chót"

    from src.agents.tools.time_tool import app_timezone

    # PostgreSQL trả về aware datetime theo UTC. SQLite/test fixture có thể trả
    # naive datetime; khi đó hiểu theo múi giờ ứng dụng, không gán UTC rồi làm
    # lệch bảy tiếng trong chính thứ mà công cụ này sinh ra để trả lời.
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=app_timezone())
    deadline = f"{due_at.astimezone(app_timezone()):%d/%m/%Y %H:%M}"
    return f"hạn {deadline}, nguồn ghi chưa rõ ràng" if ambiguous else f"hạn {deadline}"


@tool
def draft_task(
    title: str,
    detail: str = "",
    due_at: str = "",
    all_day: bool = False,
) -> str:
    """Tạo bản nháp task khi người dùng yêu cầu rõ ràng tạo/thêm một việc.

    Công cụ chỉ tạo trạng thái ``proposed``; không tự xác nhận và không ghi
    Google Calendar. Nếu người dùng muốn thêm lịch, vẫn phải mở trang Tasks,
    kiểm tra bản nháp, xác nhận rồi bấm đồng bộ. ``due_at`` phải là ISO có múi
    giờ; cần biết ngày tương đối thì gọi ``current_datetime`` trước.

    Args:
        title: Tên việc ngắn gọn, bỏ các từ điều khiển như "tạo task"
        detail: Ghi chú người dùng cung cấp, không tự bịa thêm
        due_at: Hạn chót ISO có múi giờ; để trống nếu người dùng không nêu rõ
        all_day: True chỉ khi người dùng nói đây là việc cả ngày
    """
    user_id = _user_id.get()
    if not user_id:
        return (
            "Chưa xác định được đây là việc của ai nên chưa tạo bản nháp. Tầng gọi phải đặt phạm vi người dùng trước."
        )

    clean_title = (title or "").strip()
    clean_detail = (detail or "").strip()
    if not clean_title:
        return "Chưa tạo bản nháp: cần tên task."
    if len(clean_title) > 500:
        return "Chưa tạo bản nháp: tên task tối đa 500 ký tự."
    if len(clean_detail) > 10_000:
        return "Chưa tạo bản nháp: ghi chú tối đa 10.000 ký tự."

    parsed_due = None
    if (due_at or "").strip():
        from src.agents.tools.time_tool import parse_timestamp

        parsed = parse_timestamp(due_at)
        if parsed is None:
            return "Chưa tạo bản nháp: không hiểu due_at. Hãy dùng ngày/tháng/năm hoặc ISO có múi giờ."
        parsed_due = parsed.moment

    from src.db import engine
    from src.models.task import Task
    from src.models.task_evidence import TaskEvidence
    from src.models.telemetry import AuditEvent
    from src.services.connections import preferred_connection
    from src.services.task_dedup import acquire_user_lock, candidate_fingerprint, find_duplicate_task
    from src.services.telemetry import emit_audit

    try:
        with Session(engine) as db:
            acquire_user_lock(db, user_id)
            dedup_due = parsed_due.astimezone(UTC) if parsed_due is not None else None
            decision = find_duplicate_task(
                db,
                user_id=user_id,
                title=clean_title,
                detail=clean_detail,
                due_at=dedup_due,
                all_day=bool(all_day),
            )
            merged = decision.task is not None
            if decision.task is not None:
                row = decision.task
                fingerprint = candidate_fingerprint(clean_title, clean_detail, dedup_due)
                prior_merges = db.scalars(
                    select(AuditEvent).where(
                        AuditEvent.action == "task_deduplicated",
                        AuditEvent.object_type == "task",
                        AuditEvent.object_id == str(row.id),
                    )
                ).all()
                already_recorded = any(
                    (event.details or {}).get("incoming_fingerprint") == fingerprint for event in prior_merges
                )
                if not already_recorded:
                    from src.config import get_settings

                    settings = get_settings()
                    row.source_count = int(row.source_count or 0) + 1
                    row.updated_at = datetime.now(UTC)
                    db.add(
                        TaskEvidence(
                            task_id=row.id,
                            provider="user_draft",
                            evidence_quote=clean_detail or clean_title,
                            deep_link="",
                        )
                    )
                    emit_audit(
                        db,
                        "task_deduplicated",
                        "task",
                        str(row.id),
                        actor_type="agent",
                        actor_id=user_id,
                        version_label="task-dedup-v1",
                        layer=decision.layer,
                        similarity_score=round(float(decision.similarity_score or 0.0), 6),
                        incoming_fingerprint=fingerprint,
                        due_proximity_hours=settings.task_dedup_due_proximity_hours,
                        fuzzy_threshold=settings.task_dedup_fuzzy_threshold,
                        semantic_threshold=settings.task_dedup_semantic_threshold,
                        embedding_model=settings.task_dedup_embedding_model,
                    )
            else:
                row = Task(
                    user_id=user_id,
                    cluster_key=f"user-draft-{uuid4().hex}",
                    title=clean_title,
                    detail=clean_detail,
                    due_at=dedup_due,
                    all_day=bool(all_day),
                    ambiguous=False,
                    status="proposed",
                    # Bản nháp là chỉ dẫn trực tiếp của user, không giả là đã được
                    # trích và đối chiếu từ một nguồn bên ngoài.
                    source_count=0,
                    signal_strength=1.0,
                )
                db.add(row)
                db.flush()
                if decision.degraded_reason:
                    emit_audit(
                        db,
                        "task_dedup_degraded",
                        "task",
                        str(row.id),
                        actor_type="agent",
                        actor_id=user_id,
                        reason=decision.degraded_reason,
                    )
            db.commit()
            db.refresh(row)

            google = preferred_connection(db, user_id, "google")
            granted_scopes = set((google.scopes or "").split()) if google else set()
            calendar_write_ready = bool(granted_scopes.intersection(_CALENDAR_WRITE_SCOPES))
    except Exception as exc:
        logger.warning("Tạo task draft hỏng cho user %s: error_type=%s", user_id, type(exc).__name__)
        return "Không tạo được bản nháp task. Vui lòng thử lại."

    next_steps = ["Mở /tasks để kiểm tra và xác nhận bản nháp."]
    if parsed_due is None:
        next_steps.append("Cần bổ sung hạn chót rõ ràng trước khi đồng bộ Calendar.")
    if not calendar_write_ready:
        next_steps.append("Google hiện chưa có quyền ghi Calendar; hãy kết nối lại Google.")
    else:
        next_steps.append("Sau khi xác nhận, bấm Đồng bộ lịch để tạo sự kiện Google Calendar.")

    return dumps(
        {
            "status": "draft_created",
            "task_id": row.id,
            "title": row.title,
            "due_at": row.due_at.isoformat() if row.due_at else None,
            "all_day": row.all_day,
            "task_status": row.status,
            "deduplicated": merged,
            "dedup_layer": decision.layer,
            "similarity_score": (
                round(float(decision.similarity_score), 6) if decision.similarity_score is not None else None
            ),
            "calendar_write_ready": calendar_write_ready,
            "next_steps": next_steps,
        },
        ensure_ascii=False,
    )


@tool
def suggest_tasks(suggestions: list[dict] | str) -> str:
    """Đề xuất các việc nhận ra được từ nguồn, KHÔNG tạo và KHÔNG ghi gì vào DB.

    Dùng khi vừa đọc email, tin nhắn, Jira hay lịch và thấy có việc người dùng
    cần làm, nhưng họ chưa hề yêu cầu tạo task. Kết quả chỉ là gợi ý hiện thành
    thẻ có nút "Thêm task" — chính người dùng bấm thì mới sinh bản nháp. Khác
    ``draft_task`` ở đúng chỗ đó: ``draft_task`` ghi ngay một dòng `proposed`
    nên chỉ được gọi khi người dùng yêu cầu rõ ràng.

    Cơ chế: công cụ không truy vấn gì cả. Nó chỉ kiểm tra và chuẩn hoá danh
    sách model đưa vào — cắt trắng, bỏ mục thiếu tiêu đề, chuẩn hoá ``due_at``
    về ISO có múi giờ, khử trùng tiêu đề, cắt theo trần ``_MAX_SUGGESTIONS`` —
    rồi trả lại JSON để tầng API biến thành thẻ gợi ý. Không có gì bền vững
    được tạo ra, nên gọi lại nhiều lần cũng vô hại.

    Args:
        suggestions: Danh sách mục, mỗi mục gồm `title` (bắt buộc), `detail`,
            `due_at` (ISO có múi giờ, để trống nếu nguồn không nói rõ),
            `assignee` (chỉ khi nguồn nói rõ) và `source` (tên nguồn để người
            dùng đối chiếu, ví dụ "Gmail").
    """
    if not _user_id.get():
        return "Chưa xác định được đây là việc của ai nên chưa đề xuất. Tầng gọi phải đặt phạm vi người dùng trước."

    # Model đôi khi trả chuỗi JSON thay vì list — chấp nhận cả hai thay vì bắt
    # nó gọi lại, vì gọi lại tốn trọn một vòng LLM cho lỗi hình thức.
    if isinstance(suggestions, str):
        try:
            suggestions = loads(suggestions or "[]")
        except JSONDecodeError:
            return "Chưa đề xuất được: suggestions phải là danh sách các mục, mỗi mục có title."
    if not isinstance(suggestions, list):
        return "Chưa đề xuất được: suggestions phải là danh sách các mục, mỗi mục có title."

    from src.agents.tools.time_tool import parse_timestamp

    items: list[dict] = []
    seen_titles: set[str] = set()
    for raw in suggestions:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        # BR-05: thiếu bằng chứng thì bỏ qua, không lấp bằng tiêu đề tự đoán.
        if not title:
            continue
        key = title.casefold()
        if key in seen_titles:
            continue
        seen_titles.add(key)

        due_raw = str(raw.get("due_at") or "").strip()
        parsed_due = parse_timestamp(due_raw) if due_raw else None
        item = {
            "title": title[:500],
            "detail": str(raw.get("detail") or "").strip()[:2000],
            # Hạn không hiểu được thì để trống chứ không giữ chuỗi thô:
            # thẻ gợi ý hiển thị thẳng giá trị này cho người dùng.
            "due_at": parsed_due.moment.isoformat() if parsed_due else None,
            "source": str(raw.get("source") or "").strip()[:64],
        }
        assignee = str(raw.get("assignee") or "").strip()[:255]
        if assignee:
            item["assignee"] = assignee
        items.append(item)
        if len(items) >= _MAX_SUGGESTIONS:
            break

    if not items:
        return dumps({"status": "no_suggestions", "suggestions": []}, ensure_ascii=False)

    return dumps(
        {
            "status": "suggested",
            "suggestions": items,
            "next_steps": [
                "Chưa có gì được tạo. Người dùng bấm 'Thêm task' trên từng thẻ thì mới sinh bản nháp.",
            ],
        },
        ensure_ascii=False,
    )


@tool
def suggest_calendar_events(suggestions: list[dict] | str) -> str:
    """Đề xuất nhiều sự kiện lịch đọc từ ảnh, chưa ghi sang Google Calendar.

    Mỗi mục bắt buộc có start_at/end_at ISO kèm múi giờ. Mốc thiếu hoặc không
    hiểu được bị loại bỏ thay vì tự đoán; người dùng sẽ review trước khi ghi.
    """
    if isinstance(suggestions, str):
        try:
            suggestions = loads(suggestions or "[]")
        except JSONDecodeError:
            return "Chưa đề xuất được: suggestions phải là danh sách sự kiện."
    if not isinstance(suggestions, list):
        return "Chưa đề xuất được: suggestions phải là danh sách sự kiện."

    from src.agents.tools.time_tool import parse_timestamp

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for raw in suggestions:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        start_raw = str(raw.get("start_at") or "").strip()
        end_raw = str(raw.get("end_at") or "").strip()
        start = parse_timestamp(start_raw) if start_raw else None
        end = parse_timestamp(end_raw) if end_raw else None
        if not title or start is None or end is None or end.moment <= start.moment:
            continue
        key = (title.casefold(), start.moment.isoformat())
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "title": title[:500],
                "detail": str(raw.get("detail") or "").strip()[:2000],
                "start_at": start.moment.isoformat(),
                "end_at": end.moment.isoformat(),
                "all_day": bool(raw.get("all_day", False)),
                "source": str(raw.get("source") or "Ảnh").strip()[:64],
            }
        )
        if len(items) >= 50:
            break
    return dumps({"status": "suggested" if items else "no_suggestions", "suggestions": items}, ensure_ascii=False)


@tool
def list_tasks(status: str = "proposed", due_before: str = "", due_after: str = "") -> str:
    """Liệt kê việc cần làm của người dùng, sắp theo hạn chót.

    Dùng cho câu hỏi về việc phải làm: việc tuần này, việc sắp tới hạn, việc đã
    quá hạn, còn bao nhiêu việc chưa xong. Cần biết hôm nay là ngày nào thì gọi
    current_datetime trước rồi tự tính mốc, đừng đoán.

    Args:
        status: proposed (chưa duyệt), confirmed (đã duyệt), dismissed (đã bỏ), completed (đã làm), hoặc "all"
        due_before: Chỉ lấy việc tới hạn trước mốc này, ví dụ "09/08/2026"
        due_after: Chỉ lấy việc tới hạn từ mốc này trở đi, ví dụ "03/08/2026"

    Returns:
        Danh sách việc ĐÃ NHÓM THEO NGUỒN (Gmail / Jira / Google Calendar…),
        việc được nhiều nguồn cùng xác nhận xếp riêng lên đầu. Trong mỗi nhóm,
        việc đã sắp sẵn theo độ gấp — quá hạn trước, rồi tới hôm nay, ngày mai,
        và cuối cùng là việc chưa có hạn.

        Khi trả lời: giữ nguyên cách nhóm và giữ nguyên thứ tự này, đừng gộp
        thành một danh sách phẳng và đừng sắp lại. Nhãn [QUÁ HẠN]/[hôm nay] ở
        đầu mỗi dòng là để nói lại cho người dùng biết việc nào cần làm trước.
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được đây là việc của ai nên chưa đọc. Tầng gọi phải đặt phạm vi người dùng trước."

    from src.agents.tools.time_tool import parse_timestamp
    from src.db import engine
    from src.models.task import Task
    from src.models.task_evidence import TaskEvidence
    from src.services.task_ownership import personal_task_ids

    if status and status != "all" and status not in _VALID_STATUS:
        return f"Trạng thái {status!r} không có thật. Chỉ có: {', '.join(_VALID_STATUS)}, hoặc 'all'."

    # Mốc không hiểu được thì dừng, không lặng lẽ bỏ bộ lọc — bỏ đi là trả về cả
    # danh sách rồi để model tưởng đó là việc của đúng tuần nó hỏi.
    bounds: dict[str, datetime] = {}
    for name, value in (("due_before", due_before), ("due_after", due_after)):
        if not (value or "").strip():
            continue
        parsed = parse_timestamp(value)
        if parsed is None:
            return (
                f"Không hiểu được mốc thời gian {value!r} ở tham số {name}, "
                "nên chưa đọc. Cần dạng ngày/tháng/năm hoặc chuỗi ISO."
            )
        bounds[name] = parsed.moment

    if "due_after" in bounds and "due_before" in bounds and bounds["due_after"] > bounds["due_before"]:
        return "Khoảng thời gian ngược: due_after muộn hơn due_before, nên chưa đọc."

    date_column = Task.completed_at if status == "completed" else Task.due_at
    stmt = select(Task).where(Task.user_id == user_id)
    if status and status != "all":
        stmt = stmt.where(Task.status == status)
    if "due_after" in bounds:
        stmt = stmt.where(date_column >= bounds["due_after"])
    if "due_before" in bounds:
        stmt = stmt.where(date_column <= bounds["due_before"])

    # Hạn gần lên trước; cùng hạn thì việc được nhiều nguồn nhắc tới lên trước.
    # NULL (chưa có hạn) phải xuống CUỐI: Postgres mặc định xếp NULL sau cùng
    # với ASC, nhưng SQLite lại đưa lên đầu — không nói rõ thì hai môi trường
    # cho ra hai thứ tự khác nhau, và việc chưa có hạn sẽ che mất việc gấp.
    stmt = stmt.order_by(date_column.is_(None), date_column.asc(), Task.signal_strength.desc())

    try:
        with Session(engine) as db:
            purge_expired_completed_tasks(db, user_id)
            candidate_rows = db.execute(stmt).scalars().all()
            visible_ids = personal_task_ids(db, user_id, candidate_rows)
            rows = [row for row in candidate_rows if row.id in visible_ids]
            visible_task_ids = [row.id for row in rows[:_MAX_ROWS]]
            evidence_rows = (
                db.execute(select(TaskEvidence).where(TaskEvidence.task_id.in_(visible_task_ids))).scalars().all()
                if visible_task_ids
                else []
            )
            # Việc chưa có hạn bị mọi bộ lọc thời gian loại ra, nhưng nó vẫn là
            # việc của người này. Đếm riêng rồi nói ra, nếu không người dùng
            # tưởng đã thấy hết còn thực tế thiếu mất phần chưa có hạn.
            undated = 0
            if bounds:
                undated_stmt = select(Task).where(Task.user_id == user_id, Task.due_at.is_(None))
                if status and status != "all":
                    undated_stmt = undated_stmt.where(Task.status == status)
                undated_rows = db.execute(undated_stmt).scalars().all()
                personal_undated = personal_task_ids(db, user_id, undated_rows)
                undated = sum(1 for row in undated_rows if row.id in personal_undated)
    except Exception as exc:
        logger.warning("Đọc tasks hỏng cho user %s: %s", user_id, exc)
        return f"Không đọc được danh sách việc: {exc}"

    truncated = len(rows) > _MAX_ROWS
    rows = rows[:_MAX_ROWS]

    evidence_by_task: dict[int, list] = {}
    for evidence in evidence_rows:
        evidence_by_task.setdefault(evidence.task_id, []).append(evidence)

    if not rows:
        base = (
            "Không có việc nào khớp trong khoảng thời gian đó."
            if bounds
            else "Chưa có việc nào được ghi nhận từ các nguồn đã kết nối."
        )
        if undated:
            base += f" Ngoài ra còn {undated} việc chưa có hạn chót."
        return base

    # Nhóm theo NGUỒN, không trả danh sách phẳng. Danh sách phẳng có ghi "nguồn
    # Gmail" ở cuối mỗi dòng, nhưng mô hình đọc xong vẫn kể ra một mạch nên
    # người dùng không thấy được việc nào đến từ đâu — và việc được nhiều nguồn
    # cùng xác nhận (đáng tin nhất) thì chìm lẫn vào giữa.
    now = datetime.now(UTC)
    grouped: dict[str, list[str]] = {}
    for row in rows:
        evidence = evidence_by_task.get(row.id, [])
        providers = sorted({provider_label(item.provider) for item in evidence})
        if len(providers) > 1:
            bucket = _MULTI_SOURCE_BUCKET
        elif providers:
            bucket = providers[0]
        else:
            bucket = _UNKNOWN_SOURCE_BUCKET

        if row.status == "completed":
            parts = [f"hoàn tất {_format_due(row.completed_at, False).removeprefix('hạn ')}", "trạng thái completed"]
        else:
            parts = [_format_due(row.due_at, row.ambiguous), f"trạng thái {row.status}"]
        if len(providers) > 1:
            parts.append(f"xác nhận bởi {', '.join(providers)}")
        if row.source_count > 1:
            parts.append(f"{row.source_count} nguồn nhắc tới")

        entry = [f"- {_urgency_label(row.due_at, now)} {row.title} ({' · '.join(parts)})"]
        links = list(dict.fromkeys(item.deep_link for item in evidence if item.deep_link))
        entry.extend(f"  nguồn: {link}" for link in links[:_MAX_EVIDENCE_LINKS_PER_TASK])
        grouped.setdefault(bucket, []).extend(entry)

    lines = []
    for bucket in _ordered_buckets(grouped):
        lines.append(f"{bucket} ({_count_tasks(grouped[bucket])} việc):")
        lines.extend(grouped[bucket])
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()

    footer = []
    if truncated:
        footer.append(f"Còn nữa, đây mới là {_MAX_ROWS} việc gần hạn nhất.")
    if undated:
        footer.append(f"Ngoài khoảng này còn {undated} việc chưa có hạn chót.")

    return "\n".join(lines) + ("\n\n" + " ".join(footer) if footer else "")
