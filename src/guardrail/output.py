from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class GroundingResult(BaseModel):
    status: str
    claims: list[dict[str, Any]] = Field(default_factory=list)
    reason: str | None = None
    conflict: bool = False


def _tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[\wÀ-ỹ]+", value.lower()) if len(x) > 2}


# Ký tự chỉ có trong chữ quốc ngữ (nguyên âm có dấu phụ + đ) — đủ để phân biệt
# tiếng Việt với các thứ tiếng Latin khác mà không cần thư viện nhận dạng.
_VIETNAMESE_CHARS = re.compile(r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩị"
                               r"óòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]")
_CJK_CHARS = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")

# Chi tiết sống sót qua dịch thuật: số, ngày, mã định danh (TAPB-178, T004),
# email, URL. Đây là thứ mô hình có thể bịa ra và gây hại thật, khác với câu
# chữ diễn giải.
_ANCHOR_RE = re.compile(
    r"(?i)(?:https?://\S+|[\w.+-]+@[\w-]+\.[\w.-]+|\b[a-z]{2,}[-_]?\d{2,}\b|\d{1,4}(?:[/-]\d{1,4}){0,2})"
)


# Nhãn cấu trúc do CHÍNH pipeline chèn vào bằng chứng: "[Từ:]", "[Đến:]",
# "[Đính kèm:]", "[Người báo:]"… (src/services/attribution.py). Chúng luôn viết
# bằng tiếng Việt bất kể mail viết bằng gì.
_STRUCTURAL_LABEL_RE = re.compile(r"\[[^\]]*\]")


def _script_bucket(value: str) -> str:
    """Nhóm chữ viết thô của một đoạn văn bản.

    Không phải bộ nhận dạng ngôn ngữ đầy đủ, và không cần phải thế: mục đích
    duy nhất là biết bản tóm tắt CÓ đang ở khác hệ chữ với nguồn hay không.

    Nhãn cấu trúc bị bỏ trước khi đoán, và chỉ ở đây: để nguyên thì mọi nguồn
    đều bị đọc là tiếng Việt (do chữ trong nhãn), kể cả mail thuần tiếng Anh —
    tức là bản tóm tắt tiếng Anh luôn bị coi là khác hệ chữ với nguồn tiếng
    Anh. Phép đo overlap bên dưới vẫn dùng văn bản đầy đủ, không đụng tới.
    """
    content = _STRUCTURAL_LABEL_RE.sub(" ", value)
    if _CJK_CHARS.search(content):
        return "cjk"
    if _VIETNAMESE_CHARS.search(content):
        return "vi"
    return "latin"


_DATE_RE = re.compile(r"\d{1,4}(?:[/-]\d{1,4}){1,2}")


def _anchors(value: str, *, expand_dates: bool = False) -> set[str]:
    """Neo trong văn bản. ``expand_dates`` chỉ bật cho phía NGUỒN.

    Nguồn ghi "21/08", bản tóm tắt tiếng Anh viết "August 21" — neo "21" khi đó
    không khớp chuỗi nào và bị kết luận là bịa đặt, dù đó chỉ là cách viết ngày
    khác. Tách thành phần của ngày Ở PHÍA NGUỒN khiến cách viết lại được chấp
    nhận, mà không nới lỏng phía bản tóm tắt: mọi neo model viết ra vẫn phải tìm
    thấy trong nguồn.
    """
    found: set[str] = set()
    for match in _ANCHOR_RE.findall(value):
        token = match.lower().rstrip(".,;:)")
        if not token:
            continue
        found.add(token)
        if expand_dates and _DATE_RE.fullmatch(token):
            found.update(part.lstrip("0") or "0" for part in re.split(r"[/-]", token))
    return found


def ground_candidate(
    candidate: str,
    evidence: dict[str, str],
    cited_ids: list[str] | None = None,
    *,
    conflicting: bool = False,
    permission_check: dict[str, bool] | None = None,
) -> GroundingResult:
    """Final deterministic gate for generated prose.

    Callers may pass structured claims through ``cited_ids``.  For prose, we
    require meaningful lexical support from the cited evidence; this catches
    missing/foreign citations without pretending lexical overlap proves truth.
    """
    if conflicting:
        return GroundingResult(status="uncertain", reason="conflicting_evidence", conflict=True)
    ids = cited_ids or list(evidence)
    if not candidate.strip() or not ids:
        return GroundingResult(status="abstain", reason="no_evidence")
    for evidence_id in ids:
        if evidence_id not in evidence:
            return GroundingResult(status="reject", reason="unknown_evidence_id")
        if permission_check is not None and not permission_check.get(evidence_id, False):
            return GroundingResult(status="reject", reason="permission_revoked")
    source_text = " ".join(evidence[i] for i in ids)
    source_tokens = set().union(*(_tokens(evidence[i]) for i in ids))

    # Bản tóm tắt viết bằng ngôn ngữ KHÁC nguồn (người dùng để giao diện tiếng
    # Việt nhưng mail tiếng Anh, hoặc ngược lại) gần như không trùng từ vựng
    # nào với nguồn, nên phép đo overlap bên dưới luôn trượt -> mọi bản dịch bị
    # loại và người dùng nhận lại đúng câu trích nguyên văn tiếng gốc.
    #
    # Ở đây đổi sang thứ SỐNG SÓT qua dịch thuật: số, ngày, mã định danh,
    # email, URL. Ràng buộc chặt hơn về mặt sự kiện (mọi chi tiết cụ thể trong
    # bản tóm tắt phải có trong nguồn), nhưng cố ý không kiểm được phần diễn
    # giải — không có mô hình thì không tầng tất định nào làm được việc đó.
    if _script_bucket(candidate) != _script_bucket(source_text):
        invented = _anchors(candidate) - _anchors(source_text, expand_dates=True)
        if invented:
            return GroundingResult(
                status="abstain",
                reason="unsupported_claim",
                claims=[{"text": candidate, "evidence_ids": ids, "invented": sorted(invented)}],
            )
        return GroundingResult(
            status="grounded",
            claims=[{"text": candidate, "evidence_ids": ids, "check": "cross_language_anchors"}],
        )

    overlap = len(_tokens(candidate) & source_tokens) / max(1, len(_tokens(candidate)))
    if overlap < 0.20:
        return GroundingResult(status="abstain", reason="unsupported_claim")
    return GroundingResult(
        status="grounded",
        claims=[{"text": candidate, "evidence_ids": ids}],
    )
