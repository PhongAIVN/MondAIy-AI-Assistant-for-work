"""Công cụ `plan_my_day` — nối dây planner xác định vào agent hội thoại.

ADR-018 QĐ-3: đây là MỘT trong hai tool đăng ký thẳng vào registry, không có
lane riêng. Xếp hạng và ước lượng đã có sẵn ở `src/services/planner/score.py`
và `estimate.py` (không LLM, không I/O, thuần hàm) — tool này CHỈ truy vấn DB,
gọi hai hàm đó, và định dạng chuỗi trả lời. Không tự viết lại thuật toán xếp
hạng ở đây, dù chỉ để "tiện".

Phạm vi người dùng theo đúng khuôn `calendar_tool.py`: ContextVar do tầng gọi
(`src/services/scope.py`) đặt, không nằm trong schema mà model điền được.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_user_id: ContextVar[str | None] = ContextVar("plan_my_day_user_id", default=None)

# OD-01: kế hoạch hiện đúng 3 việc, phần còn lại giữ nguyên thứ hạng cho lượt
# sau kéo tiếp — KHÔNG cắt ở tầng planner (rank_tasks trả về đầy đủ), chỉ cắt
# hiển thị ở đây.
_VISIBLE_COUNT = 3

# Trần phòng thủ cho tập tiền lệ dùng ước lượng reference-class. estimate.py tự
# lọc lấy mẫu tương tự trong tập này; con số này chỉ chặn một truy vấn không
# giới hạn khi user đã tích luỹ rất nhiều task hoàn tất qua nhiều năm.
_MAX_HISTORY_ROWS = 500

# Nhãn tiếng Việt cho từng thành phần điểm — PlannerScore.components (score.py)
# là nguồn duy nhất của các khoá này; đổi tên ở đó thì bảng này phải đổi theo.
_COMPONENT_LABELS = {
    "urgency": "khẩn (hạn chót)",
    "importance_signal": "tín hiệu quan trọng",
    "project_link_bonus": "gắn với dự án",
    "stated_priority_bonus": "mức ưu tiên nguồn ghi",
    "dismiss_penalty": "đã bị bỏ qua nhiều lần",
}


def set_plan_scope(user_id: str) -> None:
    _user_id.set(user_id or None)


def reset_plan_scope() -> None:
    _user_id.set(None)


@dataclass(frozen=True)
class _ScorableTaskView:
    """Chiếu một `Task` sang đúng contract `ScorableTask` (score.py).

    Cần lớp riêng vì `due_at` đọc từ SQLite (test) về là naive, còn Postgres
    (production) trả aware UTC — chuẩn hoá về múi giờ ứng dụng một lần ở đây,
    KHÔNG sửa lên object `Task` gốc (tránh việc lỡ tay commit lại DB một giá
    trị due_at đã bị đổi múi giờ)."""

    id: int
    title: str
    due_at: datetime | None
    signal_strength: float
    source_count: int
    reminder_dismiss_count: int
    stated_priority: str | None


def _to_scorable_view(task) -> _ScorableTaskView:
    from src.agents.tools.time_tool import app_timezone

    due_at = task.due_at
    if due_at is not None and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=app_timezone())
    return _ScorableTaskView(
        id=task.id,
        title=task.title,
        due_at=due_at,
        signal_strength=task.signal_strength,
        source_count=task.source_count,
        reminder_dismiss_count=task.reminder_dismiss_count,
        stated_priority=task.stated_priority,
    )


def _format_due(due_at: datetime | None) -> str:
    if due_at is None:
        return "chưa có hạn"
    from src.agents.tools.time_tool import app_timezone

    return f"hạn {due_at.astimezone(app_timezone()):%d/%m/%Y %H:%M}"


def _format_estimate(estimate: tuple[int, int] | None) -> str:
    if estimate is None:
        return "chưa ước lượng được"
    low, high = estimate
    if low == high:
        return f"~{low} phút"
    return f"{low}–{high} phút"


def _format_reasons(components: dict[str, float]) -> str:
    """Chỉ nêu thành phần khác 0 — thành phần bằng 0 không giải thích được gì
    (ví dụ chưa có hạn thì urgency=0, nói ra chỉ gây nhiễu)."""
    nonzero = [(name, value) for name, value in components.items() if value != 0]
    if not nonzero:
        return "không có tín hiệu nào nổi bật"
    nonzero.sort(key=lambda pair: abs(pair[1]), reverse=True)
    parts = []
    for name, value in nonzero:
        label = _COMPONENT_LABELS.get(name, name)
        sign = "+" if value >= 0 else ""
        parts.append(f"{label} ({sign}{value:g})")
    return ", ".join(parts)


@tool
def plan_my_day() -> str:
    """Xếp hạng việc cần làm hôm nay và trả về 3 việc nên làm trước.

    Dùng khi người dùng hỏi kiểu "hôm nay nên làm gì trước", "việc nào ưu tiên",
    "giúp tôi lên kế hoạch trong ngày". Đây là công cụ CHỈ ĐỌC: nó không tạo,
    sửa, xoá hay xác nhận task nào, chỉ đọc các task đang mở (proposed/confirmed)
    của người dùng và xếp hạng bằng thuật toán WSJF xác định
    (`src/services/planner/score.py`) — không dùng LLM để xếp hạng.

    Kết quả luôn hiện đúng 3 việc đầu; phần còn lại không mất đi, chỉ chưa hiện
    — làm xong một trong 3 việc thì gọi lại công cụ này, việc kế tiếp sẽ vào chỗ
    trống (mô hình kéo, không phải hạn ngạch trong ngày).

    Returns:
        3 việc ưu tiên nhất kèm lý do (thành phần điểm), hạn chót nếu có, ước
        lượng thời lượng nếu ước lượng được (nói rõ "chưa ước lượng được" thay
        vì bịa số), và số việc còn lại chưa hiện.
    """
    user_id = _user_id.get()
    if not user_id:
        return "Chưa xác định được đây là việc của ai nên chưa lên kế hoạch. Tầng gọi phải đặt phạm vi người dùng trước."

    from src.agents.tools.time_tool import now as current_now
    from src.db import engine
    from src.models.task import Task
    from src.services.planner.estimate import estimate_minutes
    from src.services.planner.score import rank_tasks
    from src.services.task_ownership import personal_task_ids

    try:
        with Session(engine) as db:
            open_stmt = select(Task).where(
                Task.user_id == user_id,
                Task.status.in_(("proposed", "confirmed")),
            )
            candidate_rows = db.execute(open_stmt).scalars().all()
            visible_ids = personal_task_ids(db, user_id, candidate_rows)
            open_tasks = [row for row in candidate_rows if row.id in visible_ids]

            history_stmt = (
                select(Task)
                .where(
                    Task.user_id == user_id,
                    Task.status == "completed",
                    Task.actual_minutes.is_not(None),
                )
                .limit(_MAX_HISTORY_ROWS)
            )
            history = list(db.execute(history_stmt).scalars().all())
    except Exception as exc:  # DB lỗi phải thành câu trả lời có kiểm soát.
        logger.warning("Đọc dữ liệu plan_my_day hỏng cho user %s: %s", user_id, exc)
        return f"Không lên kế hoạch được: {exc}"

    if not open_tasks:
        return "Hiện không có việc nào đang mở. Bạn đang trống lịch — cứ thong thả."

    moment = current_now()
    estimates = [estimate_minutes(task, history) for task in open_tasks]
    estimate_by_id = {task.id: estimate for task, estimate in zip(open_tasks, estimates)}
    views = [_to_scorable_view(task) for task in open_tasks]
    ranked = rank_tasks(views, moment, estimates)

    top = ranked[:_VISIBLE_COUNT]
    remaining = len(ranked) - len(top)

    lines = [f"{len(ranked)} việc đang mở. {_VISIBLE_COUNT} việc nên làm trước:"]
    for index, (view, score) in enumerate(top, start=1):
        estimate = estimate_by_id[view.id]
        lines.append(
            f"{index}. {view.title} — {_format_due(view.due_at)} · "
            f"ước lượng: {_format_estimate(estimate)}\n"
            f"   vì: {_format_reasons(score.components)} (wsjf={score.wsjf:.2f})"
        )

    if remaining > 0:
        lines.append(
            f"Còn {remaining} việc nữa chưa hiện — làm xong một trong 3 việc trên rồi "
            "gọi lại để việc kế tiếp vào chỗ trống."
        )
    else:
        lines.append("Không còn việc nào khác đang chờ.")

    return "\n".join(lines)
