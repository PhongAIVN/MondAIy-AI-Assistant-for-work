import type { TaskImportFile } from '../fileIntake';

export const DEFAULT_API_URL = 'https://p004-api.duckdns.org';
export const API_REQUEST_TIMEOUT_MS = 15_000;

export const apiUrl = (path: string, baseUrl = process.env.EXPO_PUBLIC_API_URL || DEFAULT_API_URL): string =>
  `${baseUrl.replace(/\/$/, '')}${path}`;

export type Tokens = { accessToken: string; refreshToken: string };
export type AuthUser = { id: string; email: string; displayName: string; role: string; avatarUrl?: string | null };
export type Task = {
  id: number;
  title: string;
  detail: string;
  dueAt?: string | null;
  status: 'proposed' | 'confirmed' | 'completed' | 'dismissed' | 'cancelled' | string;
};
export type ChatReply = { response: string; sources?: Array<{ title?: string; url?: string }> };
export type ConversationSummary = { id: number; title: string; messageCount: number; createdAt: string; updatedAt: string };
export type ConversationMessage = { id: number; role: 'user' | 'assistant'; content: string; createdAt: string; feedback?: 'helpful' | 'partly' | 'incorrect' | null };
export type ConversationDetail = { id: number; title: string; createdAt: string; updatedAt: string; messages: ConversationMessage[] };
export type ConversationSendReply = { conversationId: number; messageId: number; response: string; sources?: Array<{ title?: string; url?: string }> };
export type RoutineFrequency = 'daily' | 'every_other_day' | 'weekly' | 'monthly';
export type Routine = { id: number; name: string; instructions: string; frequency: RoutineFrequency; intervalDays: number; hour: number; minute: number; dayOfWeek: number | null; dayOfMonth: number | null; timezone: string; enabled: boolean; notifyPush: boolean; notifyEmail: boolean; lastRunDate: string | null };
export type ConnectionStatus = { provider: 'discord' | 'google' | 'telegram' | 'jira' | 'outlook' | 'slack'; connected: boolean; accountLabel: string | null; expiresAt: string | null };
export type NotificationEntry = { reminderId: number; kind: string; title: string; milestone: string; taskId: number | null; dueAt: string | null; scheduledAt: string; payload?: Record<string, unknown>; isRead: boolean };
export type CalendarEvent = { id: string; calendarId: string; title: string; description: string; startAt: string; endAt: string | null; allDay: boolean; status: string; deepLink: string | null; syncedAt: string };
export type MeetingActionItem = { id: number; title: string; detail: string; assignee: string | null; status: 'suggested' | 'accepted' | 'dismissed'; taskId: number | null; dueAt: string | null; evidenceQuote: string };
export type MeetingNote = { id: number; title: string; notes: string; transcript: string; summary: string; decisions: string; status: 'open' | 'summarized'; startedAt: string; endedAt: string | null; createdAt: string; updatedAt: string; actionItems: MeetingActionItem[]; actionItemCount: number; openActionItemCount: number };
export type TaskImportProposal = { rowNumber: number; externalKey: string; title: string; detail: string; assignee: string | null; dueAt: string | null; allDay: boolean; status: string | null; matchedUser: boolean; needsConfirmation: boolean; source: string; sourceUrl: string };
export type TaskImportResponse = { fileNames: string[]; timezone: string; proposals: TaskImportProposal[]; agentResponse: string; agentAnalysis: string; agentWarning: string | null; searchedName: string; needsNameQuery: boolean; suggestedNames: string[] };

export class ApiConnectionError extends Error {
  constructor(message = 'Không thể kết nối tới Mondaiy.') {
    super(message);
    this.name = 'ApiConnectionError';
  }
}

export async function request<T>(path: string, options: RequestInit = {}, token?: string, timeoutMs = API_REQUEST_TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
    });
  } catch (caught) {
    if (controller.signal.aborted) {
      throw new ApiConnectionError('Mondaiy chưa phản hồi. Hãy kiểm tra mạng và thử lại.');
    }
    throw new ApiConnectionError();
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || 'Không thể kết nối tới Mondaiy.');
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadTaskImportFiles(files: TaskImportFile[], token: string, searchName = ''): Promise<TaskImportResponse> {
  const form = new FormData();
  files.forEach((file) => {
    form.append('files', { uri: file.uri, name: file.name, type: file.mimeType } as unknown as Blob);
  });
  if (searchName.trim()) form.append('search_name', searchName.trim());
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/excel/task-proposals'), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
      signal: controller.signal,
    });
  } catch (caught) {
    if (controller.signal.aborted) throw new ApiConnectionError('Mondaiy chưa phản hồi khi đọc tệp. Hãy thử lại.');
    throw new ApiConnectionError();
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || 'Không thể đọc tệp.');
  }
  return response.json() as Promise<TaskImportResponse>;
}

export const login = (email: string, password: string) =>
  request<Tokens>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
export const register = (email: string, password: string, displayName: string) =>
  request<Tokens>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify({ email, password, displayName }) });
export const forgotPassword = (email: string) =>
  request<{ message: string }>('/api/v1/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) });
export const refreshSession = (refreshToken: string) =>
  request<Tokens>('/api/v1/auth/refresh', { method: 'POST', body: JSON.stringify({ refreshToken }) });
export const googleLoginUrl = (redirectUri: string): string =>
  apiUrl(`/api/v1/auth/google/login?extRedirectUri=${encodeURIComponent(redirectUri)}`);
export const exchangeGoogleLoginCode = (code: string) =>
  request<Tokens>('/api/v1/auth/google/session', { method: 'POST', body: JSON.stringify({ code }) });
export const exchangeAppleIdentityToken = (identityToken: string, displayName: string, authorizationCode?: string | null) =>
  request<Tokens>('/api/v1/auth/apple/session', { method: 'POST', body: JSON.stringify({ identityToken, displayName, ...(authorizationCode ? { authorizationCode } : {}) }) });
export const getMe = (token: string) => request<AuthUser>('/api/v1/auth/me', {}, token);
export const deleteAccount = (password: string | undefined, token: string) =>
  request<void>('/api/v1/auth/me', { method: 'DELETE', body: JSON.stringify(password ? { password } : {}) }, token);
export const askAgent = (message: string, token: string) =>
  request<ChatReply>('/api/v1/chat', { method: 'POST', body: JSON.stringify({ message }) }, token);
export const listConversations = (token: string) =>
  request<{ conversations: ConversationSummary[] }>('/api/v1/conversations', {}, token);
export const createConversation = (title: string, token: string) =>
  request<ConversationDetail>('/api/v1/conversations', { method: 'POST', body: JSON.stringify({ title }) }, token);
export const getConversation = (id: number, token: string) =>
  request<ConversationDetail>(`/api/v1/conversations/${id}`, {}, token);
export const renameConversation = (id: number, title: string, token: string) =>
  request<ConversationSummary>(`/api/v1/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }, token);
export const deleteConversation = (id: number, token: string) =>
  request<void>(`/api/v1/conversations/${id}`, { method: 'DELETE' }, token);
export const sendConversationMessage = (id: number, message: string, token: string, imageData?: string | null) =>
  request<ConversationSendReply>(`/api/v1/conversations/${id}/messages`, { method: 'POST', body: JSON.stringify({ message, ...(imageData ? { imageData } : {}) }) }, token);
export const rateConversationMessage = (conversationId: number, messageId: number, feedback: 'helpful' | 'partly' | 'incorrect', token: string) =>
  request<void>(`/api/v1/conversations/${conversationId}/messages/${messageId}/feedback`, { method: 'PATCH', body: JSON.stringify({ feedback }) }, token);
export const listRoutines = (token: string) => request<{ routines: Routine[] }>('/api/v1/routines', {}, token);
export const createRoutine = (input: { name: string; instructions: string; frequency: RoutineFrequency; intervalDays?: number; hour: number; minute: number; dayOfWeek?: number; timezone: string; notifyPush: boolean; notifyEmail: boolean }, token: string) => request<Routine>('/api/v1/routines', { method: 'POST', body: JSON.stringify(input) }, token);
export const updateRoutine = (id: number, input: Partial<Routine>, token: string) => request<Routine>(`/api/v1/routines/${id}`, { method: 'PATCH', body: JSON.stringify(input) }, token);
export const getTasks = async (token: string): Promise<Task[]> => {
  const response = await request<{ tasks: Task[] }>('/api/v1/tasks', {}, token);
  return response.tasks;
};
export const confirmTask = (taskId: number, token: string) =>
  request<Task>(`/api/v1/tasks/${taskId}/confirm`, { method: 'POST' }, token);
export const createTaskFromSuggestion = (input: { title: string; detail?: string; dueAt?: string | null; allDay?: boolean }, token: string) =>
  request<Task>('/api/v1/tasks/from-suggestion', { method: 'POST', body: JSON.stringify(input) }, token);
export const updateTask = (taskId: number, input: { title?: string; detail?: string; dueAt?: string | null; allDay?: boolean }, token: string) =>
  request<Task>(`/api/v1/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(input) }, token);
export const dismissTask = (taskId: number, token: string) => request<Task>(`/api/v1/tasks/${taskId}/dismiss`, { method: 'POST' }, token);
export const completeTask = (taskId: number, token: string) => request<Task>(`/api/v1/tasks/${taskId}/complete`, { method: 'POST' }, token);
export const cancelTask = (taskId: number, token: string) => request<Task>(`/api/v1/tasks/${taskId}/cancel`, { method: 'POST' }, token);
export const syncTaskToCalendar = (taskId: number, token: string) => request<unknown>(`/api/v1/tasks/${taskId}/calendar-sync`, { method: 'POST' }, token);
export const getTaskCalendarHandoff = (taskId: number, token: string) => request<unknown>(`/api/v1/tasks/${taskId}/calendar-handoff`, {}, token);
export const listConnections = (token: string) => request<{ connections: ConnectionStatus[] }>('/api/v1/connections', {}, token);
export const createConnectionIntent = (provider: ConnectionStatus['provider'], extRedirectUri: string, token: string) =>
  request<{ authorizeUrl: string }>(`/api/v1/connections/${provider}/intent`, { method: 'POST', body: JSON.stringify({ extRedirectUri }) }, token);
export const disconnectConnection = (provider: ConnectionStatus['provider'], token: string) =>
  request<void>(`/api/v1/connections/${provider}/disconnect`, { method: 'POST' }, token);
export const listNotifications = (token: string) =>
  request<{ notifications: NotificationEntry[] }>('/api/v1/reminders/notifications?limit=50', {}, token);
export const listReminders = (token: string) => request<unknown>('/api/v1/reminders', {}, token);
export const snoozeReminder = (reminderId: number, minutes: number | undefined, token: string) => request<unknown>(`/api/v1/reminders/${reminderId}/snooze`, { method: 'POST', body: JSON.stringify(minutes ? { minutes } : {}) }, token);
export const dismissReminder = (reminderId: number, reason: string, token: string) => request<unknown>(`/api/v1/reminders/${reminderId}/dismiss`, { method: 'POST', body: JSON.stringify({ reason }) }, token);
export const getNotificationPreferences = (token: string) => request<unknown>('/api/v1/reminders/preferences', {}, token);
export const updateNotificationPreferences = (input: Record<string, unknown>, token: string) => request<unknown>('/api/v1/reminders/preferences', { method: 'PATCH', body: JSON.stringify(input) }, token);
export const listCalendarEvents = (timeFrom: string, timeTo: string, token: string) =>
  request<{ events: CalendarEvent[] }>(`/api/v1/calendar/events?timeFrom=${encodeURIComponent(timeFrom)}&timeTo=${encodeURIComponent(timeTo)}`, {}, token);
export const createCalendarEvent = (input: { calendarId?: string; title: string; description?: string; startAt: string; endAt?: string; allDay?: boolean }, token: string) => request<unknown>('/api/v1/calendar/events', { method: 'POST', body: JSON.stringify(input) }, token);
export const updateCalendarEvent = (eventId: string, input: { calendarId?: string; title?: string; description?: string; startAt?: string; endAt?: string; allDay?: boolean }, token: string) => request<unknown>(`/api/v1/calendar/events/${encodeURIComponent(eventId)}`, { method: 'PATCH', body: JSON.stringify(input) }, token);
export const deleteCalendarEvent = (eventId: string, token: string) => request<unknown>(`/api/v1/calendar/events/${encodeURIComponent(eventId)}`, { method: 'DELETE' }, token);
export const undoCalendarOperation = (operationId: number, token: string) => request<unknown>(`/api/v1/calendar/operations/${operationId}/undo`, { method: 'POST' }, token);
export const listMeetingNotes = (token: string) => request<{ meetings: MeetingNote[] }>('/api/v1/meeting-notes', {}, token);
export const getMeetingNote = (id: number, token: string) => request<MeetingNote>(`/api/v1/meeting-notes/${id}`, {}, token);
export const createMeetingNote = (input: { title?: string; notes?: string; transcript?: string }, token: string) => request<MeetingNote>('/api/v1/meeting-notes', { method: 'POST', body: JSON.stringify(input) }, token);
export const updateMeetingNote = (id: number, input: { title?: string; notes?: string; transcript?: string }, token: string) => request<MeetingNote>(`/api/v1/meeting-notes/${id}`, { method: 'PATCH', body: JSON.stringify(input) }, token);
export const deleteMeetingNote = (id: number, token: string) => request<void>(`/api/v1/meeting-notes/${id}`, { method: 'DELETE' }, token);
export const endMeetingNote = (id: number, token: string) => request<MeetingNote>(`/api/v1/meeting-notes/${id}/end`, { method: 'POST' }, token);
export const acceptMeetingActionItem = (noteId: number, itemId: number, token: string) => request<unknown>(`/api/v1/meeting-notes/${noteId}/action-items/${itemId}/accept`, { method: 'POST' }, token);
export const dismissMeetingActionItem = (noteId: number, itemId: number, token: string) => request<unknown>(`/api/v1/meeting-notes/${noteId}/action-items/${itemId}/dismiss`, { method: 'POST' }, token);
export const getRoutine = (id: number, token: string) => request<Routine>(`/api/v1/routines/${id}`, {}, token);
export const deleteRoutine = (id: number, token: string) => request<void>(`/api/v1/routines/${id}`, { method: 'DELETE' }, token);
export const runRoutineNow = (id: number, token: string) => request<unknown>(`/api/v1/routines/${id}/run-now`, { method: 'POST' }, token);
export const listRoutineRuns = (id: number, token: string) => request<unknown>(`/api/v1/routines/${id}/runs`, {}, token);
export const listIntegrations = (token: string) => request<unknown>('/api/v1/integrations', {}, token);
export const listIntegrationSources = (integrationId: number, token: string) => request<unknown>(`/api/v1/integrations/${integrationId}/sources`, {}, token);
