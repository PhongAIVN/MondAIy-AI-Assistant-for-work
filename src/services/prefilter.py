"""Tầng lọc rác rẻ, chạy TRƯỚC khi gọi AI tách việc (Hướng 4,
summarize_page_extraction trong page_extraction.py) — mục tiêu giảm số lần
gọi LLM cho nội dung rõ ràng không phải việc cần làm (banner quảng cáo, chat
phiếm, ngôn ngữ khác). 3 bước tuần tự, dừng ngay ở bước đầu tiên fail:

1. Đủ ký tự/token, có chữ cái thật không (regex/đếm thuần trên CẢ đoạn).
2. Đúng ngôn ngữ mục tiêu (đo trên cả đoạn) + có DÒNG nào khớp từ khóa đặc
   trưng việc-cần-làm không (tái dùng các pattern rule từ page_extraction.py).
3. Có DÒNG nào mang tân ngữ (đối tượng bị tác động) không
   (_has_object_like_complement xấp xỉ qua underthesea.chunk).

Bước 2-3 xét TỪNG DÒNG rồi lấy OR (qua 1 dòng bất kỳ là đủ), KHÔNG chạy thẳng
trên cả khối nhiều dòng — _RULE_SIGNAL_PATTERNS/_has_object_like_complement
đều được thiết kế và đo cho một dòng/câu, đưa thẳng cả đoạn nhiều dòng vào sẽ sai:
- Pattern neo đầu chuỗi (vd _IMPERATIVE_START_PATTERN dùng .match()) chỉ khớp
  được ký tự đầu tiên của CẢ đoạn, bỏ lỡ tín hiệu nằm ở dòng thứ 2/3 trở đi.
- chunk() của underthesea xử lý cả đoạn như một câu liên tục, có thể ghép
  nhầm VP cuối dòng này với NP đầu dòng khác vốn không liên quan.
Bước 1 (đếm ký tự/token) vẫn xét cả đoạn — đây là câu hỏi tổng quan "có đủ
nội dung để đáng xem xét không", không cần tách dòng.

Toàn văn bản (không tách dòng) vẫn được gửi nguyên cho AI tách việc
khi qua được cả 3 bước — pre-filter chỉ quyết định CÓ GỌI AI hay không, không
cắt bớt dòng nào khỏi payload, giữ nguyên khả năng gom dòng rải rác.

Đây là 3 heuristic RẺ, mỗi bước tự nó không hoàn hảo — caller (page_extraction.py)
KHÔNG được coi reject ở đây là "chắc chắn rác" — phải fallback về nguyên văn
(_fallback_summary), không im lặng bỏ qua, để lỡ bỏ sót vẫn còn đường cho user
tự thấy lại dữ liệu đã trích.
"""

from __future__ import annotations

from dataclasses import dataclass

from langid.langid import LanguageIdentifier
from langid.langid import model as _langid_model
from underthesea import chunk

from src.services.page_extraction import (
    _ACTION_VERB_PATTERN,
    _CHECKLIST_PATTERN,
    _DATE_PATTERN,
    _DEADLINE_KEYWORD_PATTERN,
    _EXPLICIT_ASSIGNMENT_PATTERN,
    _HELP_REQUEST_PATTERN,
    _IMPERATIVE_START_PATTERN,
    _MENTION_PATTERN,
    _split_lines,
)

_MIN_CHARS = 5
_MIN_TOKENS = 2
_TARGET_LANG = "vi"
_MIN_LANG_CONFIDENCE = 0.5
# Dòng emoticon/reaction kiểu ":o" ":-((" ":-h" ">:>" chỉ có 0-1 ký tự chữ cái
# thật — dưới ngưỡng này thì xoá thẳng khỏi text trước khi gửi AI, không chờ
# đến bước gate (chk1 hiện chỉ xét TỔNG cả đoạn, một dòng rác lẫn trong 631
# dòng chat thật không làm tổng đó rớt ngưỡng được). KHÔNG bắt được sticker
# code dài có chữ thật bên trong (vd "/-heart" = 5 chữ cái) — cần rule khác
# (khớp theo tiền tố "/-") nếu muốn xử luôn, ngoài phạm vi luật "đếm chữ" này.
_MIN_REAL_LETTERS_PER_LINE = 2

# langid.classify() ở module-level (hàm rời) mặc định trả joint log-probability
# THÔ, KHÔNG chuẩn hoá (số âm lớn kiểu -270.8, không nằm trong [0,1]) — đã tự
# verify thực tế lúc viết test, ban đầu tưởng nhầm là xác suất chuẩn hoá sẵn.
# Phải tự dựng LanguageIdentifier với norm_probs=True mới ra (lang, prob) với
# prob thật sự trong [0,1] để so ngưỡng có ý nghĩa. Dựng một lần ở module
# scope, không dựng lại mỗi lần gọi (tốn khởi tạo model).
_LANG_IDENTIFIER = LanguageIdentifier.from_modelstring(_langid_model, norm_probs=True)

_RULE_SIGNAL_PATTERNS: list[tuple[str, object]] = [
    ("checklist", _CHECKLIST_PATTERN.match),
    ("date", _DATE_PATTERN.search),
    ("deadline_kw", _DEADLINE_KEYWORD_PATTERN.search),
    ("imperative", _IMPERATIVE_START_PATTERN.match),
    ("assignment", _EXPLICIT_ASSIGNMENT_PATTERN.search),
    ("help_req", _HELP_REQUEST_PATTERN.search),
    ("mention", _MENTION_PATTERN.search),
    ("action_verb", _ACTION_VERB_PATTERN.search),
]


def _has_object_like_complement(text: str) -> bool:
    """Xấp xỉ "câu có tân ngữ không" bằng chunk() (không cần torch): có cụm
    danh từ (B-NP) xuất hiện SAU cụm động từ (B-VP) đầu tiên hay không. Không
    chính xác bằng dependency parse thật (không phân biệt được NP đó có thật
    sự làm tân ngữ của đúng động từ đó hay là trạng ngữ/thành phần khác), chỉ
    là tín hiệu bổ sung cho prefilter, không dùng độc lập để quyết định.
    """
    seen_verb_phrase = False
    for _, _, phrase_tag in chunk(text):
        if phrase_tag == "B-VP":
            seen_verb_phrase = True
        elif phrase_tag == "B-NP" and seen_verb_phrase:
            return True
    return False


@dataclass(frozen=True)
class PrefilterResult:
    passed: bool
    # Lý do ngắn cho log/debug — KHÔNG hiển thị thẳng cho user, tránh rò rỉ
    # chi tiết nội bộ (giống style lỗi API hiện có trong repo).
    reason: str


def _lines_or_whole(text: str) -> list[str]:
    """chk1 đã đảm bảo text có nội dung thật trước khi các hàm này chạy, nên
    chỉ cần fallback [text] cho trường hợp _split_lines rỗng vì lý do khác
    (vd toàn ký tự không phải chữ cái lọt qua chk1 ở biên)."""
    return _split_lines(text) or [text]


def _chk1_length(text: str) -> bool:
    stripped = text.strip()
    if not any(ch.isalpha() for ch in stripped):
        return False
    if len(stripped) < _MIN_CHARS:
        return False
    return len(stripped.split()) >= _MIN_TOKENS


def _chk2_keyword_and_language(text: str) -> bool:
    lang, confidence = _LANG_IDENTIFIER.classify(text)
    if lang != _TARGET_LANG or confidence < _MIN_LANG_CONFIDENCE:
        return False
    return any(
        any(matcher(line) for _, matcher in _RULE_SIGNAL_PATTERNS) for line in _lines_or_whole(text)
    )


def _chk3_object_signal(text: str) -> bool:
    return any(_has_object_like_complement(line) for line in _lines_or_whole(text))


def strip_junk_lines(text: str) -> str:
    """Xoá từng dòng emoticon/reaction thuần (dưới _MIN_REAL_LETTERS_PER_LINE
    chữ cái thật) khỏi text — khác 3 bước chk ở dưới (chỉ QUYẾT ĐỊNH có gọi AI
    hay không, không sửa payload): đây là bước LÀM SẠCH thật, chạy trước cả
    run_prefilter(), vì dòng thuần emoticon không mang tín hiệu thật nào (khác
    dòng "thường" có thể là một phần của việc rải rác — không đụng tới loại
    đó). An toàn dùng lại cho cả nhánh AI lẫn nhánh fallback nguyên văn, vì
    đây là loại rác chắc chắn 100%, không phải suy đoán như 3 bước chk."""
    kept = [line for line in _split_lines(text) if sum(1 for ch in line if ch.isalpha()) >= _MIN_REAL_LETTERS_PER_LINE]
    return "\n".join(kept)


def run_prefilter(text: str) -> PrefilterResult:
    if not _chk1_length(text):
        return PrefilterResult(False, "duoi_nguong_ky_tu_token")
    if not _chk2_keyword_and_language(text):
        return PrefilterResult(False, "sai_ngon_ngu_hoac_khong_khop_tu_khoa")
    if not _chk3_object_signal(text):
        return PrefilterResult(False, "khong_co_tan_ngu")
    return PrefilterResult(True, "qua_het")
