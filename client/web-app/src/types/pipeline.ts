// Hình dạng dữ liệu của backend thật, khớp `src/models/schemas.py` và
// `src/api/{integrations,runs,tasks}.py` tại commit `bad686d`.
//
// Backend trả camelCase (CamelModel dùng alias_generator=to_camel), nên tên
// field ở đây trùng nguyên văn với response JSON. Đổi schema Python thì phải
// đổi file này và docs/projects/engineering/api-contract-pipeline.md cùng lúc.

export type ConnectionProvider = 'discord' | 'google' | 'telegram' | 'jira' | 'outlook' | 'slack';

/** Một Google OAuth connection phục vụ cả Gmail và Calendar. */
export const PROVIDER_LABEL: Record<ConnectionProvider, string> = {
  discord: 'Discord',
  google: 'Google',
  telegram: 'Telegram',
  jira: 'Jira',
  outlook: 'Outlook',
  slack: 'Slack',
};

/**
 * Mức độ đáng tin của nguồn, lấy từ
 * `docs/projects/engineering/program-frame.md` mục 5.
 *
 * `A` là nguồn chính thức — nơi người điều hành chương trình công bố.
 * `B` là nguồn phụ — nơi chính người dùng ghi lại cách họ hiểu.
 *
 * Đổi bảng này là đổi cách hệ thống phân xử khi hai nguồn nói khác nhau, nên
 * phải sửa Program Frame trước rồi mới sửa ở đây.
 *
 * `telegram` không có mức vì nằm ngoài năm nguồn ADR-002 (open item PF-01).
 */
export type SourceLevel = 'A' | 'B';

export const SOURCE_LEVEL: Partial<Record<ConnectionProvider, SourceLevel>> = {
  discord: 'A',
  google: 'B',
  jira: 'A',
  // Cùng vai trò với Gmail — hộp thư cá nhân, không phải kênh chính thức
  // của chương trình (ADR-013).
  outlook: 'B',
};

/**
 * Provider được phép hiện trên giao diện.
 *
 * `telegram` nằm ngoài năm nguồn ADR-002 nên bị ẩn. Mã backend
 * (`src/api/connections.py`, `src/services/connections/telegram.py`) vẫn còn
 * nguyên — muốn mở lại thì thêm `'telegram'` vào mảng này **sau khi** có ADR
 * mới, vì thêm nguồn là thay đổi về quyền riêng tư.
 *
 * `jira` đã nằm trong 5 nguồn ADR-002, không cần ADR mới — nhưng nút Connect
 * Jira chỉ thật sự chạy được sau khi có `JIRA_CLIENT_ID`/`JIRA_CLIENT_SECRET`
 * (đăng ký app trên Atlassian Developer Console), xem
 * `docs/projects/engineering/jira-connector-plan.md`.
 *
 * `outlook` được duyệt qua ADR-013 (connector đọc email thứ hai, song song
 * Gmail) — nút Connect Outlook chỉ chạy được sau khi có
 * `MICROSOFT_CLIENT_ID`/`MICROSOFT_CLIENT_SECRET` (App Registration trên
 * Azure Portal), xem `docs/projects/engineering/adr/adr-013-outlook-connector-doc-email.md`.
 *
 * `slack` bật theo quyết định PM ghi ở ADR-016 (xem
 * docs/projects/engineering/adr/adr-016-slack-connector-pilot-scope.md):
 * user tự chọn channel/DM để ingest (giống Jira/Gmail source picker), DM
 * bật ngay, app chỉ cài nội bộ 1 workspace do mondaiy quản trị (giữ rate
 * limit Tier 3 internal, không cần Slack App Directory review). Backend
 * connector (`src/connectors/slack.py`, `src/services/slack_rules.py`) đã
 * build xong theo docs/projects/engineering/slack-detail.drawio (DRAFT).
 * Còn thiếu `SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` thật (xem
 * `src/config.py`) — nút Connect Slack chỉ chạy được sau khi có Slack App
 * thật, giống cơ chế `jira`/`outlook` đang chờ credentials.
 */
export const ENABLED_PROVIDERS: ConnectionProvider[] = ['discord', 'google', 'jira', 'outlook', 'slack'];

/** Telegram là kênh giao thông báo/điều khiển, không phải nguồn ingestion. */
export const CONNECTABLE_PROVIDERS: ConnectionProvider[] = [...ENABLED_PROVIDERS, 'telegram'];

export const isEnabledProvider = (provider: ConnectionProvider): boolean =>
  ENABLED_PROVIDERS.includes(provider);

export const isConnectableProvider = (provider: ConnectionProvider): boolean =>
  CONNECTABLE_PROVIDERS.includes(provider);

/**
 * Tiền tố đánh dấu nguồn giả do FE tự dựng khi backend chưa liệt kê được nguồn
 * con thật. Chọn nguồn này thì cả lần chạy đi theo đường dữ liệu mẫu.
 */
export const MOCK_SOURCE_PREFIX = 'mock:';

export const isMockSourceId = (sourceId: string): boolean => sourceId.startsWith(MOCK_SOURCE_PREFIX);

// --- GET /api/v1/connections (dùng cho màn kết nối/ngắt kết nối) ---

export type ConnectionStatus = {
  provider: ConnectionProvider;
  connected: boolean;
  accountLabel?: string | null;
  expiresAt?: string | null;
};

export type ConnectionListResponse = {
  connections: ConnectionStatus[];
};

// --- GET /api/v1/integrations (dùng cho chọn nguồn khi chạy pipeline) ---

/** Khác `ConnectionStatus` ở chỗ có `id` — `POST /runs` cần id này. */
export type Integration = {
  id: number;
  provider: ConnectionProvider;
  accountLabel?: string | null;
  expiresAt?: string | null;
};

export type IntegrationListResponse = {
  integrations: Integration[];
};

/** Một nguồn con trong integration: nhãn Gmail, Google Calendar, project Jira. */
export type SourceInfo = {
  id: string;
  name: string;
  itemCount?: number | null;
};

export type IntegrationSourcesResponse = {
  sources: SourceInfo[];
  /** Connector con bị lỗi trong khi các connector khác vẫn dùng được. */
  warnings: string[];
};

// --- POST /api/v1/runs ---

export type SyncSourceRef = {
  connectionId: number;
  sourceId: string;
};

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';

/** Hạn mức Sync do server quyết (GET /runs/limits) — FE không được tự đoán. */
export type RunLimits = {
  maxSyncSources: number;
  maxSyncRangeDays: number;
  /** Đã là AND của công tắc tổng phía server và công tắc riêng của user. */
  autoSyncEnabled: boolean;
  autoSyncIntervalMinutes: number;
};

/** Lựa chọn auto-sync đã lưu và trạng thái hiệu lực sau công tắc vận hành. */
export type AutoSyncPreference = {
  autoSyncEnabled: boolean;
  userAutoSyncEnabled: boolean;
  autoSyncIntervalMinutes: number;
};

/** Dùng khi chưa gọi được /runs/limits: khớp default trong src/config.py. */
export const DEFAULT_RUN_LIMITS: RunLimits = {
  maxSyncSources: 10,
  maxSyncRangeDays: 31,
  autoSyncEnabled: false,
  autoSyncIntervalMinutes: 180,
};

export type RunCreateRequest = {
  sources: SyncSourceRef[];
  /** ISO 8601 có offset. Backend cần offset thật để node resolve tính giờ. */
  timeFrom: string;
  timeTo: string;
  /** IANA timezone, ví dụ Asia/Ho_Chi_Minh. */
  timezone: string;
  /** Ngôn ngữ title/summary/detail LLM viết cho lần Run này — theo ngôn ngữ
   * app đang hiển thị lúc bấm Sync, không phải cấu hình cố định. */
  language: 'vi' | 'en';
  /** Bấm hai lần cùng key thì backend trả lại run cũ, không chạy lại. */
  idempotencyKey: string;
};

export type RunResponse = {
  id: number;
  status: RunStatus;
  errorMessage?: string | null;
  createdAt: string;
};

// --- GET /api/v1/runs/{id}/events (SSE) ---

/** Chín node của LangGraph, đúng thứ tự chạy. */
export const PIPELINE_NODES = [
  'fetch',
  'normalize',
  'filter',
  'make_batches',
  'extract_batch',
  'resolve',
  'cluster',
  'reduce',
  'persist',
] as const;

export type PipelineNode = (typeof PIPELINE_NODES)[number];

/**
 * Payload SSE. `node` có thể là một trong chín node, hoặc hai giá trị canh
 * biên mà `src/api/runs.py` bắn ra: `done` khi chạy xong, `error` khi pipeline
 * chết giữa chừng. `status` chỉ có `ok` và `error` — không có `running`, nên
 * node đang chạy được suy ra từ node kế tiếp chưa có event.
 */
export type RunNodeEventPayload = {
  node: PipelineNode | 'done' | 'error';
  status: 'ok' | 'error';
  count: number | null;
  message: string | null;
  at: string;
};

/** Trạng thái UI cho một node, dựng từ chuỗi event nhận được. */
export type PipelineNodeStatus = 'pending' | 'running' | 'done' | 'error';

export type PipelineNodeProgress = {
  node: PipelineNode;
  status: PipelineNodeStatus;
  count?: number | null;
  message?: string | null;
};

// --- GET /api/v1/tasks ---

/** Chỉ đi được từ `proposed`; backend trả 409 nếu chuyển trạng thái lần hai. */
export type TaskStatus = 'proposed' | 'confirmed' | 'dismissed';

export type TaskEvidence = {
  id: number;
  messageId: number | null;
  provider: string;
  /** Trích nguyên văn câu chứa tín hiệu việc cần làm. */
  evidenceQuote: string;
  deepLink: string;
  /** Nguồn gốc (message) có đính kèm file hay không. */
  hasAttachment: boolean;
};

export type Task = {
  id: number;
  clusterKey: string;
  title: string;
  detail: string;
  dueAt: string | null;
  allDay: boolean;
  /** Node resolve không chắc mốc thời gian — UI phải cảnh báo. */
  ambiguous: boolean;
  status: TaskStatus;
  /** Số message độc lập cùng nói về việc này. */
  sourceCount: number;
  signalStrength: number;
  calendarEventId: string | null;
  createdAt: string;
  updatedAt: string;
  evidence: TaskEvidence[];
};

export type TaskListResponse = {
  tasks: Task[];
};

// --- GET /api/v1/runs/{id}/brief ---

export type BriefPriority = {
  taskId: number;
  title: string;
  dueAt: string | null;
};

export type Brief = {
  id: number;
  runId: number;
  summary: string;
  topPriority: BriefPriority[];
  /** P0 chưa triển khai thuật toán đối chiếu task/event nên vẫn rỗng. */
  scheduleConflicts: unknown[];
  createdAt: string;
};

// --- Calendar handoff ---

export type CalendarHandoffRequest = {
  taskId: number;
  title: string;
  startsAt: string;
  endsAt?: string;
  description?: string;
  timezone: string;
};

export type CalendarHandoffResponse = {
  taskId: number;
  icsUrl: string;
  googleCalendarUrl: string;
  opened: boolean;
  openedAt: string | null;
  /** Chỉ có ở FE sau khi tải .ics có xác thực thành object URL. */
  filename?: string;
};
