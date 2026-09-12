"""Lane xác định cho câu hỏi lập kế hoạch từ task đã lưu của chính user."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from src.services.task_breakdown import (
    TaskBreakdownError,
    TaskBreakdownUnavailableError,
    build_task_breakdown_from_db,
)

_PLANNING_REQUEST = re.compile(
    r"(?is)(?:hôm\s*nay|tuần\s*này|today|this\s*week).{0,180}"
    r"(?:làm\s*gì|cần\s*làm|ưu\s*tiên|priority|kế\s*hoạch|plan|retro)"
    r"|(?:làm\s*gì|cần\s*làm|ưu\s*tiên|priority|kế\s*hoạch|plan|retro).{0,180}"
    r"(?:hôm\s*nay|tuần\s*này|today|this\s*week)"
)


def is_task_planning_request(message: str) -> bool:
    """Chỉ bắt câu hỏi có cả mốc thời gian và ý định ưu tiên/lập kế hoạch."""
    return bool(_PLANNING_REQUEST.search(" ".join(message.casefold().split())))


def _due_label(value: datetime | None) -> str:
    return f" · hạn {value.strftime('%d/%m %H:%M')}" if value else " · chưa có hạn"


def _fallback_response() -> str:
    return (
        "Hiện chưa có task còn mở nào để xếp ưu tiên. Hãy thêm hoặc xác nhận một việc, "
        "rồi mình sẽ chia nó thành bước đầu tiên có thể làm ngay."
    )


def format_task_plan(plan: dict) -> str:
    """Render contract có cấu trúc thành câu trả lời chat, không bịa file/link."""
    items = plan["items"]
    if not items:
        return _fallback_response()

    lines = [plan.get("summary") or "Đây là thứ tự nên làm dựa trên các task còn mở của bạn."]
    for rank, item in enumerate(items, start=1):
        lines.append(f"\n{rank}. {item['title']}{_due_label(item.get('due_at'))}")
        if item.get("reason"):
            lines.append(f"   Vì sao: {item['reason']}")
        steps = item.get("steps") or []
        if steps:
            lines.append(f"   Bước bắt đầu (≤15 phút): {steps[0]}")
            for index, step in enumerate(steps[1:], start=2):
                lines.append(f"   Bước {index}: {step}")
        else:
            lines.append("   Bước bắt đầu (≤15 phút): mở task, chốt đầu ra nhỏ nhất và làm ngay một phần đầu tiên.")
        context = item.get("context_needed") or []
        if context:
            lines.append("   Tài liệu/context: " + "; ".join(context))
        else:
            lines.append("   Tài liệu/context: chưa có file hoặc link được lưu kèm task này.")
        if item.get("ai_prompt"):
            lines.append("   Prompt copy-paste: " + item["ai_prompt"])
    return "\n".join(lines)


async def build_task_planning_reply(db: Session, user_id: str) -> dict:
    """Tạo terminal reply cho lane planning, không đi qua tool-loop tổng quát."""
    try:
        plan = await build_task_breakdown_from_db(db, user_id)
    except (TaskBreakdownUnavailableError, TaskBreakdownError):
        # Không đưa lỗi hạ tầng vào chat như thể lỗi của user; vẫn chỉ rõ bước tiếp.
        return {
            "response": "Mình chưa thể tách nhỏ task tự động lúc này. Bạn vẫn có thể mở trang Công việc, chọn task quan trọng nhất và thêm mô tả/hạn; sau đó thử lại.",
            "analysis": "task_planning_unavailable",
        }
    return {"response": format_task_plan(plan), "analysis": "task_planning_grounded"}
