"""Impact-based tool policy.

Tools are classified by side-effect impact, never by connector/provider. This
module is intentionally deterministic and must run before a tool executor.
"""

from __future__ import annotations

from enum import Enum, IntEnum

from pydantic import BaseModel, Field


class ToolLevel(IntEnum):
    SAFE_READ = 0
    INTERNAL_COMPUTATION = 1
    DRAFT = 2
    EXTERNAL_WRITE = 3
    DESTRUCTIVE = 4


class ToolDecision(str, Enum):
    ALLOW = "allow"
    DRAFT_ONLY = "draft_only"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_DOUBLE_CONFIRMATION = "require_double_confirmation"
    BLOCK = "block"
    ABSTAIN = "abstain"
    UNCERTAIN = "uncertain"
    SHOW_WARNING = "show_warning"


class ConfidenceBand(str, Enum):
    HIGH = "high"  # >= .95
    MEDIUM = "medium"  # .85 - < .95
    LOW = "low"  # .70 - < .85
    VERY_LOW = "very_low"  # .50 - < .70
    UNKNOWN = "unknown"  # < .50


READ_ONLY_TOOLS = frozenset(
    {
        "search_evidence",
        "retrieve_context",
        "retrieve_memory",
        "search_calendar",
        "search_jira",
        "search_discord",
        "search_gmail",
        "search_vlearn",
        "open_document",
        "open_message",
        "semantic_search",
        "fetch_attachment_metadata",
        "recall_memories",
        "get_user_context",
        "get_program_context",
        "get_meeting_transcript",
        "get_upcoming_actions",
        "gmail_search_emails",
        "gmail_deadline_sweep",
        "gmail_read_email",
        # Gmail bridge chỉ đọc qua AnythingLLM, không đổi gì mailbox; đã có trong
        # core_nodes._READ_ONLY_TOOLS và được planner chủ động chọn nên thiếu ở
        # đây là bị chặn "cần approval" cho mọi user.
        "gmail_bridge_search",
        "gmail_bridge_read_thread",
        "jira_search_issues",
        "calendar_search_events",
        "google_sheets_task_proposals",
        "google_docs_task_proposals",
        "list_tasks",
        # Các tool này chỉ đọc dữ liệu trong phạm vi đã cấp hoặc nguồn công khai;
        # không tạo, sửa hay xoá dữ liệu nghiệp vụ.
        "plan_my_day",
        "generate_planner_plan",
        "program_information_search",
        "drive_search_files",
        "web_search",
        "discord_search_program",
        "discord_search_my_messages",
        "discord_get_my_activity",
        # discord_list_announcements và program_schedule đã là tool chỉ đọc trong
        # _READ_ONLY_TOOLS/system prompt của example_node.py, nhưng thiếu ở đây
        # khiến classify_tool() fall-through về EXTERNAL_WRITE và action_node
        # chặn thành "cần approval" cho mọi user, kể cả access level hợp lệ. Hai
        # allowlist (example_node._READ_ONLY_TOOLS và policy.READ_ONLY_TOOLS) vẫn
        # đang là hai nguồn song song lệch nhau — không tự gộp kiến trúc trong
        # phạm vi fix này, chỉ bổ sung data đang thiếu.
        "discord_list_announcements",
        "program_schedule",
        "current_datetime",
        "relative_time",
    }
)

INTERNAL_COMPUTATION_TOOLS = frozenset(
    {
        "summarize",
        "cluster",
        "conflict_detector",
        "ranking",
        "deadline_extractor",
        "rerank",
        "citation_matcher",
        "embedding",
        "memory",
        "extract_batch",
        "calculate",
        # Hai tool suggestion chỉ chuẩn hoá input của model thành JSON xem trước;
        # không đọc DB, gọi nguồn ngoài hay tạo dữ liệu bền vững.
        "suggest_tasks",
        "suggest_calendar_events",
    }
)

DRAFT_TOOLS = frozenset(
    {
        "draft_email",
        "draft_calendar_event",
        "draft_slack_message",
        "draft_jira_comment",
        "draft_todo",
        "draft_reminder",
        "draft_reply",
        "create_action_draft",
        "draft_task",
        "configure_planner_workday",
        "create_productivity_item",
    }
)

EXTERNAL_WRITE_TOOLS = frozenset(
    {
        "send_email",
        "send_message",
        "send_discord_message",
        "create_calendar_event",
        "update_calendar_event",
        "create_jira_issue",
        "comment_jira",
        "create_task",
        "archive_email",
        "mark_done",
        "publish_external",
        "invite_user",
        "create_productivity_item",
    }
)

DESTRUCTIVE_TOOLS = frozenset(
    {
        "delete_calendar",
        "delete_calendar_event",
        "delete_jira",
        "delete_email",
        "delete_external_action",
        "close_ticket",
        "close_issue",
        "remove_user",
        "revoke_permission",
        "delete_data",
        "change_permissions",
        "execute_code",
        "make_payment",
        "issue_refund",
    }
)

HIGH_RISK_DOMAINS = frozenset({"bank", "payment", "hr", "grading", "medical"})


def _normalized(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def classify_tool(tool_name: str) -> ToolLevel:
    """Classify by impact; unknown tools fail closed at Level 3."""
    name = _normalized(tool_name)
    if name in READ_ONLY_TOOLS:
        return ToolLevel.SAFE_READ
    if name in INTERNAL_COMPUTATION_TOOLS:
        return ToolLevel.INTERNAL_COMPUTATION
    if name in DRAFT_TOOLS:
        return ToolLevel.DRAFT
    if name in DESTRUCTIVE_TOOLS:
        return ToolLevel.DESTRUCTIVE
    if name in EXTERNAL_WRITE_TOOLS:
        return ToolLevel.EXTERNAL_WRITE
    return ToolLevel.EXTERNAL_WRITE


def confidence_band(confidence: float | None) -> ConfidenceBand:
    if confidence is None or confidence < 0.50:
        return ConfidenceBand.UNKNOWN
    if confidence >= 0.95:
        return ConfidenceBand.HIGH
    if confidence >= 0.85:
        return ConfidenceBand.MEDIUM
    if confidence >= 0.70:
        return ConfidenceBand.LOW
    return ConfidenceBand.VERY_LOW


class PolicyEvaluation(BaseModel):
    tool_name: str
    level: ToolLevel
    decision: ToolDecision
    confidence_band: ConfidenceBand
    trusted: bool = False
    approval_required: bool = False
    double_confirmation_required: bool = False
    reasons: list[str] = Field(default_factory=list)


def evaluate_tool(
    tool_name: str,
    *,
    confidence: float | None = None,
    permission_pass: bool = True,
    scope_pass: bool = True,
    evidence_present: bool = True,
    citation_complete: bool = True,
    conflict: bool = False,
    coverage: str = "complete",
    domain: str | None = None,
) -> PolicyEvaluation:
    """Evaluate tool impact and evidence gates before execution/rendering."""
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    level = classify_tool(tool_name)
    band = confidence_band(confidence)
    reasons: list[str] = []
    if not permission_pass:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.BLOCK,
            confidence_band=band,
            reasons=["permission_failed"],
        )
    if not scope_pass:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.BLOCK,
            confidence_band=band,
            reasons=["scope_failed"],
        )
    if not citation_complete:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.BLOCK,
            confidence_band=band,
            reasons=["citation_failed"],
        )
    if not evidence_present:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.ABSTAIN,
            confidence_band=band,
            reasons=["evidence_missing"],
        )
    if conflict:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.UNCERTAIN,
            confidence_band=band,
            reasons=["conflict"],
        )
    if domain and _normalized(domain) in HIGH_RISK_DOMAINS:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=ToolLevel.DESTRUCTIVE,
            decision=ToolDecision.REQUIRE_DOUBLE_CONFIRMATION,
            confidence_band=band,
            approval_required=True,
            double_confirmation_required=True,
            reasons=["high_risk_domain_never_autonomous"],
        )
    if level == ToolLevel.SAFE_READ or level == ToolLevel.INTERNAL_COMPUTATION:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.SHOW_WARNING if coverage == "partial" else ToolDecision.ALLOW,
            confidence_band=band,
            trusted=bool(confidence is not None and confidence >= 0.90),
            reasons=["coverage_partial"] if coverage == "partial" else reasons,
        )
    if level == ToolLevel.DRAFT:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.DRAFT_ONLY,
            confidence_band=band,
            reasons=["preview_only_no_external_side_effect"],
        )
    if coverage == "partial":
        reasons.append("coverage_partial")
    if level == ToolLevel.DESTRUCTIVE:
        reasons.append("destructive_action")
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.REQUIRE_DOUBLE_CONFIRMATION,
            confidence_band=band,
            approval_required=True,
            double_confirmation_required=True,
            reasons=reasons,
        )
    if reasons:
        return PolicyEvaluation(
            tool_name=tool_name,
            level=level,
            decision=ToolDecision.REQUIRE_APPROVAL,
            confidence_band=band,
            approval_required=True,
            reasons=reasons,
        )
    # External writes never become autonomous, even at confidence 1.0.
    return PolicyEvaluation(
        tool_name=tool_name,
        level=level,
        decision=ToolDecision.REQUIRE_APPROVAL,
        confidence_band=band,
        approval_required=True,
        trusted=bool(confidence is not None and confidence >= 0.90),
        reasons=["external_write_always_requires_approval"],
    )


# Backward-compatible read/draft/write allowlist used by existing callers.
TOOL_POLICY = {
    "read": READ_ONLY_TOOLS,
    "compute": INTERNAL_COMPUTATION_TOOLS,
    "draft": DRAFT_TOOLS,
    "write": frozenset(),
}


def is_tool_allowed(name: str, *, phase: str = "read") -> bool:
    """Only safe read/compute tools are directly executable by default."""
    return _normalized(name) in TOOL_POLICY.get(phase, frozenset())
