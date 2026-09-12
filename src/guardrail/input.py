from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from enum import Enum
from typing import Any
from urllib.parse import unquote

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    DEADLINE = "deadline_query"
    TASK = "task_query"
    CHANGE = "change_query"
    CONFLICT = "conflict_query"
    SOURCE = "source_query"
    SUMMARY = "summary_query"
    ACTION = "action_request"
    GENERAL = "general_knowledge"
    UNSUPPORTED = "unsupported"


class Evidence(BaseModel):
    """The minimum contract required before content can reach a model."""

    evidence_id: str
    text: str = Field(min_length=1)
    user_id: str | int | None = None
    current_user_id: str | int | None = None
    source_connection_active: bool = True
    permission_state: str = "allowed"
    status: str = "active"
    retention_valid: bool = True
    source: str = "unknown"
    authority: str = "B"
    source_url: str | None = None


class InputDecision(BaseModel):
    decision: str
    intent: QueryIntent
    coverage: str = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)
    excluded_sources: list[dict[str, str]] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class InjectionScan(BaseModel):
    """A finding, not an automatic user ban.

    ``severity`` is intentionally separate from ``detected`` so callers can
    choose warn/redact/reject according to context (user query vs source data).
    """

    detected: bool = False
    severity: str = "none"
    findings: list[str] = Field(default_factory=list)
    normalized_text: str = ""


_INTENT_WORDS = {
    QueryIntent.DEADLINE: ("deadline", "hạn", "khi nào nộp", "đến bao giờ"),
    QueryIntent.TASK: ("việc", "task", "cần làm", "to-do", "todo"),
    QueryIntent.CHANGE: ("thay đổi", "đổi", "updated", "moved", "gia hạn"),
    QueryIntent.CONFLICT: ("mâu thuẫn", "khác nhau", "conflict", "xung đột"),
    QueryIntent.SOURCE: ("nguồn", "email nào", "ở đâu", "source"),
    QueryIntent.SUMMARY: ("tóm tắt", "tổng hợp", "summary"),
    QueryIntent.ACTION: ("tạo", "lập", "nhắc", "calendar", "gửi", "send"),
}


def classify_query(query: str) -> QueryIntent:
    """Conservative product scope classifier; general chat is not in scope."""
    normalized = " ".join(query.lower().split())
    for intent, words in _INTENT_WORDS.items():
        if any(word in normalized for word in words):
            return intent
    return QueryIntent.GENERAL if normalized else QueryIntent.UNSUPPORTED


def _eligible(item: Evidence) -> tuple[bool, str]:
    if item.user_id is not None and item.current_user_id is not None and str(item.user_id) != str(item.current_user_id):
        return False, "cross_user"
    if not item.source_connection_active:
        return False, "connection_inactive"
    if item.permission_state != "allowed":
        return False, "permission_" + item.permission_state
    if item.status in {"deleted", "revoked"}:
        return False, item.status
    if not item.retention_valid:
        return False, "retention_expired"
    return True, ""


def build_context_pack(
    query: str,
    items: list[Evidence],
    *,
    coverage: str = "complete",
    max_items: int = 12,
    max_chars_each: int = 1200,
) -> tuple[InputDecision, list[dict[str, Any]]]:
    """Authorize and minimize evidence before it is interpolated into a prompt."""
    intent = classify_query(query)
    query_scan = scan_prompt_injection(query)
    allowed: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for item in items:
        ok, reason = _eligible(item)
        if not ok:
            excluded.append({"source": item.source, "reason": reason})
            continue
        allowed.append(
            {
                "evidence_id": item.evidence_id,
                "source": item.source,
                "authority": item.authority,
                "text": sanitize_untrusted_text(item.text)[:max_chars_each],
                "source_url": item.source_url,
            }
        )
    # Casual input such as "hi" is not a security violation. Scope routing can
    # decide how to answer it later; this layer should not block it.
    decision = (
        "allow"
        if (
            query_scan.severity != "high"
            and (intent == QueryIntent.GENERAL or (intent != QueryIntent.UNSUPPORTED and bool(allowed)))
        )
        else "abstain"
    )
    risks = ["partial_coverage"] if coverage == "partial" else []
    if query_scan.detected:
        risks.extend(f"query_{finding}" for finding in query_scan.findings)
    if excluded:
        risks.append("excluded_evidence")
    if intent == QueryIntent.GENERAL:
        risks.append("out_of_scope")
    return InputDecision(
        decision=decision,
        intent=intent,
        coverage=coverage,
        evidence_ids=[x["evidence_id"] for x in allowed],
        excluded_sources=excluded,
        risk_flags=risks,
    ), allowed[:max_items]


_DIRECT_INJECTION = re.compile(
    r"(?is)(ignore\s+(?:(?:all|any)\s+)?(?:previous|prior|the\s+current|all)?\s*(instructions?|rules?|messages?)|"
    r"disregard\s+(all|previous|the)|forget\s+(everything|all|previous)|"
    r"override\s+(the\s+)?(system|developer|safety|security)|"
    r"system\s+prompt|developer\s+message|reveal\s+(your|the)\s+(prompt|instructions?)|"
    r"show\s+(me\s+)?(your|the)\s+(hidden|secret)\s+(prompt|rules?)|"
    r"do\s+not\s+follow|jailbreak|prompt\s+injection|bypass\s+(safety|security|policy))"
)
_ROLEPLAY_INJECTION = re.compile(
    r"(?is)(you\s+are\s+now\s+(?:(?:a|an|the)\b|dan\b)|act\s+as\s+(a|an|the)|"
    r"pretend\s+(to\s+be|you\s+are)|"
    r"role[- ]?play\s+as|simulate\s+(a|an)\s+(developer|system|admin)|"
    r"from\s+now\s+on\s+you\s+are|enter\s+developer\s+mode|developer\s+mode)"
)
_VIETNAMESE_DIRECT_INJECTION = re.compile(
    r"(?is)(?:"
    r"(?:bo\s+qua|phot\s+lo|quen(?:\s+(?:het|toan\s+bo|moi|tat\s+ca))?)\s+"
    r"(?:(?:het|toan\s+bo|moi|tat\s+ca)\s+)?(?:cac?\s+)?"
    r"(?:huong\s+dan|chi\s+dan|quy\s+tac|lenh)\s+"
    r"(?:truoc\s+do|truoc\s+day|hien\s+tai|cua\s+he\s+thong)"
    r"|(?:cho\s+(?:(?:toi|minh|ta)\s+)?xem|tiet\s+lo|hien\s+thi)\s+"
    r"(?:(?:toan\s+bo|noi\s+dung|cac?)\s+)?"
    r"(?:prompt\s+he\s+thong|chi\s+dan\s+an|quy\s+tac\s+an)"
    r"|(?:bo\s+qua|vuot\s+qua|vo\s+hieu\s+hoa|tat)\s+"
    r"(?:(?:cac?|moi|toan\s+bo)\s+)?(?:quy\s+tac\s+)?"
    r"(?:an\s+toan|kiem\s+duyet|bao\s+mat)"
    r"|(?:bat|kich\s+hoat|chuyen\s+sang)\s+(?:che\s+do\s+)?khong\s+gioi\s+han"
    r")"
)
_VIETNAMESE_ROLEPLAY_INJECTION = re.compile(
    r"(?is)(?:"
    r"(?:dong\s+vai(?:\s+tro)?(?:\s+la)?|gia\s+vo(?:\s+la)?|gia\s+lam)\s+"
    r"(?:(?:mot|nguoi)\s+)?(?:admin|quan\s+tri(?:\s+vien)?|nha\s+phat\s+trien|he\s+thong)\b"
    r"|(?:tu\s+(?:gio|bay\s+gio)(?:\s+tro\s+di)?\s+)?"
    r"ban\s+(?:bay\s+gio\s+|hien\s+gio\s+)?(?:la|se\s+la)\s+"
    r"(?:admin|quan\s+tri(?:\s+vien)?|nha\s+phat\s+trien|he\s+thong)\b"
    r"|(?:bat|kich\s+hoat|vao|chuyen\s+sang)\s+che\s+do\s+nha\s+phat\s+trien"
    r")"
)
_DELIMITER_SMUGGLING = re.compile(r"(?is)(\<\/?system\>|\<\/?developer\>|\[/?system\]|```\s*(system|developer))")
_ENCODED_TOKEN = re.compile(r"(?i)(?:[A-Za-z0-9+/]{24,}={0,2}|(?:[0-9a-f]{2}){12,})")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")


def canonical_text(text: str) -> str:
    """Dạng chuẩn dùng cho MỌI phép so khớp với văn bản đã qua
    `sanitize_untrusted_text`.

    NFKC đổi dấu câu toàn rộng thành nửa rộng ("？" -> "?", "：" -> ":") và
    khoảng trắng bị gộp lại. Nghĩa là chuỗi mô hình ĐỌC không giống chuỗi gốc
    trong DB. Chỗ nào kiểm "trích có nguyên văn không" mà so thẳng với bản gốc
    thì sai — mail tiếng Nhật hầu như luôn trượt (bug thật: mail giao việc
    tiếng Nhật bị bỏ im lặng ở extract_batch).
    """
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return " ".join(text.split())


def _canonical(text: str) -> str:
    return canonical_text(text)


def _fold_vietnamese(text: str) -> str:
    """Bỏ dấu chỉ cho detection, giữ nguyên độ dài để redact đúng span."""
    folded: list[str] = []
    for char in text:
        if char == "đ":
            folded.append("d")
        elif char == "Đ":
            folded.append("D")
        else:
            decomposed = unicodedata.normalize("NFD", char)
            folded.append(decomposed[0] if len(decomposed) > 1 else char)
    return "".join(folded)


def _sub_folded(pattern: re.Pattern[str], replacement: str, text: str) -> str:
    """Thay match trên bản bỏ dấu nhưng cắt đúng văn bản gốc đã canonicalize."""
    matches = list(pattern.finditer(_fold_vietnamese(text)))
    if not matches:
        return text
    chunks: list[str] = []
    cursor = 0
    for match in matches:
        start, end = match.span()
        chunks.extend((text[cursor:start], replacement))
        cursor = end
    chunks.append(text[cursor:])
    return "".join(chunks)


def _decoded_payloads(text: str) -> list[tuple[str, str]]:
    payloads: list[tuple[str, str]] = []
    for token in _ENCODED_TOKEN.findall(text):
        try:
            if re.fullmatch(r"(?:[0-9a-f]{2})+", token, re.I):
                decoded = bytes.fromhex(token).decode("utf-8")
                payloads.append(("hex", decoded))
            else:
                decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True).decode("utf-8")
                payloads.append(("base64", decoded))
        except (ValueError, UnicodeDecodeError, binascii.Error):
            continue
    decoded_url = unquote(text)
    if decoded_url != text:
        payloads.append(("url_encoding", decoded_url))
    return payloads


def scan_prompt_injection(text: str) -> InjectionScan:
    """Detect direct, role-play, delimiter and common encoded injection forms.

    Detection is deliberately context-neutral. A caller may warn on a user
    asking about security, while source content should be sanitized before the
    model sees it.
    """
    normalized = _canonical(text)
    folded_vietnamese = _fold_vietnamese(normalized)
    findings: list[str] = []
    if _DIRECT_INJECTION.search(normalized) or _VIETNAMESE_DIRECT_INJECTION.search(folded_vietnamese):
        findings.append("direct_instruction_override")
    if _ROLEPLAY_INJECTION.search(normalized) or _VIETNAMESE_ROLEPLAY_INJECTION.search(folded_vietnamese):
        findings.append("role_play_override")
    if _DELIMITER_SMUGGLING.search(normalized):
        findings.append("prompt_delimiter_smuggling")
    if _ZERO_WIDTH.search(text):
        findings.append("hidden_unicode_control")
    for encoding, decoded in _decoded_payloads(text):
        decoded_scan = scan_prompt_injection(decoded)
        if decoded_scan.detected:
            findings.extend(f"encoded_{encoding}:{finding}" for finding in decoded_scan.findings)
        elif decoded.strip():
            findings.append(f"encoded_{encoding}")
    # A single hidden/encoded token is a warning; explicit instruction
    # override or a decoded override is high risk.
    high_risk = any(
        finding == "direct_instruction_override"
        or finding == "role_play_override"
        or "direct_instruction_override" in finding
        or "role_play_override" in finding
        for finding in findings
    )
    severity = "high" if high_risk else ("medium" if findings else "none")
    return InjectionScan(
        detected=bool(findings),
        severity=severity,
        findings=list(dict.fromkeys(findings)),
        normalized_text=normalized,
    )


def sanitize_untrusted_text(text: str) -> str:
    """Mark likely prompt-injection text without deleting useful source content."""
    text = text.replace("\x00", "")
    scan = scan_prompt_injection(text)
    text = _canonical(text)
    if not scan.detected:
        return text
    # Keep the surrounding source for evidence, but make the instruction
    # boundary explicit. Encoded payloads are not useful as evidence to LLM.
    text = _DIRECT_INJECTION.sub("[untrusted instruction removed]", text)
    text = _ROLEPLAY_INJECTION.sub("[untrusted role override removed]", text)
    text = _sub_folded(_VIETNAMESE_DIRECT_INJECTION, "[untrusted instruction removed]", text)
    text = _sub_folded(_VIETNAMESE_ROLEPLAY_INJECTION, "[untrusted role override removed]", text)
    text = _DELIMITER_SMUGGLING.sub("[untrusted delimiter removed]", text)
    if any(f.startswith("encoded_") for f in scan.findings):
        text = _ENCODED_TOKEN.sub("[encoded content removed]", text)
    return text


def evidence_block(items: list[dict[str, Any]]) -> str:
    """Format source data separately from system/user instructions."""
    return "\n---\n".join(
        f'<evidence id="{x["evidence_id"]}" trust="untrusted_content">\n{x["text"]}\n</evidence>' for x in items
    )
