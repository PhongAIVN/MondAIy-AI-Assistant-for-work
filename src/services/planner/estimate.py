"""Ước lượng thời lượng việc — ADR-018 QĐ-2, đường "Ước lượng khi có tiền lệ" /
"Ước lượng khi chưa có tiền lệ".

Không gọi LLM, không I/O — hàm thuần, nhận dữ liệu đã truy vấn sẵn (`history`)
từ tầng gọi. Thứ tự ưu tiên nguồn, đúng ADR:

1. Reference-class forecasting — nếu có đủ tiền lệ TƯƠNG TỰ của CHÍNH user này
   (so theo `actual_minutes`, không phải elapsed — xem ADR-018 mục bổ sung
   2026-08-26).
2. `estimate_low_min`/`estimate_high_min` đã lưu sẵn trên task.
3. Không có gì cả -> `None`. `None` là câu trả lời hợp lệ, KHÔNG được đoán.

PERT ba điểm `(o + 4m + p) / 6` KHÔNG được cài ở module này: hôm nay không có
nguồn nào đưa optimistic/most-likely/pessimistic — tự bịa ba mốc từ một
low/high sẵn có là đoán, đúng thứ ADR cấm ("KHÔNG tự bịa ba mốc").
"""

from __future__ import annotations

import re
import statistics
from typing import Protocol


class EstimatableTask(Protocol):
    """Contract tối thiểu planner cần từ một task — không ràng buộc vào model
    ORM cụ thể, để test dùng được object giả nhẹ."""

    user_id: str
    title: str
    estimate_low_min: int | None
    estimate_high_min: int | None


class HistoricalTask(Protocol):
    """Một task đã hoàn tất, dùng làm tiền lệ cho reference-class."""

    user_id: str
    title: str
    actual_minutes: int | None


# Số mẫu tương tự tối thiểu để tin một reference class. Chọn 5: dưới ngưỡng
# này, phân vị (percentile) dao động quá mạnh chỉ vì thêm/bớt một task — ví dụ
# với 2-3 mẫu, quartile gần như trùng min/max, cho một khoảng giả-chính-xác.
# 5 là ngưỡng thường dùng cho ước lượng phân vị thô (đủ để p25/p75 không suy
# biến về đúng 1-2 điểm dữ liệu biên) mà vẫn khả thi khi dữ liệu người dùng
# còn mỏng (ADR-018: prod hôm nay có 0/257 actual_minutes, nên đường này sẽ
# gần như luôn rơi xuống fallback #2 trong giai đoạn đầu — đúng như ADR dự
# đoán "giai đoạn đầu chỉ có PERT" — ở đây là fallback estimate đã lưu).
MIN_SIMILAR_SAMPLES = 5

# Ngưỡng Jaccard trên tập token của title để coi hai task là "tương tự". Chọn
# theo token của title (không dùng cluster_key: cột đó unique theo
# (user_id, cluster_key) — dùng để gộp tín hiệu thành MỘT task, không phải
# nhãn nhóm dùng chung giữa nhiều task). 0.5 nghĩa là quá nửa từ có nghĩa
# trùng nhau — đủ chặt để "trả lời email cho khách A" không lẫn với "trả lời
# email cho khách B" (chỉ trùng "trả", "lời", "email"), nhưng đủ lỏng để bỏ
# qua khác biệt nhỏ như thì/số nhiều.
SIMILARITY_THRESHOLD = 0.5

# Từ hư/từ quá ngắn không mang nghĩa phân biệt việc này với việc khác — loại
# khỏi tập token trước khi so Jaccard, tránh hai task khác hẳn nhau nhưng
# cùng chứa "the", "và", "cho" bị tính là tương tự.
_STOPWORDS = {
    "a", "an", "the", "to", "for", "of", "in", "on", "at", "and", "or",
    "và", "của", "cho", "với", "để", "là", "các", "một", "những", "và",
    "này", "đó", "cần", "hãy", "làm",
}

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _title_tokens(title: str) -> frozenset[str]:
    """Chuẩn hoá title thành tập token so khớp: thường hoá, tách theo ký tự
    chữ/số, bỏ stopword và token 1 ký tự (quá ngắn để mang nghĩa)."""
    tokens = _TOKEN_RE.findall(title.lower())
    return frozenset(t for t in tokens if t not in _STOPWORDS and len(t) > 1)


def _is_similar(a_tokens: frozenset[str], b_tokens: frozenset[str]) -> bool:
    if not a_tokens or not b_tokens:
        return False
    union = a_tokens | b_tokens
    if not union:
        return False
    jaccard = len(a_tokens & b_tokens) / len(union)
    return jaccard >= SIMILARITY_THRESHOLD


def _reference_class_actuals(
    task: EstimatableTask, history: list[HistoricalTask]
) -> list[int]:
    """Lọc history còn lại đúng của cùng user, có actual_minutes thật, và
    tương tự task hiện tại theo title."""
    task_tokens = _title_tokens(task.title)
    actuals: list[int] = []
    for past in history:
        if past.user_id != task.user_id:
            continue
        if past.actual_minutes is None:
            continue
        if not _is_similar(task_tokens, _title_tokens(past.title)):
            continue
        actuals.append(past.actual_minutes)
    return actuals


def estimate_minutes(
    task: EstimatableTask, history: list[HistoricalTask]
) -> tuple[int, int] | None:
    """Ước lượng `(low_min, high_min)` cho một task, hoặc `None` nếu không có
    cơ sở nào để ước lượng — xem thứ tự nguồn ở docstring module."""
    similar_actuals = _reference_class_actuals(task, history)
    if len(similar_actuals) >= MIN_SIMILAR_SAMPLES:
        # Khoảng liên tứ phân vị (p25-p75): phản ánh độ lệch thật quan sát
        # được giữa các lần làm việc tương tự, thay vì một khoảng bịa quanh
        # trung vị. quantiles(n=4) trả [p25, p50, p75].
        q1, _, q3 = statistics.quantiles(sorted(similar_actuals), n=4)
        low, high = round(q1), round(q3)
        if low > high:  # có thể lệch 1 phút do làm tròn khi mẫu rất ít giá trị khác nhau
            low, high = high, low
        return (low, high)

    if task.estimate_low_min is not None and task.estimate_high_min is not None:
        # Tin dữ liệu đã lưu như đang có — không tự "sửa" nếu low > high, vì
        # đó là lỗi ở nguồn ghi, không phải việc estimate_minutes suy đoán hộ.
        return (task.estimate_low_min, task.estimate_high_min)

    return None
