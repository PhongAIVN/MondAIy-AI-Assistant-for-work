from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from src.services.language import DEFAULT_LANGUAGE, SupportedLanguage


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="Tin nhắn từ user")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Phản hồi từ agent")
    analysis: str = Field(default="", description="Phân tích nội bộ")
    sources: list[dict] = Field(default_factory=list, description="Nguồn kèm link đã dùng để trả lời")


class CamelModel(BaseModel):
    """Request/response camelCase để khớp convention JSON phía extension
    (types/index.ts toàn camelCase), field Python vẫn snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class VisionActionRequest(CamelModel):
    image_data_url: str = Field(..., min_length=32, max_length=12_000_000)
    message: str = Field(
        default="Đọc nội dung trong ảnh và đề xuất những việc tôi nên làm.",
        min_length=1,
        max_length=2000,
    )


class TaskSuggestionAction(CamelModel):
    """Một việc agent nhận ra trong nguồn nhưng CHƯA tạo gì cả.

    Khác `TaskDraftActionResponse` ở chỗ không có `id`: chưa có dòng nào trong
    bảng `tasks`. Người dùng bấm "Thêm task" trên thẻ thì mới sinh bản nháp.
    Giữ nguyên ranh giới ADR-007: agent đề xuất, người dùng mới là bên ghi.
    """

    title: str = Field(..., min_length=1, max_length=500)
    detail: str = Field(default="", max_length=2000)
    due_at: datetime | None = None
    all_day: bool = False
    # Người phụ trách chỉ được hiển thị khi nguồn nêu rõ; không tự suy diễn
    # người sở hữu từ tên xuất hiện ngẫu nhiên trong ảnh/tin nhắn.
    assignee: str | None = Field(default=None, max_length=255)
    # Tên nguồn để người dùng đối chiếu ("Gmail", "Jira"). Không phải deep link
    # — thẻ gợi ý chỉ cần nói việc này nhìn thấy ở đâu.
    source: str = Field(default="", max_length=64)


class CalendarSuggestionAction(CamelModel):
    """Một sự kiện đọc được từ ảnh, chưa ghi sang Google Calendar."""

    title: str = Field(..., min_length=1, max_length=500)
    detail: str = Field(default="", max_length=2000)
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    source: str = Field(default="Ảnh", max_length=64)

    @model_validator(mode="after")
    def check_window(self) -> "CalendarSuggestionAction":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("startAt và endAt phải có múi giờ.")
        if self.end_at <= self.start_at:
            raise ValueError("endAt phải sau startAt.")
        return self


class VisionActionResponse(CamelModel):
    """Kết quả suy luận từ ảnh: chỉ đề xuất, không tự tạo task/event (ADR-007).

    `task_suggestions` dùng chung `TaskSuggestionAction` với luồng chat
    (`_task_suggestions_from_agent_result` trong `src/api/conversations.py`)
    nên có đúng field mà `POST /tasks/from-suggestion` cần (title, detail,
    due_at, all_day) — frontend gọi thẳng không cần convert thủ công. Không có
    field `calendar_suggestions` riêng: một suggestion có `due_at` vẫn đi qua
    cùng pipeline Task → xác nhận → đồng bộ Calendar, tách riêng chỉ nhân đôi
    logic mà không đổi hành vi observable.
    """

    action_type: Literal["task", "calendar_event", "mixed", "unclear"] = "unclear"
    response: str
    analysis: str = ""
    sources: list[dict] = Field(default_factory=list)
    task_suggestions: list[TaskSuggestionAction] = Field(default_factory=list)
    # Optional để các response cũ không bị phình thêm field rỗng; frontend coi
    # thiếu field như không có batch lịch.
    calendar_suggestions: list[CalendarSuggestionAction] | None = None
    warnings: list[str] = Field(default_factory=list)
    visual_context_used: bool = True


# Email regex đơn giản, tránh thêm dependency email-validator chỉ cho 1 field.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(CamelModel):
    email: str = Field(..., pattern=_EMAIL_PATTERN, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=120)


class LoginRequest(CamelModel):
    email: str = Field(..., pattern=_EMAIL_PATTERN, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(CamelModel):
    refresh_token: str = Field(..., min_length=1)


class ForgotPasswordRequest(CamelModel):
    email: str = Field(..., pattern=_EMAIL_PATTERN, max_length=255)


class ForgotPasswordResponse(CamelModel):
    message: str


class ResetPasswordRequest(CamelModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class ResetPasswordResponse(CamelModel):
    message: str


class DeleteAccountRequest(CamelModel):
    # Rỗng cho tài khoản chỉ đăng nhập Google — endpoint tự bỏ qua kiểm tra
    # password trong trường hợp đó, JWT hợp lệ là đủ.
    password: str | None = Field(default=None, max_length=128)


class GoogleSessionRequest(CamelModel):
    """Đổi login code ngắn hạn (từ redirect callback OAuth) lấy access/refresh
    token thật — xem oauth_state.sign_login_code."""

    code: str = Field(..., min_length=1)


class AppleSessionRequest(CamelModel):
    """Credential native; authorization code dùng để revoke khi xoá account."""

    identity_token: str = Field(..., min_length=1, max_length=16384)
    display_name: str = Field(default="", max_length=120)
    authorization_code: str | None = Field(default=None, max_length=4096)


class TokenResponse(CamelModel):
    access_token: str
    expires_in: int
    refresh_token: str
    user_id: str
    email: str
    role: str = "participant"
    avatar_url: str | None = None
    program_access_level: Literal["A", "B", "C"] = "C"


class UserResponse(CamelModel):
    id: str
    email: str
    role: str = "participant"
    display_name: str = ""
    avatar_url: str | None = None
    program_access_level: Literal["A", "B", "C"] = "C"


class UserProfileMemoryResponse(CamelModel):
    profile: dict[str, str] = Field(default_factory=dict)


class UserMemoryEvidenceItem(CamelModel):
    evidence_type: str
    evidence_ref: str


class UserMemoryUpdateRequest(CamelModel):
    value: str = Field(..., min_length=1, max_length=500)


class UserMemoryItem(CamelModel):
    """Một fact dài hạn hiển thị cho người dùng.

    `status` và `source` bắt buộc có mặt: giao diện phải phân biệt được fact đã
    xác nhận với fact mới chỉ suy ra, đó là bất biến của memory-lifecycle §11.
    """

    key: str
    version: int = 1
    kind: str
    subject: str
    predicate: str
    value: object = None
    status: Literal["candidate", "confirmed", "disputed", "superseded", "rejected", "forgotten"]
    source: Literal["user", "official", "inferred"]
    confidence: float = 0.5
    reinforcement_count: int = 1
    negative_feedback_count: int = 0
    first_observed_at: datetime | None = None
    last_reinforced_at: datetime | None = None
    evidence: list[UserMemoryEvidenceItem] = Field(default_factory=list)


class UserMemoryListResponse(CamelModel):
    memories: list[UserMemoryItem] = Field(default_factory=list)


class MemoryGraphNode(CamelModel):
    id: str
    label: str
    node_type: str
    status: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class MemoryGraphEdge(CamelModel):
    id: str
    source: str
    target: str
    type: str
    label: str | None = None


class MemoryGraphResponse(CamelModel):
    nodes: list[MemoryGraphNode] = Field(default_factory=list)
    edges: list[MemoryGraphEdge] = Field(default_factory=list)


ConnectionProvider = Literal["discord", "google", "telegram", "jira", "outlook", "slack"]


class ConnectionIntentRequest(CamelModel):
    ext_redirect_uri: str = Field(..., description="chrome.identity.getRedirectURL() của extension")


class ConnectionIntentResponse(CamelModel):
    authorize_url: str


class GmailStatusResponse(CamelModel):
    source: str = "gmail"
    status: str
    account_email: str | None = None
    permission: str | None = None
    email_count: int = 0
    last_synced_at: datetime | None = None
    oauth_valid: bool = False
    mailbox_accessible: bool = False
    initial_sync_completed: bool = False
    last_error: str | None = None


class GmailSyncResponse(CamelModel):
    run_id: int
    status: str


class ConnectionStatus(CamelModel):
    id: int | None = None
    provider: ConnectionProvider
    connected: bool
    account_label: str | None = None
    expires_at: datetime | None = None
    # true khi refresh token đã bị Google/Microsoft/Jira thu hồi hoặc hết hạn —
    # `connected` vẫn true (bản ghi tồn tại) nhưng gọi API thật sẽ luôn lỗi.
    # FE dùng cờ này để đổi nút "Ngắt kết nối" thành "Kết nối lại" thay vì để
    # người dùng tự đoán qua log lỗi rải rác.
    needs_reconnect: bool = False
    last_error: str | None = None


class ConnectionListResponse(CamelModel):
    connections: list[ConnectionStatus]


GoogleDriveFileKind = Literal["document", "spreadsheet"]


class GoogleDriveFile(CamelModel):
    id: str
    name: str
    kind: GoogleDriveFileKind
    modified_time: datetime
    web_view_link: str


class GoogleDriveFileListResponse(CamelModel):
    files: list[GoogleDriveFile] = Field(default_factory=list)
    next_page_token: str | None = None


def _require_exactly_one(url: str | None, identifier: str | None, field_label: str) -> None:
    """Người dùng đưa URL hoặc id, đúng một trong hai.

    Nhận cả hai rồi tự chọn một bên là im lặng bỏ qua ý định của caller: nếu
    hai giá trị trỏ hai file khác nhau thì kết quả trả về không phải file nào
    người dùng nghĩ. Thà 422.
    """
    if bool(url) == bool(identifier):
        raise ValueError(f"Cần đúng một trong hai: {field_label}Url hoặc {field_label}Id.")


class GoogleSheetsTaskProposalRequest(CamelModel):
    spreadsheet_url: str | None = Field(default=None, min_length=1, max_length=500)
    spreadsheet_id: str | None = Field(default=None, min_length=1, max_length=200)
    sheet_name: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def _check_source(self) -> "GoogleSheetsTaskProposalRequest":
        _require_exactly_one(self.spreadsheet_url, self.spreadsheet_id, "spreadsheet")
        return self


class GoogleSheetsTaskProposal(CamelModel):
    row_number: int
    external_key: str
    title: str
    detail: str = ""
    assignee: str | None = None
    due_at: datetime | None = None
    all_day: bool = False
    status: str | None = None
    matched_user: bool = False
    match_kind: Literal["exact", "close", "possible", "none"] = "none"
    needs_confirmation: bool = True
    clarification_question: str | None = None
    date_ambiguous: bool = False
    source: str
    source_url: str


class GoogleSheetsTaskProposalResponse(CamelModel):
    spreadsheet_id: str
    sheet_name: str
    timezone: str
    available_sheet_names: list[str] = Field(default_factory=list)
    proposals: list[GoogleSheetsTaskProposal] = Field(default_factory=list)
    # truncated=True nghĩa là bảng bị cắt bớt trước khi phân tích (xem
    # google_sheet_max_rows/columns/google_document_max_chars trong config).
    truncated: bool = False
    quota_remaining: int = 0


class ExcelTaskProposalResponse(CamelModel):
    """Kết quả đọc tệp Excel cục bộ; tệp không được lưu sau request."""

    file_names: list[str] = Field(default_factory=list)
    timezone: str
    proposals: list[GoogleSheetsTaskProposal] = Field(default_factory=list)
    agent_response: str = ""
    agent_analysis: str = ""
    agent_warning: str | None = None
    searched_name: str = ""
    needs_name_query: bool = False
    suggested_names: list[str] = Field(default_factory=list)


class GoogleDocsTaskProposalRequest(CamelModel):
    document_url: str | None = Field(default=None, min_length=1, max_length=500)
    document_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _check_source(self) -> "GoogleDocsTaskProposalRequest":
        _require_exactly_one(self.document_url, self.document_id, "document")
        return self


class GoogleDocsTaskProposal(CamelModel):
    paragraph_index: int
    title: str
    detail: str = ""
    assignee: str | None = None
    due_at: datetime | None = None
    all_day: bool = False
    matched_user: bool = False
    needs_confirmation: bool = True
    clarification_question: str | None = None
    date_ambiguous: bool = False
    source: str
    source_url: str


class GoogleDocsTaskProposalResponse(CamelModel):
    document_id: str
    timezone: str
    proposals: list[GoogleDocsTaskProposal] = Field(default_factory=list)
    # truncated=True nghĩa là văn bản đã bị cắt ở google_document_max_chars
    # trước khi đưa cho LLM, nên có thể sót việc ở cuối tài liệu.
    truncated: bool = False
    quota_remaining: int = 0


# TAPB-121 + ADR-007 mục 4: proposed -> confirmed | dismissed; confirmed ->
# completed | cancelled; proposed -> cancelled. Guard transition đầy đủ nằm ở
# src/api/tasks.py (_transition, allowed_from theo từng endpoint). Không có
# transition ngược. "completed"/"cancelled" tách biệt với "dismissed" của
# LỜI NHẮC (Reminder.status) — xem src/services/reminders.py.
TaskStatus = Literal["proposed", "confirmed", "dismissed", "completed", "cancelled"]


class TaskEvidenceResponse(CamelModel):
    id: int
    message_id: int | None = None
    provider: str
    evidence_quote: str
    deep_link: str
    has_attachment: bool = False


class TaskResponse(CamelModel):
    id: int
    cluster_key: str
    title: str
    detail: str
    due_at: datetime | None = None
    all_day: bool
    ambiguous: bool
    assignee: str | None = None
    assignee_ambiguous: bool = True
    status: str
    source_count: int
    signal_strength: float
    calendar_event_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    actual_minutes: int | None = None
    # Mốc vào thùng rác. FE dùng nó để hiện 'còn N ngày trước khi xoá'.
    cancelled_at: datetime | None = None
    # ADR-021 — mốc người dùng xác nhận bắt đầu làm.
    started_at: datetime | None = None
    updated_at: datetime
    evidence: list[TaskEvidenceResponse] = Field(default_factory=list)
    expected_output: str | None = None
    acceptance_criteria: str | None = None
    context_input: str | None = None
    constraints: str | None = None
    execution_tool: str | None = None
    execution_method: str | None = None
    stated_priority: str | None = None
    stakeholders: list[str] | None = None
    deliver_to: str | None = None
    # ADR-019 — ước lượng đã trích sẵn; thiếu ở response nên giao diện không
    # hiện được dù cột đã có dữ liệu.
    estimate_low_min: int | None = None
    estimate_high_min: int | None = None
    # Chỉ có trong response của thao tác xác nhận suggestion. Giúp giao diện
    # nói rõ task đã được gộp vào cụm có sẵn thay vì báo "đã tạo" sai sự thật.
    deduplicated: bool = False
    dedup_layer: str | None = None
    estimate_low_min: int | None = None
    estimate_high_min: int | None = None


class CalendarHandoffResponse(CamelModel):
    task_id: int
    ics_url: str
    google_calendar_url: str
    opened: bool
    opened_at: datetime | None = None
    # P0 chỉ sinh .ics/link mẫu (ADR-002) — KHÔNG có tích hợp Calendar API
    # thật, nên trạng thái luôn là "EXPORTED", không bao giờ "CALENDAR_SYNCED".
    # Đổi giá trị này chỉ khi thật sự có tích hợp ghi event qua Calendar API.
    status: Literal["EXPORTED"] = "EXPORTED"


class CalendarInfoResponse(CamelModel):
    id: str
    name: str
    #: Người dùng có quyền ghi vào lịch này không (Google accessRole). Mặc định
    #: True để phản hồi cũ và nguồn không phải Google giữ nguyên hành vi.
    writable: bool = True


class CalendarEventResponse(CamelModel):
    id: str
    title: str
    start_at: str
    end_at: str | None = None
    all_day: bool = False
    status: str = "confirmed"
    calendar_id: str
    calendar_name: str
    deep_link: str | None = None


class CalendarEventListResponse(CamelModel):
    calendars: list[CalendarInfoResponse] = Field(default_factory=list)
    events: list[CalendarEventResponse] = Field(default_factory=list)


class CalendarSyncResponse(CamelModel):
    task_id: int
    calendar_event_id: str
    calendar_url: str | None = None
    already_synced: bool = False


class CachedCalendarEventResponse(CamelModel):
    """Sự kiện đọc từ bộ nhớ đệm — luôn kèm mốc đồng bộ để không giả vờ realtime."""

    id: str
    calendar_id: str
    title: str
    description: str = ""
    start_at: datetime
    end_at: datetime | None = None
    all_day: bool = False
    status: str = "active"
    deep_link: str | None = None
    synced_at: datetime


class CalendarWeekResponse(CamelModel):
    events: list[CachedCalendarEventResponse] = Field(default_factory=list)
    calendars: list[CalendarInfoResponse] = Field(default_factory=list)
    # Nguồn dữ liệu của lần trả về này: `cache` đọc từ bộ nhớ đệm, `refreshed`
    # vừa gọi Google. Giao diện dùng để hiện nhãn "cập nhật lúc ...".
    origin: Literal["cache", "refreshed"] = "cache"
    last_synced_at: datetime | None = None
    # Lịch không đọc được trong lần làm mới này — FR-045 buộc phải nói rõ
    # thông tin có thể chưa đầy đủ thay vì im lặng.
    failed_calendars: list[str] = Field(default_factory=list)


ConflictType = Literal["time_overlap", "same_item"]
ConflictStatus = Literal["open", "resolved", "superseded", "stale"]
# Cùng bộ từ vựng cho gợi ý của hệ thống và quyết định của người dùng, để so
# được hai bên. `undecided` chỉ hệ thống dùng: không đủ căn cứ thì không gợi ý.
ConflictSuggestion = Literal["prioritize_task", "prioritize_event", "undecided"]
ConflictResolution = Literal["prioritize_task", "prioritize_event", "accept_both"]


class ConflictEventSideResponse(CamelModel):
    """Bên sự kiện của một lần trùng, đọc từ ảnh chụp lúc phát hiện."""

    title: str
    calendar_id: str
    event_id: str
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    deep_link: str | None = None
    synced_at: datetime | None = None


class ConflictTaskSideResponse(CamelModel):
    """Bên task của một lần trùng, đọc trực tiếp từ task hiện tại."""

    task_id: int
    title: str
    due_at: datetime | None = None
    all_day: bool = False
    ambiguous: bool = False
    status: str
    source_count: int
    signal_strength: float


class ScheduleConflictResponse(CamelModel):
    id: int
    conflict_type: ConflictType
    status: ConflictStatus
    overlap_minutes: int
    # Slug lý do, giao diện tự dịch — không trả câu tiếng Việt dựng ở máy chủ
    # để hai ngôn ngữ giao diện dùng chung một nguồn dữ liệu.
    suggestion: ConflictSuggestion
    suggestion_reasons: list[str] = Field(default_factory=list)
    resolution: ConflictResolution | None = None
    resolution_note: str = ""
    resolved_at: datetime | None = None
    detected_at: datetime
    task: ConflictTaskSideResponse
    event: ConflictEventSideResponse


class ScheduleConflictListResponse(CamelModel):
    conflicts: list[ScheduleConflictResponse] = Field(default_factory=list)
    # Số lần trùng còn chờ quyết — giao diện dùng cho badge, không phải đếm lại
    # trên danh sách đã lọc.
    open_count: int = 0


class ScheduleConflictResolveRequest(CamelModel):
    resolution: ConflictResolution
    note: str = Field(default="", max_length=500)


class AdminProgramEventRow(CamelModel):
    """Một mốc chương trình nhìn từ trang quản trị (ADR-010)."""

    id: int
    cohort_slug: str
    external_id: str
    event_type: str
    visibility: str
    title: str
    description: str = ""
    host: str | None = None
    location_url: str | None = None
    start_at: datetime
    end_at: datetime | None = None
    # feed = từ ICS ban tổ chức; admin = quản trị tự tạo.
    origin: str = "feed"
    status: str = "published"
    # Trường quản trị đã sửa tay và lần nhập feed sau không được ghi đè.
    locked_fields: list[str] = Field(default_factory=list)
    # Feed đã đổi đúng vào một trường đang khóa — cần người chọn giữ bản nào.
    source_conflict: bool = False
    # Bản gốc từ feed, để màn hình so được với bản đang hiển thị.
    feed_payload: dict | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None
    published_at: datetime | None = None
    changed_fields: list[str] = Field(default_factory=list)
    notification_count: int = 0


class AdminProgramEventListResponse(CamelModel):
    items: list[AdminProgramEventRow] = Field(default_factory=list)
    total: int = 0
    limit: int = 100
    offset: int = 0
    cohort_slug: str
    conflict_count: int = 0


class AdminProgramScheduleTemplateRow(CamelModel):
    id: int
    cohort_slug: str
    title: str
    description: str = ""
    host: str | None = None
    location_url: str | None = None
    event_type: str = "custom"
    weekdays: list[int]
    start_time: str
    end_time: str
    starts_on: date
    ends_on: date
    active: bool = True
    published: bool = False


class AdminProgramScheduleTemplateRequest(CamelModel):
    cohort_slug: str | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    host: str | None = Field(default=None, max_length=255)
    location_url: str | None = Field(default=None, max_length=512)
    event_type: Literal["custom", "daily_deadline", "weekly_deadline", "gate_deadline", "mentor_duty"] = "custom"
    weekdays: list[int] = Field(min_length=1, max_length=7)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    starts_on: date
    ends_on: date
    active: bool = True
    published: bool = False

    @model_validator(mode="after")
    def check_schedule(self) -> "AdminProgramScheduleTemplateRequest":
        if self.starts_on > self.ends_on:
            raise ValueError("endsOn phải từ startsOn trở đi.")
        if len(set(self.weekdays)) != len(self.weekdays) or any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("weekdays phải là các giá trị duy nhất từ 0 đến 6.")
        from datetime import time

        try:
            start = time.fromisoformat(self.start_time)
            end = time.fromisoformat(self.end_time)
        except ValueError as exc:
            raise ValueError("Giờ phải có định dạng HH:MM.") from exc
        if start.second or end.second or end <= start:
            raise ValueError("endTime phải sau startTime trong cùng ngày.")
        return self


class AdminProgramEventCreateRequest(CamelModel):
    """Thêm một mốc không có trên feed của ban tổ chức."""

    cohort_slug: str | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    event_type: Literal["custom", "daily_deadline", "weekly_deadline", "gate_deadline", "mentor_duty"] = "custom"
    visibility: Literal["program", "team"] = "program"
    host: str | None = Field(default=None, max_length=255)
    location_url: str | None = Field(default=None, max_length=512)
    start_at: datetime
    end_at: datetime | None = None

    @model_validator(mode="after")
    def check_window(self) -> "AdminProgramEventCreateRequest":
        """Bắt lỗi ngay tại biên; mốc lịch sai thứ tự là lỗi dữ liệu, không phải lỗi hiển thị."""
        if self.start_at.tzinfo is None:
            raise ValueError("startAt phải có múi giờ.")
        if self.end_at is not None:
            if self.end_at.tzinfo is None:
                raise ValueError("endAt phải có múi giờ.")
            if self.end_at <= self.start_at:
                raise ValueError("endAt phải sau startAt.")
        return self


class AdminProgramEventUpdateRequest(CamelModel):
    """Sửa một mốc. Chỉ trường được gửi lên mới đổi, phần còn lại giữ nguyên."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    event_type: Literal["custom", "daily_deadline", "weekly_deadline", "gate_deadline", "mentor_duty"] | None = None
    visibility: Literal["program", "team"] | None = None
    host: str | None = Field(default=None, max_length=255)
    location_url: str | None = Field(default=None, max_length=512)
    start_at: datetime | None = None
    end_at: datetime | None = None
    notify_users: bool = False
    change_note: str = Field(default="", max_length=500)
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def check_window(self) -> "AdminProgramEventUpdateRequest":
        if self.start_at is not None and self.start_at.tzinfo is None:
            raise ValueError("startAt phải có múi giờ.")
        if self.end_at is not None and self.end_at.tzinfo is None:
            raise ValueError("endAt phải có múi giờ.")
        if self.expected_updated_at is not None and self.expected_updated_at.tzinfo is None:
            raise ValueError("expectedUpdatedAt phải có múi giờ.")
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("endAt phải sau startAt.")
        return self


class AdminProgramEventPublishRequest(CamelModel):
    """Tuỳ chọn báo người đã đồng ý sync; mặc định không tự gửi."""

    notify_users: bool = False
    change_note: str = Field(default="", max_length=500)
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def check_expected_updated_at(self) -> "AdminProgramEventPublishRequest":
        if self.expected_updated_at is not None and self.expected_updated_at.tzinfo is None:
            raise ValueError("expectedUpdatedAt phải có múi giờ.")
        return self


class ProgramSyncPreviewRequest(CamelModel):
    """Xin bảng xem trước trước khi đồng bộ lịch chương trình (ADR-009)."""

    # Bỏ trống là dùng mặc định của service: workshop/office hour, gate, weekly.
    # Hạn daily phải chọn tường minh vì nó lặp mỗi ngày.
    event_types: list[str] | None = None
    time_from: datetime | None = None
    time_to: datetime | None = None


class ProgramSyncPlanItemResponse(CamelModel):
    program_event_id: int
    event_type: str
    title: str
    start_at: datetime
    end_at: datetime | None = None
    # create | update | unchanged — giao diện tick sẵn create/update, không tick
    # unchanged, và luôn hiện `reason` để user biết vì sao mốc này lại hỏi lại.
    action: str
    reason: str


class ProgramSyncPreviewResponse(CamelModel):
    items: list[ProgramSyncPlanItemResponse] = Field(default_factory=list)
    cohort_slug: str


class ProgramSyncApplyRequest(CamelModel):
    """Danh sách mốc user đã bấm đồng ý — máy chủ chỉ ghi đúng những mốc này."""

    calendar_id: str = Field(default="primary", max_length=512)
    program_event_ids: list[int] = Field(default_factory=list)


class ProgramSyncApplyResponse(CamelModel):
    created: int = 0
    updated: int = 0
    # Mốc bị bỏ qua kèm lý do: không thuộc cohort, không phải lịch chung, hoặc
    # ghi sang Google hỏng. Im lặng bỏ qua là để user tin lịch đã đủ trong khi
    # không đủ.
    skipped: list[str] = Field(default_factory=list)


class CalendarEventWriteRequest(CamelModel):
    """Người dùng tự tạo hoặc sửa sự kiện trên lưới lịch (FR-069)."""

    calendar_id: str = Field(default="primary", max_length=512)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool = False

    @model_validator(mode="after")
    def check_window(self) -> "CalendarEventWriteRequest":
        """Không tự suy ra giờ kết thúc; sai thứ tự thì từ chối ngay tại biên."""
        if self.start_at is not None and self.start_at.tzinfo is None:
            raise ValueError("startAt phải có múi giờ.")
        if self.end_at is not None and self.end_at.tzinfo is None:
            raise ValueError("endAt phải có múi giờ.")
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValueError("endAt phải sau startAt.")
        return self


class CalendarWriteResponse(CamelModel):
    event: CachedCalendarEventResponse | None = None
    # Mã thao tác để hoàn tác trong cửa sổ cho phép (BR-14). Hết cửa sổ thì
    # endpoint undo từ chối, không âm thầm bỏ qua.
    operation_id: int
    undo_expires_at: datetime


class CalendarBatchWriteRequest(CamelModel):
    """Các sự kiện user đã chọn trong một review ảnh."""

    calendar_id: str = Field(default="primary", max_length=512)
    events: list[CalendarEventWriteRequest] = Field(..., min_length=1, max_length=50)


class CalendarBatchFailure(CamelModel):
    index: int
    detail: str


class CalendarBatchWriteResponse(CamelModel):
    created: list[CalendarWriteResponse] = Field(default_factory=list)
    failed: list[CalendarBatchFailure] = Field(default_factory=list)


class TaskListResponse(CamelModel):
    tasks: list[TaskResponse]


class TaskBreakdownItem(CamelModel):
    """Một đoạn chat trong kế hoạch hôm nay: vì sao ưu tiên, tách bước ra sao,
    cần chuẩn bị gì và prompt copy-paste sang AI khác. Xem
    src/services/task_breakdown.py — mọi task_id đều đã được ground vào DB."""

    task_id: int
    title: str
    due_at: datetime | None = None
    should_break: bool
    reason: str = ""
    steps: list[str] = Field(default_factory=list)
    context_needed: list[str] = Field(default_factory=list)
    ai_prompt: str = ""


class ScheduledBlockResponse(CamelModel):
    task_id: int
    title: str
    start: datetime
    end: datetime
    minutes: int
    energy: Literal["deep", "shallow"]
    estimate_confidence: Literal["estimated", "neutral_fallback"]
    why: str
    communication: str | None = None


class DeferredTaskResponse(CamelModel):
    task_id: int
    title: str
    start: datetime | None = None
    end: datetime | None = None
    minutes: int
    energy: Literal["deep", "shallow"]
    estimate_confidence: Literal["estimated", "neutral_fallback"]
    why: str


class DayScheduleResponse(CamelModel):
    now: datetime
    blocks: list[ScheduledBlockResponse] = Field(default_factory=list)
    deferred_to_tomorrow: list[DeferredTaskResponse] = Field(default_factory=list)
    rest_reminder: str | None = None
    notes: list[str] = Field(default_factory=list)


class PlannerPreferenceResponse(CamelModel):
    workday_start_minute: int
    lunch_start_minute: int
    lunch_end_minute: int
    workday_end_minute: int
    happy_time_enabled: bool
    happy_time_start_minute: int
    happy_time_end_minute: int


class PlannerPreferenceUpdateRequest(CamelModel):
    workday_start_minute: int | None = Field(default=None, ge=0, le=1439)
    lunch_start_minute: int | None = Field(default=None, ge=0, le=1439)
    lunch_end_minute: int | None = Field(default=None, ge=0, le=1439)
    workday_end_minute: int | None = Field(default=None, ge=1, le=1439)
    happy_time_enabled: bool | None = None
    happy_time_start_minute: int | None = Field(default=None, ge=0, le=1439)
    happy_time_end_minute: int | None = Field(default=None, ge=1, le=1440)


class PlannerPlanRequest(CamelModel):
    start: datetime | None = None
    days: Literal[1, 7] = 1
    # Snapshot chỉ tồn tại tại client để lần "Làm mới" so sánh với proposal
    # trước. Nó không phải lệnh ghi lịch hay một nguồn dữ liệu mới.
    known_task_ids: list[int] = Field(default_factory=list, max_length=500)
    previous_blocks: list["PlannerPreviousBlock"] = Field(default_factory=list, max_length=200)


class PlannerPreviousBlock(CamelModel):
    task_id: int
    start: datetime
    end: datetime


class PlannerRefreshSummary(CamelModel):
    new_task_count: int = 0
    new_urgent_today_count: int = 0
    reschedule_count: int = 0
    at_risk_count: int = 0


class PlannerRescheduleSuggestion(CamelModel):
    task_id: int
    title: str
    from_start: datetime | None = None
    from_end: datetime | None = None
    to_start: datetime | None = None
    to_end: datetime | None = None
    reason: str


class PlannerBusyBlockResponse(CamelModel):
    """Khoảng bận được Planner tôn trọng, không phải task do Planner tạo."""

    title: str
    start: datetime
    end: datetime
    source: Literal["personal_calendar", "program_calendar"]
    all_day: bool = False
    synced_at: datetime | None = None


class PlannerPlanResponse(CamelModel):
    generated_at: datetime
    days: Literal[1, 7]
    blocks: list[ScheduledBlockResponse] = Field(default_factory=list)
    at_risk: list[DeferredTaskResponse] = Field(default_factory=list)
    calendar_blocks: list[PlannerBusyBlockResponse] = Field(default_factory=list)
    considered_task_ids: list[int] = Field(default_factory=list)
    refresh: PlannerRefreshSummary = Field(default_factory=PlannerRefreshSummary)
    reschedule_suggestions: list[PlannerRescheduleSuggestion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TaskBreakdownResponse(CamelModel):
    generated_at: datetime
    summary: str = ""
    items: list[TaskBreakdownItem] = Field(default_factory=list)
    schedule: DayScheduleResponse


class IntegrationResponse(CamelModel):
    id: int
    provider: ConnectionProvider
    account_label: str | None = None
    expires_at: datetime | None = None


class IntegrationListResponse(CamelModel):
    integrations: list[IntegrationResponse]


class SourceInfo(CamelModel):
    id: str
    name: str
    item_count: int | None = None


class IntegrationSourcesResponse(CamelModel):
    sources: list[SourceInfo]
    # Một OAuth connection có thể phục vụ nhiều connector. Nếu một connector
    # con lỗi (vd. token cũ chưa có Calendar scope), vẫn trả nguồn còn dùng được
    # và nói rõ phần thiếu thay vì biến toàn bộ integration thành mock.
    warnings: list[str] = Field(default_factory=list)


class SyncSourceRef(CamelModel):
    connection_id: int
    source_id: str


RunStatus = Literal["queued", "running", "succeeded", "failed"]


class RunCreateRequest(CamelModel):
    sources: list[SyncSourceRef] = Field(..., min_length=1, max_length=20)
    time_from: datetime
    time_to: datetime
    timezone: str = Field(default="UTC")
    # Ngôn ngữ title/summary/detail do LLM viết cho run này — theo đúng
    # ngôn ngữ app đang hiển thị lúc FE gọi Sync, không phải cấu hình cố
    # định của user. evidence_quote/time_expression KHÔNG bị ảnh hưởng, luôn
    # giữ nguyên ngôn ngữ gốc của nguồn (xem extract_batch.py).
    language: SupportedLanguage = DEFAULT_LANGUAGE
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    mode: Literal["summary", "task_extraction"] = "task_extraction"

    @model_validator(mode="after")
    def validate_time_range(self) -> "RunCreateRequest":
        if self.time_to <= self.time_from:
            raise ValueError("timeTo phải sau timeFrom.")
        if self.time_to - self.time_from > timedelta(days=365):
            raise ValueError("Khoảng Sync vượt quá giới hạn tuyệt đối 365 ngày.")
        return self


class RunLimitsResponse(CamelModel):
    """Hạn mức Sync mà FE cần biết trước khi người dùng bấm gì.

    `auto_sync_enabled` đã là kết quả AND của công tắc tổng phía server và
    công tắc riêng của user, nên FE chỉ việc hiển thị chứ không phải tự suy.
    """

    max_sync_sources: int
    max_sync_range_days: int
    auto_sync_enabled: bool
    auto_sync_interval_minutes: int


class AutoSyncPreferenceUpdateRequest(CamelModel):
    """Công tắc đồng ý auto-sync của chính người dùng.

    Field bắt buộc để PATCH không vô tình biến body rỗng thành thao tác thành
    công mà không đổi gì. Công tắc tổng vẫn thuộc vận hành, không nhận ở đây.
    """

    model_config = ConfigDict(extra="forbid")

    auto_sync_enabled: bool


class AutoSyncPreferenceResponse(CamelModel):
    """Trả cả lựa chọn đã lưu và trạng thái hiệu lực sau công tắc tổng."""

    auto_sync_enabled: bool
    user_auto_sync_enabled: bool
    auto_sync_interval_minutes: int


class RunResponse(CamelModel):
    id: int
    status: RunStatus
    error_message: str | None = None
    created_at: datetime


class ChatSyncRequest(CamelModel):
    """Yêu cầu "kiểm tra xem câu chat này có cần kéo đồng bộ không".

    Gửi cả câu chat lên chứ không để client tự phán: luật quyết định nằm ở
    server (src/services/chat_sync.py) để mọi client — web, mobile, extension —
    cư xử giống nhau và sửa luật không phải deploy lại từng client.
    """

    message: str = Field(default="", max_length=5000)
    timezone: str = Field(default="UTC", max_length=64)
    language: SupportedLanguage = DEFAULT_LANGUAGE


class ChatSyncResponse(CamelModel):
    """`run` chỉ có khi thật sự vừa xếp một lần đồng bộ.

    `triggered=False` không phải lỗi — nghĩa là dữ liệu còn mới, hoặc đang có
    run khác chạy. Client cứ trả lời từ dữ liệu sẵn có; `reason` để hiện ra khi
    debug chứ không phải câu chữ cho người dùng đọc.
    """

    triggered: bool
    reason: str
    run: RunResponse | None = None


class ProjectCreateRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    color: str = Field(default="slate", max_length=16)


class ProjectUpdateRequest(CamelModel):
    """Mọi field optional — PATCH chỉ đổi thứ được gửi lên.

    `model_config` cấm field lạ để một lỗi chính tả phía client không âm thầm
    biến thành "không đổi gì" mà client vẫn nhận 200.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=to_camel)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=16)


class ProjectResponse(CamelModel):
    id: int
    name: str
    description: str
    color: str
    conversation_count: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(CamelModel):
    projects: list[ProjectResponse]


class ProjectConversationSummary(CamelModel):
    id: int
    title: str
    message_count: int
    updated_at: datetime


class ProjectMeetingSummary(CamelModel):
    id: int
    title: str
    status: Literal["open", "summarized"]
    started_at: datetime
    ended_at: datetime | None = None
    updated_at: datetime


class ProjectContextResponse(CamelModel):
    project_id: int
    conversations: list[ProjectConversationSummary]
    meetings: list[ProjectMeetingSummary]


class ProjectOverviewResponse(CamelModel):
    """Trang chi tiết dự án: danh sách hội thoại + tóm tắt điểm chung.

    `summary` rỗng là hợp lệ (dự án chưa có hội thoại nào). `summary_updated_at`
    None nghĩa là chưa từng sinh.
    """

    project: ProjectResponse
    conversations: list[ProjectConversationSummary]
    summary: str
    summary_updated_at: datetime | None = None
    meetings: list[ProjectMeetingSummary] = Field(default_factory=list)
    meeting_count: int = 0


class ProjectSuggestionResponse(CamelModel):
    """`suggestion` là None khi không đủ chắc — đó là kết quả hợp lệ, không
    phải lỗi. Thà im lặng còn hơn hỏi sai liên tục rồi bị bỏ qua như rác."""

    suggestion: dict | None = None


class BriefResponse(CamelModel):
    id: int
    run_id: int
    summary: str
    top_priority: list[dict]
    schedule_conflicts: list[dict]
    evidence: list[dict] = Field(default_factory=list)
    created_at: datetime


class MessageResponse(CamelModel):
    id: int
    provider: str
    thread_id: str | None = None
    author_name: str | None = None
    is_self: bool
    is_dm: bool
    text: str
    sent_at: datetime
    deep_link: str | None = None


class MessageListResponse(CamelModel):
    messages: list[MessageResponse]


class ConversationCreateRequest(CamelModel):
    title: str | None = Field(default=None, max_length=255)
    initial_question: str | None = Field(default=None, max_length=20000)


class ConversationSummary(CamelModel):
    id: int
    title: str
    message_count: int
    # Dự án chứa hội thoại. None = chưa xếp — trạng thái mặc định hợp lệ, danh
    # sách dùng nó để biết chỗ nào cần hiện huy hiệu gợi ý.
    project_id: int | None = None
    is_favorite: bool = False
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(CamelModel):
    conversations: list[ConversationSummary]


class ConversationTurn(CamelModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    extras: dict | None = None
    feedback: Literal["helpful", "partly", "incorrect"] | None = None
    created_at: datetime


class ConversationFavoriteRequest(CamelModel):
    is_favorite: bool


class AppendTurnRequest(CamelModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20000)
    extras: dict | None = None


class RenameConversationRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=255)


class FeedbackRequest(CamelModel):
    feedback: Literal["helpful", "partly", "incorrect"]


class ConversationDetailResponse(CamelModel):
    id: int
    title: str
    is_favorite: bool = False
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationTurn]


class ShareConversationRequest(CamelModel):
    visibility: Literal["private", "public"] = "private"


class ShareConversationResponse(CamelModel):
    visibility: Literal["private", "public"]
    public_url: str | None = None
    public_token: str | None = None


class SharedConversationResponse(CamelModel):
    title: str
    messages: list[ConversationTurn]


class SendMessageRequest(CamelModel):
    message: str = Field(..., min_length=1, max_length=5000)
    image_data: str | None = Field(default=None, max_length=8_000_000)


class TaskFromSuggestionRequest(CamelModel):
    """Payload người dùng gửi khi bấm "Thêm task" trên một thẻ gợi ý."""

    title: str = Field(..., min_length=1, max_length=500)
    detail: str = Field(default="", max_length=10_000)
    due_at: datetime | None = None
    all_day: bool = False
    assignee: str | None = Field(default=None, max_length=255)
    # Nhãn nguồn chỉ dùng để lưu evidence trên task đã gộp/tạo; không là URL
    # và không được đưa vào telemetry.
    source: str = Field(default="", max_length=64)
    expected_output: str | None = Field(default=None, max_length=10_000)
    acceptance_criteria: str | None = Field(default=None, max_length=10_000)
    context_input: str | None = Field(default=None, max_length=10_000)
    constraints: str | None = Field(default=None, max_length=10_000)
    execution_tool: str | None = Field(default=None, max_length=10_000)
    execution_method: str | None = Field(default=None, max_length=10_000)
    stated_priority: str | None = Field(default=None, max_length=32)
    stakeholders: list[str] | None = None
    deliver_to: str | None = Field(default=None, max_length=10_000)


class PageExtractionSummaryRequest(CamelModel):
    """Nội dung tab đang active mà extension lấy được (đã redact số thẻ/tài
    khoản dài phía client) — gửi lên để xử lý rule-based (không LLM, xem
    src/services/page_extraction.py) thành title/detail gợi ý cho task.
    Xem client/extension/entrypoints/sidepanel/App.tsx."""

    url: str = Field(..., min_length=1, max_length=2048)
    page_title: str = Field(default="", max_length=500)
    text: str = Field(..., min_length=1, max_length=20_000)
    # Nhãn nhận diện nguồn cụ thể hơn url/page_title khi trang là SPA route
    # tĩnh (vd Zalo web luôn ở chat.zalo.me bất kể đang mở nhóm nào) — client
    # tự đoán theo từng nền tảng (xem guessSourceContext() ở App.tsx), ví dụ
    # tên nhóm chat đang mở. Rỗng khi không đoán được, không bắt buộc.
    source_context: str = Field(default="", max_length=300)


class PageExtractionSuggestionItem(CamelModel):
    """Một việc-cần-làm nhận diện được (đường chính: LLM một lượt trên toàn
    đoạn, xem src/services/page_extraction.py). due_at chỉ được set khi
    resolve_due_at() parse chắc chắn được ngày/giờ/timezone từ text gốc
    (BR-05) — mơ hồ thì để trống, không đoán.

    source_url/source_label trả RIÊNG khỏi detail (trước đây bị nhét cứng vào
    cuối detail, chật và khó đọc trên panel hẹp — phản hồi người dùng
    2026-08-26) để client hiện thành link riêng. source_url luôn có giá trị;
    source_label chỉ có khi client đoán được nhãn cụ thể hơn url (vd tên
    nhóm chat — cần cho SPA route tĩnh như Zalo web).

    Các field bên dưới (expected_output...deliver_to) CHỈ điền khi text gốc
    nêu rõ — LLM tuyệt đối không tự suy ra/bịa cho đủ trường (cùng nguyên tắc
    BR-05 áp cho deadline). Rỗng là kết quả hợp lệ, không phải thiếu sót.
    Trả riêng (không gộp vào detail) để client hiện thành ô sửa riêng trước
    khi lưu — lúc lưu thật, client tự gộp lại vào detail (cùng source_url/
    source_label) vì bảng Task dùng chung nhiều pipeline khác không có cột
    riêng cho các field này (phạm vi cố ý giới hạn ở tab "Lấy dữ liệu" của
    extension)."""

    title: str
    detail: str
    due_at: datetime | None = None
    source_url: str = ""
    source_label: str = ""
    expected_output: str = ""
    constraint: str = ""
    execution_steps: list[str] = Field(default_factory=list)
    execution_tool: str = ""
    execution_method: str = ""
    priority: str = ""
    assignee: str = ""
    stakeholders: str = ""
    deliver_to: str = ""


class PageExtractionSummaryResponse(CamelModel):
    """Danh sách gợi ý do rule+LLM hybrid lọc ra — MỖI dòng khớp việc-cần-làm
    là MỘT suggestion riêng (không gộp vào một detail như trước) để người
    dùng confirm/bỏ từng cái. Không dòng nào khớp thì trả đúng 1 suggestion
    dùng nguyên text thô làm fallback. Xem/sửa ở extension trước khi bấm lưu
    thật từng cái qua POST /tasks/from-suggestion (endpoint này không tạo
    task, chỉ xử lý gợi ý)."""

    suggestions: list[PageExtractionSuggestionItem]


class TaskUpdateRequest(CamelModel):
    """Fields the user may adjust on a proposed task before approving it."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    detail: str | None = Field(default=None, max_length=10_000)
    due_at: datetime | None = None
    all_day: bool | None = None


class TaskCompletionRequest(CamelModel):
    """Thời lượng do người dùng tự báo khi hoàn tất task (ADR-018 QĐ-5)."""

    actual_minutes: int | None = Field(default=None, gt=0, le=24 * 60)


class TaskDraftActionResponse(CamelModel):
    id: int
    title: str
    detail: str = ""
    due_at: datetime | None = None
    all_day: bool = False
    status: Literal["proposed", "confirmed", "dismissed"]
    calendar_write_ready: bool = False
    calendar_event_id: str | None = None
    # True only when this draft came from an explicit request to create a
    # Calendar entry.  It lets the client offer one explicit approve-and-sync
    # action without turning ordinary task approval into a Calendar write.
    calendar_requested: bool = False
    # Nhãn nguồn hiện lên đầu thẻ ("Gmail", "Jira", "Nhiều nguồn"...). Thẻ task
    # trước đây không nói việc này từ đâu ra, nên nhìn thẻ không phân biệt được
    # việc lấy từ mail hay từ Jira. Rỗng khi task không còn bằng chứng nào
    # (người dùng tự tạo, hoặc nguồn đã bị gỡ kết nối) — thà để trống còn hơn
    # gán bừa một nền tảng.
    source_label: str = ""


ReminderStatus = Literal["scheduled", "cancelled"]
# FR-096: 3 lý do bỏ qua cố định — khớp DISMISS_REASONS trong src/services/reminders.py.
DismissReason = Literal["khong_can_nua", "da_lam_o_cho_khac", "han_chot_sai"]
# 6 loại thông báo chạy chung 1 pipe — khớp REMINDER_KINDS trong src/models/reminder.py.
ReminderKind = Literal[
    "task_due",
    "task_proposed",
    "conflict_schedule",
    "conflict_evidence",
    "daily_brief",
    "calendar_changed",
]


class ReminderResponse(CamelModel):
    id: int
    task_id: int | None = None
    kind: ReminderKind = "task_due"
    milestone: str
    scheduled_at: datetime
    status: ReminderStatus
    snooze_count: int
    dismiss_reason: str | None = None


class ReminderListResponse(CamelModel):
    reminders: list[ReminderResponse]


class NotificationTaskResponse(CamelModel):
    kind: ReminderKind
    title: str
    milestone: str
    task_id: int | None = None
    due_at: datetime | None = None
    evidence_deep_link: str | None = None
    # Dữ liệu riêng theo kind — vd conflict_schedule có otherTaskTitle, daily_brief
    # có dueSoonTasks/proposedCount. FE đọc theo kind, không ép chung 1 shape.
    payload: dict = Field(default_factory=dict)


class NotificationBundleResponse(CamelModel):
    bundle_key: str
    scheduled_at: datetime
    reminder_ids: list[int]
    tasks: list[NotificationTaskResponse]


class DueNotificationsResponse(CamelModel):
    notifications: list[NotificationBundleResponse]


class NotificationItemResponse(CamelModel):
    """1 dòng trong Trung tâm thông báo (web) — khác NotificationTaskResponse
    ở chỗ mang theo reminder_id + is_read, vì đây là danh sách phẳng cho
    người dùng lướt lại (đã đọc lẫn chưa đọc), không phải bundle chờ giao."""

    reminder_id: int
    kind: ReminderKind
    title: str
    milestone: str
    task_id: int | None = None
    due_at: datetime | None = None
    scheduled_at: datetime
    evidence_deep_link: str | None = None
    payload: dict = Field(default_factory=dict)
    is_read: bool


class NotificationListResponse(CamelModel):
    notifications: list[NotificationItemResponse]


class SnoozeReminderRequest(CamelModel):
    minutes: int | None = Field(default=None, ge=1, le=1440)


class DismissReminderRequest(CamelModel):
    reason: DismissReason


class RecordDeliveriesRequest(CamelModel):
    reminder_ids: list[int] = Field(..., min_length=1, max_length=50)


class RecordDeliveriesResponse(CamelModel):
    recorded: list[int]


class NotificationPreferenceResponse(CamelModel):
    timezone: str
    quiet_hours_start: int
    quiet_hours_end: int
    hourly_cap: int
    batch_window_minutes: int
    # NULL = tắt daily brief tự động — mặc định TẮT, người dùng tự bật (mục
    # "Daily brief tự động" trong src/services/reminders.py).
    daily_brief_hour: int | None = None
    # Bật/tắt kênh không sinh thêm thông báo; chỉ quyết định thông báo
    # đã sinh có được giao qua kênh tương ứng hay không.
    extension_enabled: bool = True
    telegram_enabled: bool = True
    web_push_enabled: bool = True
    # Giữ ReminderKind làm contract chung, bao gồm cả calendar_changed.
    muted_kinds: list[ReminderKind] = Field(default_factory=list)


class UpdateNotificationPreferenceRequest(CamelModel):
    """PATCH từng phần: field bỏ trống = giữ nguyên giá trị cũ.

    `daily_brief_hour` chỉ ÁP DỤNG khi có giá trị 0-23; muốn tắt daily brief
    phải gửi `disable_daily_brief=true` tường minh, không dùng None làm
    sentinel "xoá" — None ở đây nghĩa là "không đổi", không phải "tắt".

    `muted_kinds` thì ngược lại: khi client gửi field này thì thay nguyên danh
    sách; danh sách rỗng là thao tác bật lại mọi loại thông báo.
    """

    timezone: str | None = Field(default=None, max_length=64)
    daily_brief_hour: int | None = Field(default=None, ge=0, le=23)
    disable_daily_brief: bool = False
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)
    hourly_cap: int | None = Field(default=None, ge=1, le=20)
    batch_window_minutes: int | None = Field(default=None, ge=1, le=180)
    extension_enabled: bool | None = None
    telegram_enabled: bool | None = None
    web_push_enabled: bool | None = None
    muted_kinds: list[ReminderKind] | None = None


# Khớp ROUTINE_FREQUENCIES trong src/models/routine.py. "trigger" chưa làm —
# xem TODO(OD) ở đầu src/services/routines.py.
RoutineFrequency = Literal["daily", "every_other_day", "weekly", "monthly"]


class RoutineCreateRequest(CamelModel):
    name: str = Field(..., min_length=1, max_length=200)
    instructions: str = Field(..., min_length=1)
    frequency: RoutineFrequency = "daily"
    interval_days: int = Field(default=2, ge=1, le=31)
    hour: int = Field(default=7, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    # Bắt buộc có giá trị đúng khi frequency tương ứng — validate ở API layer,
    # không ép ràng buộc chéo field trong Pydantic để thông báo lỗi rõ ràng hơn.
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", max_length=64)
    # Chỉ lưu lựa chọn — CHƯA có delivery push/email thật đứng sau (xem
    # src/services/routines.py). Không phải field giả: giá trị được lưu đúng,
    # chỉ chưa có gì đọc nó để gửi.
    notify_push: bool = True
    notify_email: bool = False


class RoutineUpdateRequest(CamelModel):
    """PATCH từng phần: field bỏ trống (None) = giữ nguyên giá trị cũ."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str | None = Field(default=None, min_length=1)
    frequency: RoutineFrequency | None = None
    interval_days: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    enabled: bool | None = None
    notify_push: bool | None = None
    notify_email: bool | None = None


class RoutineResponse(CamelModel):
    id: int
    name: str
    instructions: str
    frequency: RoutineFrequency
    interval_days: int = 2
    hour: int
    minute: int = 0
    day_of_week: int | None = None
    day_of_month: int | None = None
    timezone: str
    enabled: bool
    notify_push: bool = True
    notify_email: bool = False
    last_run_date: str | None = None


class RoutineListResponse(CamelModel):
    routines: list[RoutineResponse]


class RoutineRunResponse(CamelModel):
    id: int
    routine_id: int
    status: str
    output_text: str | None = None
    output_json: dict | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    routine_name: str | None = None


class RoutineRunListResponse(CamelModel):
    runs: list[RoutineRunResponse]


class SendMessageResponse(CamelModel):
    conversation_id: int
    message_id: int
    response: str
    analysis: str = ""
    productivity_action: dict | None = None
    # Nguồn đã dùng để trả lời, dạng có cấu trúc để giao diện dựng link bấm được.
    # Rỗng nghĩa là lượt này không có nguồn nào kèm link, không phải là mất nguồn.
    sources: list[dict] = []
    task_drafts: list[TaskDraftActionResponse] = Field(default_factory=list)
    task_backlog_count: int = Field(default=0, ge=0)
    task_suggestions: list[TaskSuggestionAction] = Field(default_factory=list)


class MeetingNoteCreateRequest(CamelModel):
    title: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=200_000)
    transcript: str = Field(default="", max_length=200_000)
    project_id: int | None = None


class MeetingNoteUpdateRequest(CamelModel):
    """Mọi field đều optional: giao diện autosave chỉ gửi phần vừa đổi, gửi cả
    khối sẽ ghi đè mất phần người dùng đang gõ ở ô còn lại."""

    title: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=200_000)
    transcript: str | None = Field(default=None, max_length=200_000)


class MeetingActionItemResponse(CamelModel):
    id: int
    title: str
    detail: str
    assignee: str | None = None
    assignee_ambiguous: bool = True
    time_expression: str = ""
    due_at: datetime | None = None
    all_day: bool = False
    ambiguous: bool = False
    evidence_quote: str = ""
    status: Literal["suggested", "accepted", "dismissed"]
    task_id: int | None = None


class MeetingNoteResponse(CamelModel):
    id: int
    title: str
    notes: str
    transcript: str
    status: Literal["open", "summarized"]
    summary: str
    decisions: str
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    action_items: list[MeetingActionItemResponse] = Field(default_factory=list)
    project_id: int | None = None


class MeetingNoteListItemResponse(CamelModel):
    """Bản rút gọn cho màn hình danh sách — không trả notes/transcript vì một
    cuộc họp có thể dài hàng chục nghìn ký tự, kéo cả danh sách là lãng phí."""

    id: int
    title: str
    status: Literal["open", "summarized"]
    started_at: datetime
    ended_at: datetime | None = None
    updated_at: datetime
    action_item_count: int = 0
    open_action_item_count: int = 0


class MeetingNoteListResponse(CamelModel):
    meetings: list[MeetingNoteListItemResponse]


class PushPublicKeyResponse(CamelModel):
    """Khoá công khai VAPID cho trình duyệt. Rỗng nghĩa là máy chủ chưa cấu
    hình Web Push — client phải ẩn nút bật thông báo thay vì đăng ký hỏng."""

    public_key: str = ""
    enabled: bool = False


class PushSubscriptionKeys(CamelModel):
    """Đúng khối ``keys`` mà ``PushSubscription.toJSON()`` của trình duyệt trả
    về, giữ nguyên tên field để client gửi thẳng lên, không phải nắn lại."""

    p256dh: str = Field(..., min_length=1, max_length=255)
    auth: str = Field(..., min_length=1, max_length=255)


class PushSubscribeRequest(CamelModel):
    endpoint: str = Field(..., min_length=1, max_length=512)
    keys: PushSubscriptionKeys
    user_agent: str | None = Field(default=None, max_length=255)


class PushUnsubscribeRequest(CamelModel):
    endpoint: str = Field(..., min_length=1, max_length=512)


class PushSubscriptionResponse(CamelModel):
    """Không trả lại endpoint hay khoá: client đã có sẵn, còn máy chủ vọng lại
    bí mật giao vận là tăng số nơi có thể rò mà không đổi lại được gì."""

    subscribed: bool


class ConsentStateResponse(CamelModel):
    """Trạng thái một công tắc học. Thiếu dòng trong DB vẫn trả về mặc định tắt."""

    capability: str
    enabled: bool = False
    policy_version: str | None = None
    consented_at: datetime | None = None
    revoked_at: datetime | None = None


class ConsentListResponse(CamelModel):
    consents: list[ConsentStateResponse]


class ConsentUpdateRequest(CamelModel):
    capability: str
    enabled: bool


class LearningCandidateResponse(CamelModel):
    """Thẻ inbox "Mondaiy đã học gì" — chỉ payload có cấu trúc, không raw chat."""

    id: int
    candidate_key: str
    version: int
    candidate_type: str
    status: str
    payload: dict
    confidence: float | None = None
    expires_at: datetime | None = None
    created_at: datetime


class LearningCandidateListResponse(CamelModel):
    candidates: list[LearningCandidateResponse]


class CandidateRejectRequest(CamelModel):
    reason_codes: list[str] = Field(default_factory=list, max_length=8)


class LearningResetRequest(CamelModel):
    scope: Literal["style", "skills", "routines", "all"]


class LearningResetResponse(CamelModel):
    scope: str
    forgotten: int


class LearningAuditEventResponse(CamelModel):
    id: int
    actor: str
    action: str
    target_type: str
    target_ref: str
    reason_codes: list[str] = Field(default_factory=list)
    created_at: datetime


class LearningAuditListResponse(CamelModel):
    events: list[LearningAuditEventResponse]
