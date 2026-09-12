"""Chấm chất lượng một bản tóm tắt — TẤT ĐỊNH, không dùng LLM làm giám khảo.

Dùng LLM chấm LLM thì kết quả đổi theo từng lần chạy và không so sánh được ba
nhánh với nhau. Ở đây mọi tiêu chí đều kiểm được bằng chuỗi, nên chạy lại luôn
ra cùng con số và có thể đưa vào CI.

Bốn tiêu chí, mỗi cái ứng với một lỗi thật đã gặp trong quá trình làm:

* attribution — tóm tắt không nêu nguồn thì người dùng không biết việc từ đâu.
* coverage    — điểm chính (nhất là trong file đính kèm) phải còn.
* faithfulness— không được bịa số/ngày/mã không có trong bằng chứng.
* language    — theo ngôn ngữ GIAO DIỆN, không bám ngôn ngữ tư liệu.

Tiêu chí phụ `paraphrase` không tính vào điểm đúng/sai mà để phân biệt bản viết
lại với bản nối nguyên văn trích dẫn — hai thứ có thể cùng "đúng" nhưng đọc
khác hẳn nhau.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Neo: thứ sống sót qua dịch thuật và là thứ người dùng hành động theo. Cùng
# tinh thần với `_ANCHOR_RE` ở guardrail/output.py.
_ANCHOR_RE = re.compile(
    r"(?i)(?:[\w.+-]+@[\w-]+\.[\w.-]+|\b[a-z]{2,}-\d+\b|\d{1,4}(?:[/-]\d{1,4}){1,2}|\b\d+\b)"
)
_DATE_SEP_RE = re.compile(r"^\d{1,4}(?:[/-]\d{1,4}){1,2}$")
_VIETNAMESE_CHARS = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
    r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]"
)


def fold(value: str) -> str:
    """Bỏ dấu + hạ hoa thường, để "Lê Thị Yến Nhi" khớp với "yen nhi"."""
    normalized = unicodedata.normalize("NFKD", value).replace("đ", "d").replace("Đ", "d")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).casefold()


def anchors(value: str) -> set[str]:
    """Neo đã chuẩn hoá, để so sánh không bắt nhầm chuyện vô hại.

    Hai chuẩn hoá, mỗi cái vá một lần chấm sai đã quan sát được:

    * Bỏ dấu câu dính đuôi — regex email nuốt cả dấu chấm cuối câu, khiến
      "nhi@example.com." bị coi là địa chỉ khác với "nhi@example.com".
    * Ngày tách thêm thành phần — bản tóm tắt viết "August 21" từ bằng chứng
      "21/08" là diễn đạt lại, không phải bịa. Không tách thì mọi bản dịch
      ngày tháng đều bị chấm là bịa đặt.
    """
    found: set[str] = set()
    for match in _ANCHOR_RE.findall(value):
        token = match.lower().strip(".,;:")
        if not token:
            continue
        found.add(token)
        if _DATE_SEP_RE.search(token):
            found.update(part.lstrip("0") or "0" for part in re.split(r"[/-]", token))
    return found


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    attribution: bool
    coverage: bool
    faithful: bool
    language_ok: bool
    paraphrased: bool
    output: str

    @property
    def passed(self) -> bool:
        """Đạt = đúng cả bốn tiêu chí tính điểm. Paraphrase không tính."""
        return self.attribution and self.coverage and self.faithful and self.language_ok


def _looks_vietnamese(text: str) -> bool:
    return bool(_VIETNAMESE_CHARS.search(text))


def score_case(case: dict, output: str) -> CaseScore:
    """Chấm một bản tóm tắt theo kỳ vọng của case.

    Bản rỗng trượt hết — nó không phải "trung lập", nó là mất thông tin.
    """
    folded = fold(output or "")
    expectations = [fold(item) for item in case.get("must_mention", [])]

    # Attribution tách khỏi coverage: kỳ vọng đầu tiên luôn là tên người/nguồn
    # nếu case có nêu, phần còn lại là nội dung.
    sender_names = {
        fold(str((item.get("message") or {}).get("author_name") or ""))
        for item in case.get("items", [])
    }
    sender_names = {name for name in sender_names if name}
    attribution = bool(sender_names) and any(name in folded for name in sender_names)
    if not sender_names:
        attribution = True

    # Mỗi kỳ vọng cho phép nhiều cách viết, ngăn bằng "|": "22/08|august 22".
    # Cần vì cùng một ngày có nhiều cách diễn đạt hợp lệ tuỳ ngôn ngữ, ép đúng
    # một dạng chuỗi là chấm cách viết chứ không chấm nội dung.
    coverage = all(
        any(variant in folded for variant in expectation.split("|"))
        for expectation in expectations
    ) if expectations else True

    # Neo hop le = moi thu bang chung THAT SU chua, ke ca sieu du lieu nguon
    # (ten/email nguoi gui) vi dong [Tu:]/[Den:] duoc phep xuat hien trong ban
    # tom tat. Bo chung ra thi nhanh rule bi cham la "bia" chinh cai no trich.
    def _evidence_of(item: dict) -> str:
        message = item.get("message") or {}
        parts = [
            str(item.get("evidence_quote", "")),
            str(item.get("detail", "")),
            str(message.get("attachment_text", "")),
            str(message.get("author_name", "")),
            str(message.get("author_id", "")),
            str(message.get("id", "")),
            str(message.get("jira_assignee_name", "")),
            str(message.get("jira_status", "")),
            " ".join(str(x) for x in (message.get("to") or [])),
        ]
        return " ".join(part for part in parts if part)

    evidence_text = " ".join(_evidence_of(item) for item in case.get("items", []))
    invented = {fold(item) for item in case.get("must_not_invent", [])}
    faithful = not any(item in folded for item in invented)
    # Ngoài danh sách bẫy, mọi neo trong bản tóm tắt cũng phải có trong bằng chứng.
    faithful = faithful and not (anchors(output or "") - anchors(evidence_text))

    target = case.get("language", "vi")
    if not (output or "").strip():
        language_ok = False
    elif target == "vi":
        language_ok = _looks_vietnamese(output)
    else:
        # Tiếng Anh: không được lẫn chữ có dấu tiếng Việt.
        language_ok = not _looks_vietnamese(output)

    quotes = [str(item.get("evidence_quote", "")).strip() for item in case.get("items", [])]
    joined = " / ".join(q for q in quotes if q)
    paraphrased = bool((output or "").strip()) and fold(joined) not in folded

    return CaseScore(
        case_id=case["id"],
        attribution=attribution,
        coverage=coverage,
        faithful=faithful,
        language_ok=language_ok,
        paraphrased=paraphrased,
        output=output or "",
    )


def aggregate(scores: list[CaseScore]) -> dict[str, float]:
    total = len(scores) or 1
    return {
        "attribution": sum(s.attribution for s in scores) / total,
        "coverage": sum(s.coverage for s in scores) / total,
        "faithful": sum(s.faithful for s in scores) / total,
        "language": sum(s.language_ok for s in scores) / total,
        "paraphrased": sum(s.paraphrased for s in scores) / total,
        "passed": sum(s.passed for s in scores) / total,
    }
