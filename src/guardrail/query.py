"""Cheap, deterministic checks that run before retrieval or an LLM call."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPreflight:
    action: str
    reason: str
    response: str | None = None
    expression: str | None = None


_SECRET_VALUE = (
    r"(?:\b(?:api\s*key|apikey|khoa\s+api|access\s+token|token\s+truy\s+cap|refresh\s+token|"
    r"mat\s+khau|secrets?|khoa\s+bi\s+mat|ma\s+bi\s+mat|thong\s+tin\s+dang\s+nhap|"
    r"tai\s+khoan\s+(?:va\s+)?mat\s+khau|bien\s+moi\s+truong|chuoi\s+ket\s+noi|"
    r"credentials?|thong\s+tin\s+xac\s+thuc)\b|(?<!\w)(?:file\s+)?\.env\b)"
)
_SECRET_ACTION = (
    r"(?:dua|lay|gui|show|give|reveal|provide|send|tiet\s+lo|doc(?:\s+giup)?|in(?:\s+ra)?|"
    r"copy|sao\s+chep|dan|trich|xuat)"
)
# Danh từ trung gian: có nó thì người dùng đang hỏi VỀ một tài liệu nhắc tới
# secret, không đòi chính secret. "đọc tài liệu API key giúp tôi" là câu hỏi
# chính đáng; "đọc giúp khoá API" thì không. Đây là ranh giới duy nhất phân
# biệt được hai câu gần như giống hệt nhau về mặt từ vựng.
_REFERENCE_NOUN = re.compile(
    r"\b(?:tai\s+lieu|huong\s+dan|task|ticket|issue|policy|quy\s+dinh|email|mail|"
    # KHÔNG đưa `doc` trần vào đây: "đọc" fold thành "doc" nên nó nuốt luôn
    # động từ, và "Đọc giúp khoá API" thoát cổng.
    r"link|note|ghi\s+chu|bao\s+cao|document)\b"
)
# Phủ định: câu dặn KHÔNG được làm gì không phải là câu đòi làm điều đó.
_NEGATION = re.compile(r"\b(?:khong\s+(?:nen|bao\s+gio|duoc|(?=gui|dua))|dung|cam|tranh)\b")
_RECEIVER = r"(?:toi|minh|t|em|anh|chi)"
_SECRET_ACTION_FIRST = re.compile(
    rf"(?<!\w)(?<!khong\s)(?<!dung\s)(?<!cam\s)(?<!khong\sduoc\s){_SECRET_ACTION}"
    rf"(?:\s+(?:giup\s+)?(?:cho\s+)?{_RECEIVER})?(?:\s+[\w-]+){{0,2}}\s+{_SECRET_VALUE}"
)
_SECRET_RECEIVER_FIRST = re.compile(
    rf"\b(?:cho\s+{_RECEIVER}(?:\s+(?:xin|xem))?|(?:cho\s+)?xin(?:\s+{_RECEIVER})?|"
    rf"noi\s+cho\s+{_RECEIVER})\s+{_SECRET_VALUE}"
)
_SECRET_VALUE_FIRST = re.compile(
    rf"{_SECRET_VALUE}(?:\s+[\w-]+){{0,2}}\s+"
    rf"(?:{_SECRET_ACTION}|khai\s+bao)(?:\s+(?:giup\s+)?(?:cho\s+)?{_RECEIVER}|\s+xem)\b"
)
# "API key cho tôi xem" — không có động từ nào, chỉ là giá trị + người nhận.
_SECRET_VALUE_TO_RECEIVER = re.compile(rf"{_SECRET_VALUE}\s+cho\s+{_RECEIVER}(?:\s+xem)?\b")
_SECRET_DECLARE_REQUEST = re.compile(rf"\bkhai\s+bao\s+{_SECRET_VALUE}\s+cho\s+{_RECEIVER}\b")

_ABUSIVE_TERM = (
    r"(?:\b(?:chui|mang|si\s+nhuc|noi\s+xau|de\s+doa|miet\s+thi|lang\s+ma|xuc\s+pham)\b)"
)
_ABUSIVE_IMPERATIVE = re.compile(
    rf"\b(?:hay|please|lam\s+on|giup\s+(?:toi|minh))\s+(?:[\w-]+\s+){{0,2}}{_ABUSIVE_TERM}"
)
_ABUSIVE_GENERATION = re.compile(
    rf"\b(?:viet|tao|soan)\s+(?:loi|cau|doan|tin\s+nhan|email)\s+"
    rf"(?:[\w-]+\s+){{0,1}}{_ABUSIVE_TERM}"
)
_ABUSIVE_SUFFIX = re.compile(
    rf"{_ABUSIVE_TERM}(?:\s+[\w-]+){{0,4}}\s+"
    rf"(?:di|nhe|ho|giup\s+(?:toi|minh)|cho\s+(?:toi|minh))\b"
)
# Mệnh lệnh trần: động từ xúc phạm đứng ĐẦU vế và có tân ngữ ngay sau.
# "Chửi nó" là ra lệnh; "Ai đã xúc phạm khách hàng?" thì không vì có chủ ngữ
# đứng trước.
_ABUSIVE_BARE_IMPERATIVE = re.compile(rf"^\s*{_ABUSIVE_TERM}\s+[\w-]+")
# Động từ XỬ LÝ nội dung xúc phạm — người dùng đang dọn dẹp hoặc tra cứu nó,
# không phải yêu cầu tạo ra nó.
_ABUSIVE_HANDLING_VERB = re.compile(
    r"\b(?:xoa|go|tim|tra\s+cuu|tong\s+hop|thong\s+ke|bao\s+cao|cap\s+nhat|chong|"
    r"kiem\s+tra|ra\s+soat|loc|phat\s+hien|ai\s+da)\b"
)
_ABUSIVE_ENGLISH = re.compile(
    r"(?:\bplease\s+(?:fuck|swear|insult)\b|\b(?:fuck|swear|insult)\b"
    r"(?:\s+[\w-]+){0,3}\s+(?:you|them|him|her|please)\b)"
)
_CLAUSE_SPLIT = re.compile(r"(?:(?<=[\w])\.(?=\s|$)|[!?;\n]+)")
_ARITHMETIC = re.compile(r"(?P<expression>[0-9][0-9\s+\-*/().%]+)\s*(?:=|l[aà]nh?|l[aà]\s*g[iì]|b[aằ]ng|m[aấ]y|bao\s*nhieu)")


# Use folded ASCII patterns at runtime. The source file historically contains
# mixed-encoding Vietnamese literals, so matching the normalized form keeps
# the guardrail deterministic across Windows and Linux.
_ARITHMETIC = re.compile(r"(?P<expression>[0-9][0-9\s+\-*/().%]+)\s*=")
_ARITHMETIC_REQUEST = re.compile(r"(?:tinh\s+)?[0-9][0-9\s+\-*/().%]+\s+(?:bang\s+may|bao\s*nhieu)\s*\??")
_WORD_ARITHMETIC_REQUEST = re.compile(r"[0-9]+\s+(?:cong|tru|nhan|chia)\s+[0-9]+\s+bang\s+may\s*\??")


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    return " ".join(
        "".join(char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char))
        .casefold()
        .split()
    )


def _is_secret_disclosure_request(text: str) -> bool:
    """Chỉ bind động từ cung cấp với secret trong cùng một vế ngắn.

    Hai lớp loại trừ, cả hai đều bảo vệ CÂU HỎI THẬT của người dùng. Chặn nhầm ở
    đây là chặn hẳn một câu hỏi chính đáng, tệ hơn nhiều so với bỏ sót một cách
    diễn đạt — model vẫn còn tầng từ chối phía sau.
    """
    for clause in _CLAUSE_SPLIT.split(text):
        # "Không bao giờ gửi API key" là lời dặn, không phải lời đòi.
        if _NEGATION.search(clause):
            continue
        # "Đọc tài liệu API key giúp tôi" hỏi về một tài liệu, không đòi khoá.
        if _REFERENCE_NOUN.search(clause):
            continue
        if (
            _SECRET_ACTION_FIRST.search(clause)
            or _SECRET_RECEIVER_FIRST.search(clause)
            or _SECRET_VALUE_FIRST.search(clause)
            or _SECRET_VALUE_TO_RECEIVER.search(clause)
            or _SECRET_DECLARE_REQUEST.search(clause)
        ):
            return True
    return False


def _is_abusive_generation_request(text: str) -> bool:
    """Phân biệt lệnh tạo lời xúc phạm với câu hỏi chỉ nhắc đến nó."""
    for clause in _CLAUSE_SPLIT.split(text):
        # "Hãy xóa câu chửi", "Tìm email xúc phạm khách hàng giúp tôi" — người
        # dùng đang dọn dẹp hoặc tra cứu nội dung xúc phạm, không đặt hàng nó.
        if _ABUSIVE_HANDLING_VERB.search(clause):
            continue
        if (
            _ABUSIVE_BARE_IMPERATIVE.search(clause)
            or _ABUSIVE_IMPERATIVE.search(clause)
            or _ABUSIVE_GENERATION.search(clause)
            or _ABUSIVE_SUFFIX.search(clause)
            or _ABUSIVE_ENGLISH.search(clause)
        ):
            return True
    return False


def preflight_query(query: str) -> QueryPreflight:
    """Chặn yêu cầu nguy hiểm rõ ràng trước khi gọi model hoặc công cụ."""
    folded = _fold(query)

    if _is_secret_disclosure_request(folded):
        return QueryPreflight(
            "block",
            "secret_request",
            "Mình không thể cung cấp API key hoặc thông tin nhạy cảm.",
        )

    if _is_abusive_generation_request(folded):
        return QueryPreflight(
            "block",
            "abusive_generation_request",
            "Mình không thể tạo nội dung chửi bậy hoặc xúc phạm người khác.",
        )

    arithmetic = _ARITHMETIC.search(folded)
    if arithmetic:
        expression = arithmetic.group("expression").strip()
        if re.fullmatch(r"[0-9\s+\-*/().%]+", expression):
            return QueryPreflight("fast_answer", "safe_arithmetic", expression=expression)

    # Keep natural-language arithmetic on the existing calculate-tool path;
    # only the unambiguous `1+1=` form is answered directly here.
    if (
        _ARITHMETIC_REQUEST.fullmatch(folded)
        or _WORD_ARITHMETIC_REQUEST.fullmatch(folded)
        or re.fullmatch(r"tinh\s+[0-9\s+\-*/().%]+", folded)
    ):
        return QueryPreflight("continue", "safe_arithmetic")

    return QueryPreflight("continue", "general_query")
