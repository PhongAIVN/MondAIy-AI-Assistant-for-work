"""Gom model để `Base.metadata` thấy đủ bảng khi tạo schema."""

from src.models.connection import Connection
from src.models.conversation import Conversation, ConversationMessage
from src.models.document_read import DocumentReadCache, DocumentReadQuota
from src.models.evidence import (
    Chunk,
    ChunkItem,
    SourceItem,
    SourceItemVersion,
    SourceScope,
)
from src.models.learning import (
    AssistantContextRef,
    LearningAuditEvent,
    LearningCandidate,
    LearningConsent,
    LearningEvidence,
    LearningReviewCursor,
    LearningSignal,
)
from src.models.llm_usage import LLMUsageEvent
from src.models.program_information import (
    ProgramInformationItem,
    ProgramInformationRequest,
    ProgramInformationVersion,
)
from src.models.program_schedule_template import ProgramScheduleTemplate
from src.models.push_subscription import PushSubscription
from src.models.source_scope_access import SourceScopeAccess
from src.models.telemetry import AuditEvent, TelemetryEvent
from src.models.user import User
from src.models.user_memory import UserMemory, UserMemoryEvidence, UserProfileMemory
from src.models.worker_heartbeat import WorkerHeartbeat

__all__ = [
    "AuditEvent",
    "Chunk",
    "ChunkItem",
    "AssistantContextRef",
    "Connection",
    "Conversation",
    "ConversationMessage",
    "DocumentReadCache",
    "DocumentReadQuota",
    "LearningAuditEvent",
    "LearningCandidate",
    "LearningConsent",
    "LearningEvidence",
    "LearningReviewCursor",
    "LearningSignal",
    "LLMUsageEvent",
    "PushSubscription",
    "ProgramInformationItem",
    "ProgramInformationRequest",
    "ProgramInformationVersion",
    "ProgramScheduleTemplate",
    "SourceItem",
    "SourceItemVersion",
    "SourceScope",
    "SourceScopeAccess",
    "TelemetryEvent",
    "User",
    "UserMemory",
    "UserMemoryEvidence",
    "UserProfileMemory",
    "WorkerHeartbeat",
]
