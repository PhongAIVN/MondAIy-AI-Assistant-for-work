"""Ghi sự kiện đo lường và nhật ký thay đổi, chặn nội dung gốc bằng cấu trúc.

PRD §13 cấm ghi nội dung email, tin nhắn, item, câu hỏi hay câu trả lời vào dữ
liệu đo lường. Chỗ này thi hành bằng **danh sách cho phép theo từng sự kiện**:
thuộc tính nào không có tên trong bảng thì bị loại và đếm vào `_da_chan`. Cách
làm ngược lại — chặn theo danh sách cấm — sẽ rò ngay khi ai đó thêm trường mới.

`trace_id` giữ trong contextvar nên nó tự đi theo cả chuỗi xử lý mà không phải
truyền tay qua từng hàm. Architecture §9 đòi trace chạy suốt từ đồng bộ nguồn tới
câu trả lời.

Bề mặt nào cũng dùng chung hàm này — web, telegram, discord, cli — nên số liệu
so sánh được giữa các bề mặt thay vì mỗi nơi một kiểu.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.models.telemetry import AuditEvent, TelemetryEvent

log = logging.getLogger("mondaiy.telemetry")

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_surface: ContextVar[str] = ContextVar("surface", default="web")
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)

# Thuộc tính được phép wait từng sự kiện, chép đúng từ PRD §13. Thêm sự kiện mới
# phải sửa PRD trước rồi mới sửa bảng này, không làm ngược lại.
ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "capture_enqueued": frozenset({"source_type", "mode", "size_bucket"}),
    "capture_synced": frozenset({"latency", "duplicate", "version_created"}),
    "capture_failed": frozenset({"source_type", "error_class", "retry_count"}),
    "memory_candidate_created": frozenset({"kind", "confidence_bucket", "source_type"}),
    "memory_status_changed": frozenset({"from", "to", "actor_type"}),
    "brief_generated": frozenset({"coverage", "item_count", "source_count"}),
    "brief_opened": frozenset({"time_since_generated"}),
    "ask_submitted": frozenset({"intent", "scope"}),
    "answer_rendered": frozenset(
        {"latency", "citation_count", "abstained", "conflict", "model", "cost_usd", "token_in", "token_out"}
    ),
    "answer_feedback": frozenset({"verdict"}),
    "action_draft_created": frozenset({"origin", "type", "missing_fields"}),
    "action_confirmed": frozenset({"type", "edit_count", "time_to_confirm"}),
    "calendar_handoff_opened": frozenset({"provider", "handoff_type"}),
    "consent_changed": frozenset({"source_type", "state"}),
    # Sự kiện ngoài PRD §13, thêm cho bước truy hồi. Chưa có trong tài liệu nên
    # đánh dấu để nêu trong PR — TODO(OD-TEL1).
    "retrieval_ran": frozenset({"latency", "fts_hits", "vector_hits", "merged_hits", "returned", "filtered_by"}),
    "embedding_called": frozenset({"latency", "model", "batch_size", "dims", "error_class"}),
}


def start_trace(surface: str = "web", user_id: str | None = None) -> str:
    """Mở một trace mới cho một yêu cầu và gắn bề mặt phát sinh."""
    tid = str(uuid.uuid4())
    _trace_id.set(tid)
    _surface.set(surface)
    _user_id.set(user_id)
    return tid


def current_trace() -> str:
    return _trace_id.get()


def _filter_attrs(name: str, attributes: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Giữ lại thuộc tính có trong danh sách cho phép, trả về phần bị chặn."""
    allowed = ALLOWED_ATTRS.get(name)
    if allowed is None:
        return {}, sorted(attributes)
    kept = {k: v for k, v in attributes.items() if k in allowed}
    blocked = sorted(k for k in attributes if k not in allowed)
    return kept, blocked


def emit(
    db: Session | None,
    name: str,
    duration_ms: int | None = None,
    **attributes: Any,
) -> TelemetryEvent | None:
    """Ghi một sự kiện đo lường; thuộc tính ngoài danh sách bị loại chứ không lưu."""
    kept, blocked = _filter_attrs(name, attributes)
    if name not in ALLOWED_ATTRS:
        log.warning("sự kiện lạ %r, không ghi. Khai vào PRD §13 trước.", name)
        return None
    if blocked:
        # Không in giá trị bị chặn ra log — chính nó mới là thứ có thể chứa nội dung.
        log.warning("sự kiện %s: loại %d thuộc tính ngoài danh sách %s", name, len(blocked), blocked)

    ev = TelemetryEvent(
        name=name,
        trace_id=_trace_id.get(),
        surface=_surface.get(),
        user_id=_user_id.get(),
        attributes=kept or None,
        duration_ms=duration_ms,
    )
    log.info("%s trace=%s surface=%s %s", name, ev.trace_id[:8], ev.surface, kept)
    if db is not None:
        db.add(ev)
    return ev


def emit_audit(
    db: Session,
    action: str,
    object_type: str,
    object_id: str,
    actor_type: str = "system",
    actor_id: str | None = None,
    version_label: str | None = None,
    **details: Any,
) -> AuditEvent:
    """Ghi một thao tác đã đổi trạng thái, theo FR-070."""
    ev = AuditEvent(
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        actor_type=actor_type,
        actor_id=actor_id,
        trace_id=_trace_id.get(),
        version_label=version_label,
        details=details or None,
    )
    db.add(ev)
    return ev


@contextmanager
def timed(db: Session | None, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Đo thời gian một đoạn rồi ghi sự kiện, kể cả khi đoạn đó ném lỗi.

    Trả về một dict để đoạn code bên trong nhét thêm thuộc tính vào trước khi ghi.
    """
    extra: dict[str, Any] = {}
    t0 = time.perf_counter()
    try:
        yield extra
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        emit(db, name, duration_ms=ms, latency=ms, **{**attributes, **extra})


def create_tables(engine: Engine) -> None:
    """Tạo hai bảng telemetry nếu chưa có, để script chạy độc lập được."""
    TelemetryEvent.__table__.create(engine, checkfirst=True)
    AuditEvent.__table__.create(engine, checkfirst=True)
