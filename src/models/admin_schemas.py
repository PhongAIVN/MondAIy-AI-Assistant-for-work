"""Response models dedicated to the privacy-preserving admin API."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from src.models.schemas import CamelModel
from src.services.program_cohorts import normalize_program_cohort_slug

AdminRole = Literal["participant", "mentor", "admin"]


class AdminRoleBreakdown(CamelModel):
    participant: int = 0
    mentor: int = 0
    admin: int = 0


class AdminSourceHealth(CamelModel):
    provider: str
    total: int
    connected: int
    syncing: int
    failed: int
    last_synced_at: datetime | None = None


class AdminOverviewResponse(CamelModel):
    total_users: int
    active_users: int
    inactive_users: int
    roles: AdminRoleBreakdown
    total_connections: int
    failed_connections: int
    source_health_percent: float
    runs_total: int
    runs_succeeded: int
    runs_failed: int
    runs_running: int
    briefs_generated: int
    tasks_proposed: int
    tasks_confirmed: int
    open_conflicts: int
    feedback_total: int
    feedback_helpful: int
    window_days: int
    generated_at: datetime


class AdminUserRow(CamelModel):
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_synced_at: datetime | None = None
    connection_count: int = 0
    run_count: int = 0
    program_access_level: Literal["A", "B", "C"] = "C"
    program_cohort_slug: str | None = None


class AdminUserListResponse(CamelModel):
    items: list[AdminUserRow]
    total: int
    limit: int
    offset: int


class AdminUserUpdateRequest(CamelModel):
    role: AdminRole | None = None
    is_active: bool | None = None
    program_cohort_slug: str | None = Field(default=None, max_length=64)

    @field_validator("program_cohort_slug")
    @classmethod
    def validate_program_cohort_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return ""
        return normalize_program_cohort_slug(value)


class AdminProgramAccessUpdateRequest(CamelModel):
    level: Literal["A", "B", "C"]


class AdminConnectionRow(CamelModel):
    id: int
    user_id: str
    user_email: str = ""
    provider: str
    status: str
    initial_sync_completed: bool
    connected_at: datetime
    last_synced_at: datetime | None = None
    email_count: int = 0
    last_error: str | None = None


class AdminSourcesResponse(CamelModel):
    providers: list[AdminSourceHealth]
    connections: list[AdminConnectionRow]


class AdminSourceScopeRow(CamelModel):
    id: int
    provider: str
    external_id: str
    name: str | None = None
    tier: str


class AdminSourceScopeGrantRequest(CamelModel):
    scope_ids: list[int] = Field(default_factory=list)


class AdminSourceScopeGrantResponse(CamelModel):
    user_id: str
    scope_ids: list[int]


class AdminRunRow(CamelModel):
    id: int
    user_id: str
    status: str
    created_at: datetime
    sources_count: int
    error_message: str | None = None


class AdminRunListResponse(CamelModel):
    items: list[AdminRunRow]
    total: int


class AdminAuditRow(CamelModel):
    id: int
    action: str
    object_type: str
    object_id: str
    actor_type: str
    actor_id: str | None = None
    version_label: str | None = None
    details: dict | None = None
    created_at: datetime


class AdminAuditListResponse(CamelModel):
    items: list[AdminAuditRow]
    total: int


class AdminTelemetryCount(CamelModel):
    name: str
    count: int
    avg_duration_ms: int | None = None


class AdminFeedbackBreakdown(CamelModel):
    verdict: str
    count: int


class AdminTelemetryResponse(CamelModel):
    window_days: int
    events: list[AdminTelemetryCount]
    feedback: list[AdminFeedbackBreakdown]


class AdminAppRatingRow(CamelModel):
    id: int
    rating: int
    feedback: str
    trigger: str
    created_at: datetime


class AdminAppRatingSummary(CamelModel):
    total: int
    average_rating: float | None = None
    distribution: list[AdminFeedbackBreakdown]
    items: list[AdminAppRatingRow]
