"""Rule engine 100% rule-based cho Jira — KHÔNG gọi AI/LLM ở bất kỳ hàm nào.

Bám sát docs/projects/engineering/jira-detail.drawio (tab "Jira pipeline"):
Normalization -> Hard Filter -> Jira Rules + Common Rules -> Scoring ->
Extraction -> Decision. Mọi threshold/weight nằm trong RuleConfig — đổi được
qua config, không hard-code rải rác trong logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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

DueBucket = Literal["OVERDUE", "DUE_TODAY", "DUE_TOMORROW", "DUE_SOON", "FUTURE", "NO_DEADLINE"]
DecisionVerdict = Literal["DROP", "REVIEW", "KEEP"]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")


@dataclass(frozen=True)
class CurrentUserContext:
    """Người đang đồng bộ — dùng account_id (KHÔNG dùng display name/email)
    để so khớp assigned_to_current_user, và timezone để quy đổi due_date."""

    account_id: str
    timezone: str


@dataclass(frozen=True)
class NormalizedIssue:
    """Schema chuẩn hoá nội bộ cho 1 issue Jira — mọi rule phía sau CHỈ đọc
    từ đây, không phụ thuộc trực tiếp response Jira API."""

    issue_id: str
    issue_key: str
    project: str
    title: str
    description: str
    assignee_account_id: str | None
    status: str
    status_category: str  # "To Do" | "In Progress" | "Done" — chuẩn Jira
    resolution: str | None
    priority: str | None
    issue_type: str
    due_date: datetime | None  # đã quy đổi theo timezone user
    created_at: datetime
    updated_at: datetime
    url: str


@dataclass(frozen=True)
class RuleConfig:
    """Toàn bộ threshold/weight của pipeline — CONFIGURABLE DEFAULT, không
    phải giá trị tuyệt đối. Giá trị mặc định khớp panel RULE_CONFIG trong
    jira-detail.drawio."""

    rule_version: str = "jira-rules-v1"

    action_score: int = 25
    deadline_score: int = 25
    urgency_score: int = 25
    program_score: int = 20
    newsletter_score: int = -40
    automated_score: int = -30
    resolution_not_done_penalty: int = -15

    assigned_to_current_user_score: int = 15
    priority_scores: dict[str, int] = field(
        default_factory=lambda: {"Highest": 15, "High": 10, "Medium": 5, "Low": 0, "Lowest": 0}
    )
    due_bucket_scores: dict[str, int] = field(
        default_factory=lambda: {
            "OVERDUE": 15,
            "DUE_TODAY": 15,
            "DUE_TOMORROW": 12,
            "DUE_SOON": 10,
            "FUTURE": 0,
            "NO_DEADLINE": 0,
        }
    )
    due_soon_days: int = 5

    keep_threshold: int = 35
    review_threshold: int = 15

    grouping_fuzzy_threshold: float = 0.72
    overlap_window_minutes: int = 10


@dataclass(frozen=True)
class HardFilterResult:
    """dropped=True nghĩa là loại CHẮC CHẮN — không qua Scoring nữa.
    resolution_flagged để Scoring biết mà trừ điểm nhẹ (không tự DROP)."""

    dropped: bool
    reason: str | None = None
    resolution_flagged: bool = False


@dataclass(frozen=True)
class ScoreResult:
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    """Kết quả cuối, explainable — reasons là mã rule deterministic, không
    phải câu văn tự do, để trả lời được "vì sao issue này thành task"."""

    score: int
    decision: DecisionVerdict
    reasons: tuple[str, ...]
    rule_version: str


def _mentions_user(issue: NormalizedIssue, user: CurrentUserContext) -> bool:
    """Issue nhắc đích danh người dùng trong tiêu đề/mô tả.

    Jira nhúng mention dạng `[~accountid:xxx]` trong text; đối chiếu thẳng
    accountId chứ không dò tên hiển thị (tên trùng nhau là chuyện thường).
    """
    if not user.account_id:
        return False
    haystack = f"{issue.title} {issue.description}".lower()
    return user.account_id.lower() in haystack


def hard_filter(issue: NormalizedIssue, user: CurrentUserContext | None = None) -> HardFilterResult:
    """Loại CHẮC CHẮN, không tính điểm. status_category=Done hoặc issue sinh
    tự động không hành động thì loại thẳng; resolution có giá trị nhưng chưa
    Done thì KHÔNG tự loại — chỉ đánh dấu cho Scoring xử lý tiếp.

    `user` là tuỳ chọn để không phá caller cũ (và test) vốn chỉ truyền issue;
    thiếu nó thì luật "không phải việc của tôi" không chạy.
    """
    if issue.status_category == "Done":
        return HardFilterResult(dropped=True, reason="STATUS_DONE")

    # Tương đương `not_addressed` của mail: issue giao cho NGƯỜI KHÁC không
    # phải việc của người dùng, dù có hạn chót gấp tới đâu. Issue chưa ai nhận
    # cũng loại — quyết định của chủ sở hữu sản phẩm 2026-08-21; muốn giữ lại
    # nhóm đó thì nới đúng nhánh `assignee_account_id is None` ở đây.
    # Mention đích danh vẫn được giữ: người khác làm nhưng cần mình trả lời.
    if user is not None and user.account_id:
        assigned_to_me = bool(issue.assignee_account_id) and issue.assignee_account_id == user.account_id
        if not assigned_to_me and not _mentions_user(issue, user):
            return HardFilterResult(dropped=True, reason="NOT_ASSIGNED_TO_ME")

    text = f"{issue.title} {issue.description}"
    has_action_or_deadline = bool(ACTION_RE.search(text) or DEADLINE_RE.search(text))
    if AUTOMATED_RE.search(text) and not has_action_or_deadline:
        return HardFilterResult(dropped=True, reason="SYSTEM_GENERATED")

    resolution_flagged = bool(issue.resolution) and issue.status_category != "Done"
    return HardFilterResult(dropped=False, resolution_flagged=resolution_flagged)


def compute_due_bucket(due_date: datetime | None, now: datetime, config: RuleConfig) -> DueBucket:
    """Suy ra nhóm hạn chót từ due_date đã quy đổi timezone — không chỉ check
    "có hạn hay không"."""
    if due_date is None:
        return "NO_DEADLINE"
    delta_days = (due_date.date() - now.date()).days
    if delta_days < 0:
        return "OVERDUE"
    if delta_days == 0:
        return "DUE_TODAY"
    if delta_days == 1:
        return "DUE_TOMORROW"
    if delta_days <= config.due_soon_days:
        return "DUE_SOON"
    return "FUTURE"


def score_issue(
    issue: NormalizedIssue,
    due_bucket: DueBucket,
    user: CurrentUserContext,
    resolution_flagged: bool,
    config: RuleConfig,
) -> ScoreResult:
    """Chỉ gọi cho issue đã QUA Hard Filter. Cộng/trừ theo Common Rules (từ
    khoá dùng chung, tái dùng đúng regex đã duyệt ở filter_classify.py) +
    Jira Rules (assignee/priority/due bucket/resolution)."""
    text = f"{issue.title} {issue.description}"
    score = 0
    reasons: list[str] = []

    if ACTION_RE.search(text):
        score += config.action_score
        reasons.append("HAS_ACTION")
    if DEADLINE_RE.search(text):
        score += config.deadline_score
        reasons.append("HAS_DEADLINE")
    if URGENCY_RE.search(text):
        score += config.urgency_score
        reasons.append("URGENT")
    if PROGRAM_RE.search(text):
        score += config.program_score
        reasons.append("PROGRAM_RELEVANCE")
    if NEWSLETTER_RE.search(text):
        score += config.newsletter_score
        reasons.append("NEWSLETTER")
    if AUTOMATED_RE.search(text):
        score += config.automated_score
        reasons.append("SYSTEM_GENERATED_SIGNAL")

    if issue.assignee_account_id and issue.assignee_account_id == user.account_id:
        score += config.assigned_to_current_user_score
        reasons.append("ASSIGNED_TO_CURRENT_USER")

    if issue.priority:
        score += config.priority_scores.get(issue.priority, 0)
        if issue.priority in ("Highest", "High"):
            reasons.append("HIGH_PRIORITY")

    score += config.due_bucket_scores.get(due_bucket, 0)
    if due_bucket in ("OVERDUE", "DUE_TODAY", "DUE_TOMORROW", "DUE_SOON"):
        reasons.append(due_bucket)

    if resolution_flagged:
        score += config.resolution_not_done_penalty
        reasons.append("HAS_RESOLUTION_NOT_DONE")

    return ScoreResult(score=score, reasons=tuple(reasons))


def extract_evidence(issue: NormalizedIssue) -> str:
    """Câu đầu tiên trong description khớp rule hành động/hạn chót; không câu
    nào khớp thì fallback lấy title — không paraphrase, không AI."""
    for sentence in _SENTENCE_SPLIT_RE.split(issue.description or ""):
        sentence = sentence.strip()
        if sentence and (ACTION_RE.search(sentence) or DEADLINE_RE.search(sentence)):
            return sentence
    return issue.title


def decide_hard_filter(hard_result: HardFilterResult, config: RuleConfig) -> Decision:
    """Gọi khi hard_filter().dropped=True — DROP tuyệt đối, không qua Scoring."""
    reasons = (hard_result.reason,) if hard_result.reason else ()
    return Decision(score=0, decision="DROP", reasons=reasons, rule_version=config.rule_version)


def decide_from_score(score_result: ScoreResult, config: RuleConfig) -> Decision:
    """DROP/REVIEW/KEEP theo threshold cấu hình được — score dưới review_threshold
    coi là NO_ACTION_REQUIRED nếu không có reason nào khác trigger."""
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


def evaluate_issue(
    issue: NormalizedIssue, user: CurrentUserContext, now: datetime, config: RuleConfig | None = None
) -> tuple[Decision, str]:
    """Chạy trọn Hard Filter -> Scoring -> Decision cho 1 issue đã chuẩn hoá.
    Trả về (Decision, evidence) — evidence rỗng nếu DROP ở Hard Filter (không
    cần trích dẫn cho issue chắc chắn bị loại)."""
    config = config or RuleConfig()

    hard_result = hard_filter(issue, user)
    if hard_result.dropped:
        return decide_hard_filter(hard_result, config), ""

    due_bucket = compute_due_bucket(issue.due_date, now, config)
    score_result = score_issue(issue, due_bucket, user, hard_result.resolution_flagged, config)
    decision = decide_from_score(score_result, config)
    evidence = extract_evidence(issue) if decision.decision != "DROP" else ""
    return decision, evidence
