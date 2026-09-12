"""Rule engine 100% rule-based cho Slack — KHÔNG gọi AI/LLM ở bất kỳ hàm nào.

Bám sát docs/projects/engineering/slack-detail.drawio (tab "Slack pipeline",
DRAFT — PRD hiện loại Slack khỏi scope chính thức): Normalization -> Hard
Filter -> Slack Rules + Common Rules -> Scoring -> Extraction -> Decision.
Mọi threshold/weight nằm trong RuleConfig — đổi được qua config.

Khác Jira: Slack không có due_date/assignee/status field cứng, nên KHÔNG có
NormalizedIssue.due_date/assignee_account_id kiểu Jira — deadline suy luận
CHỈ từ regex DEADLINE_RE (đánh dấu HAS_DEADLINE_INFERRED, không phải
HAS_DEADLINE, để phân biệt rõ với field cứng — xem docstring slack-detail.drawio
bước 8). Không có resolve_due_at()/NLP thời gian tương đối ở bản này — theo
dõi ở TODO(OD-SLACK2), việc sau.

Hai tín hiệu trong sơ đồ (bước 4) CHƯA wiring đầy đủ ở bản này, chủ động ghi
rõ thay vì giả vờ đã xong:
- "Reaction cần phản hồi" (:question:/:eyes:...): sơ đồ liệt là tín hiệu
  nhưng KHÔNG có trọng số chốt trong bảng RULE_CONFIG bước 5 — không tự bịa
  số, để trống scoring, chỉ giữ chỗ trong NormalizedMessage.reactions.
- "Pinned message" (pins.list): CÓ trọng số (+10) nhưng SlackConnector chưa
  gọi pins.list — NormalizedMessage.is_pinned mặc định False cho tới khi nối
  API đó (theo dõi TODO(OD-SLACK3)).
- "THREAD_REPLY_TO_SELF": connector hiện chỉ ingest message top-level qua
  conversations.history, KHÔNG backfill reply trong thread (xem docstring
  SlackConnector) — is_thread_reply_to_self mặc định False, tín hiệu này
  không thể trigger cho tới khi có TODO(OD-SLACK1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.services.filter_classify import (
    ACTION_RE,
    AUTOMATED_RE,
    DEADLINE_RE,
    NEWSLETTER_RE,
    PROGRAM_RE,
    URGENCY_RE,
)

DecisionVerdict = Literal["DROP", "REVIEW", "KEEP"]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")
_TITLE_MAX_CHARS = 80


def _is_signal_sentence(sentence: str) -> bool:
    """Chỉ coi tín hiệu deadline khi nó không phải cách nói thứ tự câu.

    DEADLINE_RE dùng chung còn nhận diện "thứ hai" để bắt ngày trong tiếng
    Việt, nhưng không nên biến "Câu thứ hai" thành tiêu đề có tín hiệu.
    """
    if re.search(r"(?i)^câu\s+thứ\s+(hai|ba|tư|năm|sáu|bảy|nhất)\b", sentence.strip()):
        return False
    return bool(ACTION_RE.search(sentence) or DEADLINE_RE.search(sentence))

# subtype hệ thống/tự động — DROP tuyệt đối ở Hard Filter (bước 3).
_SYSTEM_SUBTYPES = frozenset(
    {
        "channel_join",
        "channel_leave",
        "channel_topic",
        "channel_purpose",
        "channel_name",
        "channel_archive",
        "channel_unarchive",
    }
)


@dataclass(frozen=True)
class NormalizedMessage:
    """Schema chuẩn hoá nội bộ cho 1 message Slack — mọi rule phía sau CHỈ đọc
    từ đây, không phụ thuộc trực tiếp response Slack API."""

    message_id: str  # "{channel_id}:{ts}"
    channel_id: str
    channel_type: str  # "public_channel" | "private_channel" | "im" | "mpim"
    thread_ts: str | None
    subtype: str | None
    text: str
    author_id: str | None
    is_self: bool
    mentions_current_user: bool
    reactions: tuple[str, ...] = ()
    is_pinned: bool = False  # xem docstring module — chưa nối pins.list
    is_thread_reply_to_self: bool = False  # xem docstring module — chưa nối
    created_at: datetime | None = None
    url: str = ""


@dataclass(frozen=True)
class RuleConfig:
    """Toàn bộ threshold/weight của pipeline — CONFIGURABLE DEFAULT, khớp
    panel RULE_CONFIG trong slack-detail.drawio bước 5."""

    rule_version: str = "slack-rules-v1-draft"

    mentioned_current_user_score: int = 30
    direct_message_score: int = 15
    thread_reply_to_self_score: int = 15
    action_score: int = 25
    deadline_score: int = 25
    urgency_score: int = 20
    pinned_score: int = 10
    # Sơ đồ gộp chung "newsletter/automated: -40" thành 1 dòng trong bảng
    # trọng số — áp 1 lần nếu KHỚP 1 TRONG 2 (không cộng dồn khi khớp cả
    # hai), khác Jira tách riêng newsletter_score/automated_score.
    newsletter_or_automated_score: int = -40
    # Không có trong bảng trọng số bước 5 nhưng bước 4 Common Rules liệt nó
    # là rule dùng chung với Jira — giữ mặc định khớp Jira để nhất quán.
    program_score: int = 20

    keep_threshold: int = 35
    review_threshold: int = 15

    grouping_fuzzy_threshold: float = 0.72


@dataclass(frozen=True)
class HardFilterResult:
    dropped: bool
    reason: str | None = None


@dataclass(frozen=True)
class ScoreResult:
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    """Explainable — reasons là mã rule deterministic, không phải câu văn tự
    do, để trả lời được "vì sao message này thành task"."""

    score: int
    decision: DecisionVerdict
    reasons: tuple[str, ...]
    rule_version: str


def _strip_mentions_and_emoji(text: str) -> str:
    """Bỏ <@U123>, :emoji:, khoảng trắng để phát hiện "chỉ có reaction/mention,
    không có nội dung thật" — khớp điều kiện DROP bước 3."""
    text = re.sub(r"<@[A-Z0-9]+>", "", text)
    text = re.sub(r":[a-z0-9_+-]+:", "", text)
    return text.strip()


def hard_filter(message: NormalizedMessage) -> HardFilterResult:
    """Loại CHẮC CHẮN, không tính điểm — khớp bước 3 Hard Filter."""
    if message.subtype in _SYSTEM_SUBTYPES:
        return HardFilterResult(dropped=True, reason="SYSTEM_SUBTYPE")

    # Đơn giản hoá có chủ đích: sơ đồ mô tả "chỉ giữ bản MỚI NHẤT theo
    # message_ts gốc" cho message_changed (cần state 2 phiên bản để so sánh).
    # Bản này DROP thẳng message_changed thay vì merge — theo dõi
    # TODO(OD-SLACK4) nếu cần giữ bản sửa mới nhất thay vì bỏ hẳn.
    if message.subtype == "message_changed":
        return HardFilterResult(dropped=True, reason="MESSAGE_CHANGED_DROPPED")

    if not _strip_mentions_and_emoji(message.text):
        return HardFilterResult(dropped=True, reason="EMPTY_TEXT")

    return HardFilterResult(dropped=False)


def score_message(message: NormalizedMessage, config: RuleConfig) -> ScoreResult:
    """Chỉ gọi cho message đã QUA Hard Filter. Cộng/trừ theo Slack Rules
    (bước 4, cột cam) + Common Rules (bước 4, cột xanh dương)."""
    text = message.text
    score = 0
    reasons: list[str] = []
    is_newsletter_or_automated = bool(NEWSLETTER_RE.search(text) or AUTOMATED_RE.search(text))

    if message.mentions_current_user:
        score += config.mentioned_current_user_score
        reasons.append("MENTIONED_CURRENT_USER")

    if message.channel_type in ("im", "mpim") and not is_newsletter_or_automated:
        score += config.direct_message_score
        reasons.append("DIRECT_MESSAGE")

    if message.is_thread_reply_to_self:
        score += config.thread_reply_to_self_score
        reasons.append("THREAD_REPLY_TO_SELF")

    if message.is_pinned:
        score += config.pinned_score
        reasons.append("PINNED")

    if ACTION_RE.search(text):
        score += config.action_score
        reasons.append("HAS_ACTION")
    if DEADLINE_RE.search(text):
        score += config.deadline_score
        # INFERRED: Slack không có due_date field cứng như Jira — đây LUÔN là
        # suy luận từ text, không phải field đọc thẳng (xem docstring module).
        reasons.append("HAS_DEADLINE_INFERRED")
    if URGENCY_RE.search(text):
        score += config.urgency_score
        reasons.append("URGENT")
    program_match = PROGRAM_RE.search(text)
    if program_match and program_match.group(0).casefold() != "nhóm":
        score += config.program_score
        reasons.append("PROGRAM_RELEVANCE")

    if is_newsletter_or_automated:
        score += config.newsletter_or_automated_score
        reasons.append("NEWSLETTER_OR_AUTOMATED")

    return ScoreResult(score=score, reasons=tuple(reasons))


def extract_title(message: NormalizedMessage) -> str:
    """SUY RA từ câu đầu khớp action/deadline, else câu đầu tiên — Slack
    không có field tiêu đề sẵn như Jira summary (xem bước 6 Extraction)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(message.text) if s.strip()]
    if not sentences:
        return "(không có nội dung)"
    for sentence in sentences:
        if _is_signal_sentence(sentence):
            return _truncate_title(sentence)
    return _truncate_title(sentences[0])


def _truncate_title(text: str) -> str:
    if len(text) <= _TITLE_MAX_CHARS:
        return text
    return text[:_TITLE_MAX_CHARS].rstrip() + "…"


def extract_deadline_phrase(message: NormalizedMessage) -> str:
    """Câu khớp RIÊNG DEADLINE_RE (khác extract_evidence có thể trả câu chỉ
    khớp ACTION_RE) — dùng làm time_expression cho resolve_due_at(), tránh
    đưa nhầm câu không có ngày giờ vào bộ parse thời gian."""
    for sentence in _SENTENCE_SPLIT_RE.split(message.text):
        sentence = sentence.strip()
        if sentence and DEADLINE_RE.search(sentence) and not sentence.strip().lower().startswith("câu thứ "):
            return sentence
    return ""


def extract_evidence(message: NormalizedMessage) -> str:
    """Câu khớp rule hành động/hạn chót; không câu nào khớp thì fallback lấy
    nguyên text — không paraphrase, không AI."""
    for sentence in _SENTENCE_SPLIT_RE.split(message.text):
        sentence = sentence.strip()
        if sentence and _is_signal_sentence(sentence):
            return sentence
    return message.text


def decide_hard_filter(hard_result: HardFilterResult, config: RuleConfig) -> Decision:
    reasons = (hard_result.reason,) if hard_result.reason else ()
    return Decision(score=0, decision="DROP", reasons=reasons, rule_version=config.rule_version)


def decide_from_score(score_result: ScoreResult, config: RuleConfig) -> Decision:
    if score_result.score >= config.keep_threshold:
        return Decision(
            score=score_result.score, decision="KEEP", reasons=score_result.reasons, rule_version=config.rule_version
        )
    if score_result.score >= config.review_threshold:
        return Decision(
            score=score_result.score,
            decision="REVIEW",
            reasons=score_result.reasons,
            rule_version=config.rule_version,
        )
    reasons = score_result.reasons or ("NO_ACTION_REQUIRED",)
    return Decision(score=score_result.score, decision="DROP", reasons=reasons, rule_version=config.rule_version)


def evaluate_message(message: NormalizedMessage, config: RuleConfig | None = None) -> tuple[Decision, str, str]:
    """Chạy trọn Hard Filter -> Scoring -> Decision cho 1 message đã chuẩn
    hoá. Trả về (Decision, title, evidence) — title/evidence rỗng nếu DROP ở
    Hard Filter (không cần trích dẫn cho message chắc chắn bị loại)."""
    config = config or RuleConfig()

    hard_result = hard_filter(message)
    if hard_result.dropped:
        return decide_hard_filter(hard_result, config), "", ""

    score_result = score_message(message, config)
    decision = decide_from_score(score_result, config)
    if decision.decision == "DROP":
        return decision, "", ""
    return decision, extract_title(message), extract_evidence(message)
