"""Deterministic safety boundaries for retrieval, LLM calls, and rendering.

The guardrail deliberately does not ask an LLM to police itself.  It produces
small, serializable decisions that callers can log and test.
"""

from src.guardrail.attachment_safety import (
    ALLOWED_MIME_TYPES,
    AttachmentRejectedError,
    assert_safe_to_download,
    assert_uncompressed_size_ok,
    configure_pillow_pixel_cap,
    ensure_openpyxl_defusedxml_active,
    run_with_timeout,
    validate_image_bytes,
)
from src.guardrail.hitl import (
    HIGH_RISK_ACTIONS,
    ConfidenceRouter,
    HITLActionDecision,
    HITLAuditLog,
    HITLRoute,
    ReviewerDecision,
    apply_reviewer_decision,
    hitl_decision_points,
    route_tool_call,
)
from src.guardrail.input import (
    Evidence,
    InputDecision,
    build_context_pack,
    classify_query,
    sanitize_untrusted_text,
    scan_prompt_injection,
)
from src.guardrail.monitoring import GuardrailMetrics, MetricsCollector, MonitoringAlert
from src.guardrail.output import GroundingResult, ground_candidate
from src.guardrail.pii import PiiRedactor
from src.guardrail.policy import (
    TOOL_POLICY,
    ToolDecision,
    ToolLevel,
    classify_tool,
    confidence_band,
    evaluate_tool,
    is_tool_allowed,
)

__all__ = [
    "ALLOWED_MIME_TYPES",
    "AttachmentRejectedError",
    "assert_safe_to_download",
    "assert_uncompressed_size_ok",
    "configure_pillow_pixel_cap",
    "ensure_openpyxl_defusedxml_active",
    "run_with_timeout",
    "validate_image_bytes",
    "Evidence",
    "InputDecision",
    "GroundingResult",
    "PiiRedactor",
    "TOOL_POLICY",
    "classify_query",
    "build_context_pack",
    "sanitize_untrusted_text",
    "scan_prompt_injection",
    "ground_candidate",
    "is_tool_allowed",
    "HIGH_RISK_ACTIONS",
    "ConfidenceRouter",
    "HITLAuditLog",
    "HITLActionDecision",
    "HITLRoute",
    "ReviewerDecision",
    "apply_reviewer_decision",
    "hitl_decision_points",
    "route_tool_call",
    "GuardrailMetrics",
    "MetricsCollector",
    "MonitoringAlert",
    "ToolDecision",
    "ToolLevel",
    "classify_tool",
    "confidence_band",
    "evaluate_tool",
]
