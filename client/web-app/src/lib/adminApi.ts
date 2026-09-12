// Client cho /api/v1/admin. Mọi endpoint ở đây đòi role admin ở phía server —
// ProtectedRoute chỉ chặn điều hướng, không phải quyền.
//
// Backend cố ý không trả nội dung cá nhân (PRD §4.4, §5) nên không type nào
// dưới đây có trường nội dung email/tin nhắn/câu hỏi/câu trả lời. Thêm trường
// như vậy là phải sửa cả src/api/admin.py và cân lại hai mục PRD đó trước.

import { apiRequest } from './apiClient';

export type AdminRole = 'participant' | 'mentor' | 'admin';
export type AdminProgramAccessLevel = 'A' | 'B' | 'C';

export type AdminOverview = {
  totalUsers: number;
  activeUsers: number;
  inactiveUsers: number;
  roles: { participant: number; mentor: number; admin: number };
  totalConnections: number;
  failedConnections: number;
  sourceHealthPercent: number;
  runsTotal: number;
  runsSucceeded: number;
  runsFailed: number;
  runsRunning: number;
  briefsGenerated: number;
  tasksProposed: number;
  tasksConfirmed: number;
  openConflicts: number;
  feedbackTotal: number;
  feedbackHelpful: number;
  windowDays: number;
  generatedAt: string;
};

export type AdminUserRow = {
  id: string;
  email: string;
  displayName: string;
  role: AdminRole;
  isActive: boolean;
  createdAt: string;
  lastSyncedAt: string | null;
  connectionCount: number;
  runCount: number;
  programAccessLevel: AdminProgramAccessLevel;
  programCohortSlug: string | null;
};

export type AdminUserList = {
  items: AdminUserRow[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminSourceHealth = {
  provider: string;
  total: number;
  connected: number;
  syncing: number;
  failed: number;
  lastSyncedAt: string | null;
};

export type AdminConnectionRow = {
  id: number;
  userId: string;
  userEmail: string;
  provider: string;
  status: string;
  initialSyncCompleted: boolean;
  connectedAt: string;
  lastSyncedAt: string | null;
  emailCount: number;
  lastError: string | null;
};

export type AdminSources = {
  providers: AdminSourceHealth[];
  connections: AdminConnectionRow[];
};

export type AdminRunRow = {
  id: number;
  userId: string;
  status: string;
  createdAt: string;
  sourcesCount: number;
  errorMessage: string | null;
};

export type AdminAuditRow = {
  id: number;
  action: string;
  objectType: string;
  objectId: string;
  actorType: string;
  actorId: string | null;
  versionLabel: string | null;
  details: Record<string, unknown> | null;
  createdAt: string;
};

export type AdminTelemetry = {
  windowDays: number;
  events: { name: string; count: number; avgDurationMs: number | null }[];
  feedback: { verdict: string; count: number }[];
};

export type AdminAppRating = {
  id: number;
  rating: number;
  feedback: string;
  trigger: string;
  createdAt: string;
};

export type AdminAppRatingSummary = {
  total: number;
  averageRating: number | null;
  distribution: { verdict: string; count: number }[];
  items: AdminAppRating[];
};

const query = (params: Record<string, string | number | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
};

export const getOverview = (accessToken: string, days = 7): Promise<AdminOverview> =>
  apiRequest<AdminOverview>(`/api/v1/admin/overview${query({ days })}`, { accessToken });

export const listUsers = (
  accessToken: string,
  params: {
    search?: string;
    role?: string;
    programAccessLevel?: AdminProgramAccessLevel;
    limit?: number;
    offset?: number;
  } = {},
): Promise<AdminUserList> =>
  apiRequest<AdminUserList>(`/api/v1/admin/users${query(params)}`, { accessToken });

export const updateUser = (
  accessToken: string,
  userId: string,
  patch: { role?: AdminRole; isActive?: boolean; programCohortSlug?: string },
): Promise<AdminUserRow> =>
  apiRequest<AdminUserRow>(`/api/v1/admin/users/${userId}`, {
    method: 'PATCH',
    body: patch,
    accessToken,
  });

export const getSources = (accessToken: string, limit = 100): Promise<AdminSources> =>
  apiRequest<AdminSources>(`/api/v1/admin/sources${query({ limit })}`, { accessToken });

export const listRuns = (
  accessToken: string,
  params: { status?: string; limit?: number } = {},
): Promise<{ items: AdminRunRow[]; total: number }> =>
  apiRequest(`/api/v1/admin/runs${query(params)}`, { accessToken });

// Body/response đi qua alias camelCase của Pydantic, nhưng query param thì
// không — FastAPI đọc đúng tên tham số Python. Nên `object_type` giữ snake_case.
export const listAudit = (
  accessToken: string,
  params: { action?: string; objectType?: string; limit?: number } = {},
): Promise<{ items: AdminAuditRow[]; total: number }> =>
  apiRequest(
    `/api/v1/admin/audit${query({
      action: params.action,
      object_type: params.objectType,
      limit: params.limit,
    })}`,
    { accessToken },
  );

export const getTelemetry = (accessToken: string, days = 7): Promise<AdminTelemetry> =>
  apiRequest<AdminTelemetry>(`/api/v1/admin/telemetry${query({ days })}`, { accessToken });

export const getAppRatings = (accessToken: string, days = 30): Promise<AdminAppRatingSummary> =>
  apiRequest<AdminAppRatingSummary>(`/api/v1/admin/app-ratings${query({ days })}`, { accessToken });

export type AdminAnnouncementAction = { title: string; kind: 'task' | 'calendar' | 'change' | 'resource'; dueAt: string | null; allDay: boolean; ambiguous: boolean; ambiguityReason: string | null };
export type AdminAnnouncementCategory = 'overview' | 'schedule' | 'policy' | 'submission' | 'support' | 'other';
export type AdminAnnouncementCandidate = { id: number; status: string; rawText: string; evidence: { sourceLevel: 'A'; channel?: string }; preview: { title: string; body: string; category: AdminAnnouncementCategory; aliases: string[]; items: AdminAnnouncementAction[]; timezone: string; extractionMethod: 'llm' | 'regex_fallback'; fallbackReason?: string | null }; informationItemId: number | null };
export const previewDiscordAnnouncement = (accessToken: string, body: { rawText: string; channel?: string; deepLink?: string | null; referenceDate?: string }) => apiRequest<AdminAnnouncementCandidate>('/api/v1/admin/discord-announcements/preview', { method: 'POST', body, accessToken });
export const publishDiscordAnnouncement = (accessToken: string, id: number, body: { title: string; category: AdminAnnouncementCategory; aliases: string[]; items: Array<Pick<AdminAnnouncementAction, 'title' | 'kind' | 'dueAt' | 'allDay'> > }) => apiRequest<AdminAnnouncementCandidate>(`/api/v1/admin/discord-announcements/${id}/publish`, { method: 'POST', body, accessToken });

// --- Lịch chương trình (ADR-010) ---
//
// Khác mọi type ở trên: các endpoint này CÓ trả nội dung (tiêu đề, mô tả mốc).
// Đó là dữ liệu chương trình do ban tổ chức soạn để phát cho học viên, không
// phải nội dung cá nhân của người dùng — ranh giới PRD §5 vẫn nguyên vẹn.

export type AdminProgramEventRow = {
  id: number;
  cohortSlug: string;
  externalId: string;
  eventType: 'custom' | 'daily_deadline' | 'weekly_deadline' | 'gate_deadline' | 'mentor_duty';
  visibility: 'program' | 'team';
  title: string;
  description: string;
  host: string | null;
  locationUrl: string | null;
  startAt: string;
  endAt: string | null;
  origin: 'feed' | 'admin';
  status: 'draft' | 'published' | 'archived';
  /** Trường đã sửa tay; lần nhập feed sau không ghi đè chúng. */
  lockedFields: string[];
  /** Feed đã đổi đúng một trường đang khoá — cần người chọn giữ bản nào. */
  sourceConflict: boolean;
  /** Bản gốc từ feed, để so với bản đang hiển thị. */
  feedPayload: Record<string, string | null> | null;
  updatedBy: string | null;
  updatedAt: string | null;
  publishedAt: string | null;
  /** Mutation metadata is returned inline by the backend row contract. */
  changedFields?: string[];
  notificationCount?: number;
};

export type AdminProgramEventList = {
  items: AdminProgramEventRow[];
  total: number;
  limit: number;
  offset: number;
  cohortSlug: string;
  conflictCount: number;
};

export type AdminProgramEventPatch = {
  title?: string;
  description?: string;
  eventType?: AdminProgramEventRow['eventType'];
  visibility?: AdminProgramEventRow['visibility'];
  host?: string | null;
  locationUrl?: string | null;
  startAt?: string;
  endAt?: string | null;
  /** Chỉ gửi khi admin chủ động muốn báo thay đổi lịch đã phát hành. */
  notifyUsers?: boolean;
  changeNote?: string;
  /** Chặn ghi đè khi một admin khác vừa sửa cùng mốc. */
  expectedUpdatedAt?: string | null;
};

export type AdminProgramEventMutationResult = {
  event: AdminProgramEventRow;
  changedFields: string[];
  notificationCount: number;
};

type AdminProgramEventApiResult = AdminProgramEventRow | AdminProgramEventMutationResult;

const normalizeProgramEventResult = (
  result: AdminProgramEventApiResult,
): AdminProgramEventMutationResult =>
  'event' in result
    ? result
    : {
        event: result,
        changedFields: result.changedFields ?? [],
        notificationCount: result.notificationCount ?? 0,
      };

export const listProgramEvents = (
  accessToken: string,
  params: { cohortSlug?: string; status?: string; conflictsOnly?: boolean; limit?: number } = {},
): Promise<AdminProgramEventList> =>
  apiRequest<AdminProgramEventList>(
    `/api/v1/admin/program-events${query({
      cohortSlug: params.cohortSlug,
      status: params.status,
      conflictsOnly: params.conflictsOnly ? 'true' : undefined,
      limit: params.limit,
    })}`,
    { accessToken },
  );

export const createProgramEvent = (
  accessToken: string,
  body: AdminProgramEventPatch & { title: string; startAt: string; cohortSlug?: string },
): Promise<AdminProgramEventMutationResult> =>
  apiRequest<AdminProgramEventApiResult>('/api/v1/admin/program-events', {
    method: 'POST',
    body,
    accessToken,
  }).then(normalizeProgramEventResult);

export const updateProgramEvent = (
  accessToken: string,
  eventId: number,
  patch: AdminProgramEventPatch,
): Promise<AdminProgramEventMutationResult> =>
  apiRequest<AdminProgramEventApiResult>(`/api/v1/admin/program-events/${eventId}`, {
    method: 'PATCH',
    body: patch,
    accessToken,
  }).then(normalizeProgramEventResult);

/** action: publish | unpublish | archive | revert-to-source */
export const actOnProgramEvent = (
  accessToken: string,
  eventId: number,
  action: 'publish' | 'unpublish' | 'archive' | 'revert-to-source',
  options: Pick<AdminProgramEventPatch, 'notifyUsers' | 'changeNote' | 'expectedUpdatedAt'> = {},
): Promise<AdminProgramEventMutationResult> =>
  apiRequest<AdminProgramEventApiResult>(`/api/v1/admin/program-events/${eventId}/${action}`, {
    method: 'POST',
    body: options,
    accessToken,
  }).then(normalizeProgramEventResult);

// --- Thông tin chương trình do đội ngũ xác minh ---

export type AdminProgramInformationStatus = 'draft' | 'published' | 'archived';
export type AdminProgramInformationCategory =
  | 'overview'
  | 'schedule'
  | 'policy'
  | 'submission'
  | 'support'
  | 'other';

export type AdminProgramInformationItem = {
  id: number;
  cohortSlug: string;
  category: AdminProgramInformationCategory;
  title: string;
  body: string;
  aliases: string[];
  sourceUrl: string | null;
  visibility: 'public' | 'program';
  status: AdminProgramInformationStatus;
  version: number;
  publishedVersion: number | null;
  updatedAt: string;
  publishedAt: string | null;
};

export type AdminProgramInformationList = {
  items: AdminProgramInformationItem[];
  total: number;
};

export type AdminProgramInformationPatch = {
  cohortSlug?: string;
  category?: AdminProgramInformationCategory;
  title?: string;
  body?: string;
  aliases?: string[];
  sourceUrl?: string | null;
  visibility?: AdminProgramInformationItem['visibility'];
  expectedVersion?: number;
};

export type AdminProgramInformationRequest = {
  id: number;
  sharedQuestion: string;
  status: 'open' | 'resolved';
  createdAt: string;
  resolvedItemId: number | null;
};

export type AdminProgramInformationRequestList = {
  items: AdminProgramInformationRequest[];
  total: number;
};

export const listProgramInformation = (
  accessToken: string,
  params: { status?: AdminProgramInformationStatus; limit?: number } = {},
): Promise<AdminProgramInformationList> =>
  apiRequest<AdminProgramInformationList>(
    `/api/v1/admin/program-information${query(params)}`,
    { accessToken },
  );

export const createProgramInformation = (
  accessToken: string,
  body: AdminProgramInformationPatch & { title: string; body: string },
): Promise<AdminProgramInformationItem> =>
  apiRequest<AdminProgramInformationItem>('/api/v1/admin/program-information', {
    method: 'POST',
    body,
    accessToken,
  });

export const updateProgramInformation = (
  accessToken: string,
  itemId: number,
  patch: AdminProgramInformationPatch,
): Promise<AdminProgramInformationItem> =>
  apiRequest<AdminProgramInformationItem>(`/api/v1/admin/program-information/${itemId}`, {
    method: 'PATCH',
    body: patch,
    accessToken,
  });

export const actOnProgramInformation = (
  accessToken: string,
  itemId: number,
  action: 'publish' | 'archive',
  expectedVersion: number,
): Promise<AdminProgramInformationItem> =>
  apiRequest<AdminProgramInformationItem>(
    `/api/v1/admin/program-information/${itemId}/${action}`,
    { method: 'POST', body: { expectedVersion }, accessToken },
  );

export const listProgramInformationRequests = (
  accessToken: string,
  params: { status?: 'open' | 'resolved'; limit?: number } = {},
): Promise<AdminProgramInformationRequestList> =>
  apiRequest<AdminProgramInformationRequestList>(
    `/api/v1/admin/program-information/human-requests${query(params)}`,
    { accessToken },
  );

export const resolveProgramInformationRequest = (
  accessToken: string,
  requestId: number,
  resolvedItemId: number,
  expectedVersion: number,
): Promise<AdminProgramInformationRequest> =>
  apiRequest<AdminProgramInformationRequest>(
    `/api/v1/admin/program-information/human-requests/${requestId}/resolve`,
    { method: 'POST', body: { itemId: resolvedItemId, expectedVersion }, accessToken },
  );
