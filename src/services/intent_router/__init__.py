"""Định tuyến ý định bằng luật, không gọi LLM.

Package này là nguồn duy nhất cho mọi quyết định điều hướng dạng luật của phần
chat. Trước đây có hai bộ luật song song: `route_gmail_intent`/`route_calendar_intent`
ở đây, và tám hàm `_prefer_*`/`_ensure_*` nằm trong `agents/nodes/core_nodes.py`.
Hai bộ đó quyết định cùng một việc nhưng lệch nhau ở chỗ quan trọng: bộ ở đây bỏ
dấu trước khi khớp, bộ trong node thì không, nên "tao lich ngay mai" gõ không dấu
trượt hết luật lịch. Gộp về đây để chỉ còn một chỗ phải sửa.

Router chọn kế hoạch truy hồi/hành động; nó không bao giờ tự thực thi tool.

Tách thành package (2026-08-15, vượt quy ước 800 dòng/file) — VẪN chỉ 1 nguồn sự
thật cho mỗi rule, chỉ tổ chức lại theo file vật lý:
- `types.py` — enum/dataclass dùng chung.
- `_shared.py` — helper text-normalization dùng chung (`_fold`).
- `gmail.py` — `route_gmail_intent`, không phụ thuộc `calendar.py`.
- `calendar.py` — `route_calendar_intent`, không phụ thuộc `gmail.py`.
- `tool_planning.py` — 8 hàm `_prefer_*`/`_ensure_*` + `plan_tool_calls`, hoàn
  toàn độc lập với `gmail.py`/`calendar.py` (đã verify không import chéo).

Import bên ngoài package KHÔNG đổi — mọi tên public vẫn `from
src.services.intent_router import X` như trước khi tách.
"""

from src.services.intent_router.calendar import route_calendar_intent
from src.services.intent_router.gmail import route_gmail_intent
from src.services.intent_router.tool_planning import (
    ToolPlanContext,
    agenda_window,
    calendar_window,
    can_answer_from_memory,
    gmail_window,
    is_agenda_query,
    is_productivity_create,
    plan_tool_calls,
)
from src.services.intent_router.types import (
    CalendarIntent,
    CalendarIntentPlan,
    GmailIntent,
    GmailIntentPlan,
    ToolRisk,
)

__all__ = [
    "CalendarIntent",
    "CalendarIntentPlan",
    "GmailIntent",
    "GmailIntentPlan",
    "ToolPlanContext",
    "ToolRisk",
    "agenda_window",
    "calendar_window",
    "can_answer_from_memory",
    "gmail_window",
    "is_agenda_query",
    "is_productivity_create",
    "plan_tool_calls",
    "route_calendar_intent",
    "route_gmail_intent",
]
