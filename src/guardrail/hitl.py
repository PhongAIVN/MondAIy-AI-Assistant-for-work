"""Human-in-the-loop routing, dangerous-tool policy, and tamper-evident audit.

This module only decides whether an action may proceed. It never executes an
external side effect. The executor must require an ``approved`` decision.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.guardrail.policy import ToolLevel, classify_tool


class HITLRoute(str, Enum):
    AUTO_SEND = "auto_send"
    DRAFT_ONLY = "draft_only"
    QUEUE_REVIEW = "queue_review"
    ESCALATE = "escalate"


class ReviewerDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class HITLActionDecision(BaseModel):
    request_id: str
    action: str
    confidence: float = Field(ge=0.0, le=1.0)
    route: HITLRoute
    reviewer_decision: ReviewerDecision
    hitl_required: bool
    high_risk: bool
    reason: str
    audit_layer: str = "hitl"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


HIGH_RISK_ACTIONS = frozenset(
    {
        "send_email",
        "send_message",
        "post_message",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "delete_external_action",
        "delete_data",
        "change_permissions",
        "publish_external",
        "execute_code",
        "make_payment",
        "issue_refund",
        "invite_user",
        "revoke_access",
        "create_productivity_item",
    }
)


def is_high_risk_action(action: str) -> bool:
    """Match exact names and common provider-prefixed tool names."""
    normalized = action.strip().lower()
    return (
        classify_tool(normalized) >= ToolLevel.EXTERNAL_WRITE
        or normalized in HIGH_RISK_ACTIONS
        or any(normalized.endswith("." + name) or normalized.endswith("_" + name) for name in HIGH_RISK_ACTIONS)
    )


class ConfidenceRouter:
    """Route an action without allowing confidence to bypass dangerous tools."""

    def route(
        self,
        confidence: float,
        action: str,
        *,
        request_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> HITLActionDecision:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        request_id = request_id or str(uuid.uuid4())
        high_risk = False if action == "ordinary_action" else is_high_risk_action(action)
        # ``ordinary_action`` is the neutral routing sentinel used by callers
        # that have already classified the action separately. Unknown real
        # tool names still fail closed in policy.classify_tool().
        level = ToolLevel.INTERNAL_COMPUTATION if action == "ordinary_action" else classify_tool(action)
        if high_risk:
            return HITLActionDecision(
                request_id=request_id,
                action=action,
                confidence=confidence,
                route=HITLRoute.ESCALATE,
                reviewer_decision=ReviewerDecision.PENDING,
                hitl_required=True,
                high_risk=True,
                reason="high_risk_action_always_requires_human_approval",
            )
        if level == ToolLevel.DRAFT:
            return HITLActionDecision(
                request_id=request_id,
                action=action,
                confidence=confidence,
                route=HITLRoute.DRAFT_ONLY,
                reviewer_decision=ReviewerDecision.PENDING,
                hitl_required=False,
                high_risk=False,
                reason="draft_only_preview_no_external_side_effect",
            )
        if confidence >= 0.90:
            return HITLActionDecision(
                request_id=request_id,
                action=action,
                confidence=confidence,
                route=HITLRoute.AUTO_SEND,
                reviewer_decision=ReviewerDecision.APPROVED,
                hitl_required=False,
                high_risk=False,
                reason="high_confidence_ordinary_action",
            )
        if confidence >= 0.70:
            return HITLActionDecision(
                request_id=request_id,
                action=action,
                confidence=confidence,
                route=HITLRoute.QUEUE_REVIEW,
                reviewer_decision=ReviewerDecision.PENDING,
                hitl_required=True,
                high_risk=False,
                reason="medium_confidence_requires_review",
            )
        return HITLActionDecision(
            request_id=request_id,
            action=action,
            confidence=confidence,
            route=HITLRoute.ESCALATE,
            reviewer_decision=ReviewerDecision.PENDING,
            hitl_required=True,
            high_risk=False,
            reason="low_confidence_requires_escalation",
        )


@dataclass(frozen=True)
class HITLDecisionPoint:
    name: str
    trigger: str
    hitl_model: str
    reviewer_context: str
    approve: str
    reject: str
    timeout: str


hitl_decision_points: tuple[HITLDecisionPoint, ...] = (
    HITLDecisionPoint(
        name="dangerous_tool_call",
        trigger="A tool call is in HIGH_RISK_ACTIONS, regardless of confidence.",
        hitl_model="security_reviewer",
        reviewer_context="request_id, tool name, redacted arguments, evidence IDs, permission state, and a before/after diff",
        approve="mark approved and allow exactly this idempotency-keyed call",
        reject="mark rejected and do not execute; return a safe explanation",
        timeout="deny by default and escalate to an operator",
    ),
    HITLDecisionPoint(
        name="medium_confidence_action",
        trigger="An ordinary action has confidence from 0.70 up to but not including 0.90.",
        hitl_model="task_reviewer",
        reviewer_context="proposed intent, action payload, evidence citations, confidence, and change diff",
        approve="mark approved and hand off to the constrained executor",
        reject="discard the draft and preserve the rejection audit event",
        timeout="move to escalate; never auto-send after timeout",
    ),
    HITLDecisionPoint(
        name="grounding_or_permission_failure",
        trigger="Citation fails, evidence conflicts, or permission changes before render/execute.",
        hitl_model="trust_safety_reviewer",
        reviewer_context="request_id, failed layer, evidence IDs, conflict variants, and redacted diagnostic",
        approve="only after a fresh permission/grounding check passes",
        reject="abstain, revoke the candidate action, and hide unsupported claims",
        timeout="abstain and escalate; no render of the unsupported action",
    ),
)


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    event_type: str
    layer: str
    reviewer_decision: str
    action: str | None
    details: dict[str, Any]
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    previous_hash: str = ""
    event_hash: str = ""


class HITLAuditLog:
    """In-process audit sink with a hash chain.

    Production should persist these events in the canonical audit store. The
    chain makes accidental mutation or deletion detectable in the meantime.
    ``details`` must contain metadata only; raw prompt/source text is refused.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._last_hash = "GENESIS"
        self._lock = threading.Lock()

    @staticmethod
    def _safe_details(details: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"prompt", "raw", "raw_text", "email_body", "content", "source_text"}
        if forbidden.intersection(details):
            raise ValueError("HITL audit cannot store raw prompt or source content")
        return json.loads(json.dumps(details, default=str))

    def record(
        self,
        *,
        request_id: str,
        event_type: str,
        layer: str,
        reviewer_decision: str,
        action: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        with self._lock:
            safe = self._safe_details(details or {})
            body = {
                "request_id": request_id,
                "event_type": event_type,
                "layer": layer,
                "reviewer_decision": reviewer_decision,
                "action": action,
                "details": safe,
                "at": datetime.now(UTC).isoformat(),
                "previous_hash": self._last_hash,
            }
            event_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            event = AuditEvent(**body, event_hash=event_hash)
            self._events.append(event)
            self._last_hash = event_hash
            return event

    def verify_integrity(self) -> bool:
        previous = "GENESIS"
        for event in self._events:
            body = {
                "request_id": event.request_id,
                "event_type": event.event_type,
                "layer": event.layer,
                "reviewer_decision": event.reviewer_decision,
                "action": event.action,
                "details": event.details,
                "at": event.at,
                "previous_hash": previous,
            }
            expected = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
            if event.previous_hash != previous or event.event_hash != expected:
                return False
            previous = event.event_hash
        return True

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


def apply_reviewer_decision(
    decision: HITLActionDecision,
    reviewer_decision: ReviewerDecision,
    *,
    audit: HITLAuditLog,
    reviewer_id: str,
    context_or_diff: dict[str, Any] | None = None,
) -> HITLActionDecision:
    if decision.route == HITLRoute.AUTO_SEND and reviewer_decision != ReviewerDecision.APPROVED:
        raise ValueError("auto_send decisions do not accept a reviewer override")
    if reviewer_decision == ReviewerDecision.TIMED_OUT:
        route = HITLRoute.ESCALATE
    else:
        route = decision.route
    updated = decision.model_copy(update={"reviewer_decision": reviewer_decision, "route": route})
    audit.record(
        request_id=decision.request_id,
        event_type="hitl_decision",
        layer=decision.audit_layer,
        reviewer_decision=reviewer_decision.value,
        action=decision.action,
        details={"reviewer_id": reviewer_id, "reason": decision.reason, "context_or_diff": context_or_diff or {}},
    )
    return updated


def route_tool_call(
    tool_name: str,
    *,
    confidence: float,
    request_id: str | None = None,
    audit: HITLAuditLog | None = None,
) -> HITLActionDecision:
    """Single entry point to call before any tool executor."""
    decision = ConfidenceRouter().route(confidence, tool_name, request_id=request_id)
    if audit is not None:
        audit.record(
            request_id=decision.request_id,
            event_type="tool_call_routed",
            layer="hitl",
            reviewer_decision=decision.reviewer_decision.value,
            action=tool_name,
            details={"route": decision.route.value, "high_risk": decision.high_risk, "confidence": confidence},
        )
    return decision
