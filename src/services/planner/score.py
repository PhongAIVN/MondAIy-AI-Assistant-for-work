"""Điểm ưu tiên xác định — ADR-018 QĐ-2 (Eisenhower ở mặt người dùng, WSJF bên
trong) và OD-02 (quan trọng tự động, học dần theo hành vi).

Không gọi LLM, không I/O, không đọc đồng hồ hệ thống — `now` luôn là tham số
truyền vào từ tầng gọi, để cùng input luôn cho cùng output (test được bằng
golden dataset, chạy 100 lần không đổi).

WSJF = chi phí trì hoãn (cost of delay) / khối lượng (job size). Chi phí trì
hoãn được TÁCH thành các thành phần cộng dồn (`PlannerScore.components`) —
tổng đúng bằng `PlannerScore.total`, đây là phần "giải thích được" ADR-018 đòi
hỏi: xem một task đứng trước task khác vì thành phần nào, không phải cảm tính.
`wsjf = total / job_size_min` là khoá dùng để `rank_tasks` sắp xếp — chia cho
khối lượng nên hai task cùng chi phí trì hoãn nhưng một task nhẹ hơn sẽ đứng
trước (làm việc nhẹ trước, đúng tinh thần WSJF: tối đa hoá giá trị/đơn vị thời
gian).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class ScorableTask(Protocol):
    id: int | None
    due_at: datetime | None
    signal_strength: float
    source_count: int
    reminder_dismiss_count: int
    stated_priority: str | None
    # `project_id` KHÔNG có trên model Task hôm nay (đã tra src/models/task.py
    # — chỉ Project, MeetingNote, Conversation có project_id). ADR-018 QĐ-2 kỳ
    # vọng "liên kết project" làm một tín hiệu quan trọng; đọc phòng thủ bằng
    # getattr bên dưới, KHÔNG khai báo bắt buộc ở Protocol này, để score_task
    # vẫn chạy được với Task thật hôm nay và tự nhặt tín hiệu này khi model
    # sau này có cột đó.


@dataclass(frozen=True)
class PlannerScore:
    """Điểm ưu tiên của một task, giải thích được theo thành phần.

    `total` (chi phí trì hoãn) LUÔN bằng `sum(components.values())` — bất biến
    này được test giữ (xem test_score.py). `wsjf = total / job_size_min` là
    điểm cuối dùng để xếp hạng.
    """

    task_id: int | None
    components: dict[str, float]
    total: float
    job_size_min: float
    wsjf: float


# --- Khẩn (urgency), từ due_at — QĐ-2: "khẩn từ due_at" ---------------------

# Bucket cố định thay vì công thức liên tục: đảm bảo THỨ TỰ quá hạn > hôm nay >
# sắp tới > tương lai > không hạn LUÔN đúng bất kể độ lớn chênh lệch thời gian
# thật (một task quá hạn 1 phút vẫn phải đứng trước một task còn nguyên ngày
# hôm nay). Trong bucket OVERDUE có thêm một số hạng nhỏ theo số ngày trễ để
# hai task cùng quá hạn vẫn phân biệt được — chặn trần để không bao giờ vượt
# quá bucket kế tiếp nếu tính sai (ở đây không cần vì OVERDUE_BASE đã cách xa
# DUE_TODAY, nhưng chặn trần vẫn giữ cho rõ ý định).
_OVERDUE_BASE = 100.0
_OVERDUE_PER_DAY = 1.0
_OVERDUE_DAY_CAP = 20.0
_DUE_TODAY = 70.0
_DUE_SOON = 40.0
_DUE_SOON_WINDOW = timedelta(days=3)
_FUTURE = 15.0
_NO_DEADLINE = 0.0


def _urgency(due_at: datetime | None, now: datetime) -> float:
    if due_at is None:
        return _NO_DEADLINE
    if due_at < now:
        overdue_days = (now - due_at).total_seconds() / 86400
        bonus = min(overdue_days * _OVERDUE_PER_DAY, _OVERDUE_DAY_CAP)
        return _OVERDUE_BASE + bonus
    if due_at.date() == now.date():
        return _DUE_TODAY
    if due_at <= now + _DUE_SOON_WINDOW:
        return _DUE_SOON
    return _FUTURE


# --- Quan trọng (importance), từ signal_strength + source_count + project ---
# link — QĐ-2: "quan trọng từ signal_strength, source_count, liên kết
# project". due_at CỐ Ý không cộng lại ở đây dù OD-02 liệt kê due_at vào danh
# sách nguồn "quan trọng": due_at đã có mặt trong `_urgency` ở trên, và
# `total` là TỔNG các thành phần — cộng due_at hai lần sẽ đếm trùng chi phí
# trì hoãn trong cùng một tổng cộng dồn. OD-02 mô tả "quan trọng" như một khái
# niệm hiển thị (Eisenhower, mặt người dùng); ở tầng WSJF nội bộ này, ADR-018
# QĐ-2 đã tách sẵn khẩn/quan trọng thành hai trục — giữ đúng tách đó thay vì
# gộp lại theo OD-02 để tránh double-count. Quyết định này nêu rõ để review.

_SIGNAL_STRENGTH_WEIGHT = 20.0  # signal_strength thường trong khoảng 0..1
_SOURCE_COUNT_WEIGHT = 5.0
_SOURCE_COUNT_CAP = 4  # từ nguồn thứ 5 trở đi không cộng thêm, tránh spam nguồn thổi điểm vô hạn
_PROJECT_LINK_BONUS = 15.0


def _importance_signal(signal_strength: float, source_count: int) -> float:
    bounded_sources = min(max(source_count, 0), _SOURCE_COUNT_CAP)
    return signal_strength * _SIGNAL_STRENGTH_WEIGHT + bounded_sources * _SOURCE_COUNT_WEIGHT


def _project_link_bonus(task: ScorableTask) -> float:
    project_id = getattr(task, "project_id", None)
    return _PROJECT_LINK_BONUS if project_id is not None else 0.0


# --- stated_priority — MỘT TÍN HIỆU ĐẦU VÀO, không phải phán quyết ----------
# (ADR-018 QĐ-3 / ADR-019 QĐ-3). Biên độ CỐ Ý nhỏ so với urgency (100) và
# importance_signal (tối đa ~40): nguồn ngoài nói "gấp" không được tự động
# nhảy lên đầu danh sách, chỉ nghiêng nhẹ khi các tín hiệu khác đã gần cân
# bằng. Hôm nay cột này luôn None trên production (0/257) — nhánh None PHẢI
# chạy được, trả 0, không phải lỗi.
_STATED_PRIORITY_BONUS = {
    "urgent": 5.0,
    "high": 5.0,
    "p1": 5.0,
    "medium": 0.0,
    "p2": 0.0,
    "normal": 0.0,
    "low": -5.0,
    "p3": -5.0,
}


def _stated_priority_bonus(stated_priority: str | None) -> float:
    if stated_priority is None:
        return 0.0
    # Giá trị lạ không nằm trong bảng -> 0, không đoán mức ưu tiên từ chuỗi
    # không nhận diện được (ví dụ nguồn Jira đặt "P4" mà bảng chưa có).
    return _STATED_PRIORITY_BONUS.get(stated_priority.strip().lower(), 0.0)


# --- reminder_dismiss_count cao -> GIẢM ưu tiên (ADR-007) -------------------

_DISMISS_WEIGHT = 5.0
_DISMISS_CAP = 30.0  # chặn trần: né việc nhiều không được kéo điểm xuống âm vô hạn


def _dismiss_penalty(reminder_dismiss_count: int) -> float:
    return -min(max(reminder_dismiss_count, 0) * _DISMISS_WEIGHT, _DISMISS_CAP)


# --- Khối lượng (job size), từ estimate -------------------------------------

# Không có ước lượng (None) vẫn phải xếp hạng được (yêu cầu bắt buộc). Chọn
# một khối lượng TRUNG TÍNH thay vì 0 hoặc vô cùng:
#   - 0 phút -> chia cho 0 (nổ), hoặc nếu chặn sàn ở gần 0 thì WSJF phóng to
#     bất thường, việc chưa ước lượng luôn nhảy lên đầu bất kể chi phí trì
#     hoãn thật — sai, vì "chưa ước lượng" không có nghĩa là "chắc chắn nhanh".
#   - Vô cùng -> WSJF tiến về 0, việc chưa ước lượng luôn rớt xuống đáy — cũng
#     sai vì "chưa ước lượng" không có nghĩa là "chắc chắn tốn thời gian".
# 30 phút là điểm giữa hợp lý cho một "việc" cỡ trung bình trong ngữ cảnh
# planner cá nhân (không phải sprint), tương đương ranh giới deep/shallow của
# OD-03 (45 phút) trừ hao. Đây là quyết định nêu rõ để review, không phải số
# suy ra từ dữ liệu.
NEUTRAL_JOB_SIZE_MIN = 30.0
_MIN_JOB_SIZE_MIN = 1.0  # sàn chặn chia cho 0 khi estimate hợp lệ nhưng bằng 0


def _job_size_min(estimate: tuple[int, int] | None) -> float:
    if estimate is None:
        return NEUTRAL_JOB_SIZE_MIN
    low, high = estimate
    midpoint = (low + high) / 2
    return max(midpoint, _MIN_JOB_SIZE_MIN)


def score_task(
    task: ScorableTask,
    now: datetime,
    estimate: tuple[int, int] | None,
) -> PlannerScore:
    """Tính điểm ưu tiên xác định cho một task. `estimate` do tầng gọi tính
    sẵn qua `estimate.estimate_minutes` (hoặc None nếu không ước lượng được —
    hợp lệ, xem module estimate.py)."""
    components = {
        "urgency": _urgency(task.due_at, now),
        "importance_signal": _importance_signal(task.signal_strength, task.source_count),
        "project_link_bonus": _project_link_bonus(task),
        "stated_priority_bonus": _stated_priority_bonus(task.stated_priority),
        "dismiss_penalty": _dismiss_penalty(task.reminder_dismiss_count),
    }
    total = sum(components.values())
    job_size_min = _job_size_min(estimate)
    return PlannerScore(
        task_id=getattr(task, "id", None),
        components=components,
        total=total,
        job_size_min=job_size_min,
        wsjf=total / job_size_min,
    )


def rank_tasks(
    tasks: Sequence[ScorableTask],
    now: datetime,
    estimates: Sequence[tuple[int, int] | None] | None = None,
) -> list[tuple[ScorableTask, PlannerScore]]:
    """Xếp hạng TOÀN BỘ `tasks` theo `wsjf` giảm dần, KHÔNG cắt bớt (OD-01 —
    hiển thị 3 việc là việc của tầng trên, planner chỉ xếp hạng đầy đủ để tầng
    đó "kéo" tiếp khi một việc xong).

    `estimates[i]` phải khớp `tasks[i]` theo vị trí (không theo `task.id`, vì
    task chưa insert DB có thể chưa có id). Không truyền `estimates` nghĩa là
    không có ước lượng cho task nào — vẫn xếp hạng được nhờ `NEUTRAL_JOB_SIZE_MIN`.

    Đồng hạng WSJF giữ nguyên thứ tự đầu vào (`sorted` ổn định) — không có
    tiêu chí phá đồng hạng nào khác được ADR chỉ định, và một tie-break bịa ra
    sẽ không giải thích được.
    """
    if estimates is not None and len(estimates) != len(tasks):
        raise ValueError("estimates phải khớp số lượng và thứ tự với tasks")
    resolved_estimates = estimates if estimates is not None else [None] * len(tasks)
    scored = [(t, score_task(t, now, e)) for t, e in zip(tasks, resolved_estimates)]
    return sorted(scored, key=lambda pair: pair[1].wsjf, reverse=True)
