import { apiRequest } from './apiClient';

export type TaskStatus = 'proposed' | 'confirmed' | 'dismissed' | 'completed' | 'cancelled';

export type TaskEvidence = {
  id: number;
  messageId: number | null;
  provider: string;
  evidenceQuote: string;
  deepLink: string;
  hasAttachment: boolean;
};

export type Task = {
  id: number;
  clusterKey: string;
  title: string;
  detail: string;
  dueAt: string | null;
  allDay: boolean;
  ambiguous: boolean;
  assignee: string | null;
  assigneeAmbiguous: boolean;
  status: TaskStatus;
  sourceCount: number;
  signalStrength: number;
  calendarEventId: string | null;
  createdAt: string;
  completedAt: string | null;
  // Mốc vào thùng rác. NULL nghĩa là không nằm trong rác — task huỷ TRƯỚC
  // khi có cột này cũng NULL, và backend cố ý không bao giờ tự xoá chúng.
  cancelledAt: string | null;
  actualMinutes: number | null;
  updatedAt: string;
  evidence: TaskEvidence[];
  expectedOutput: string | null;
  acceptanceCriteria: string | null;
  contextInput: string | null;
  constraints: string | null;
  executionTool: string | null;
  executionMethod: string | null;
  statedPriority: string | null;
  stakeholders: string[] | null;
  deliverTo: string | null;
  estimateLowMin: number | null;
  estimateHighMin: number | null;
  deduplicated?: boolean;
  dedupLayer?: string | null;
};

export type TaskSuggestion = {
  title: string;
  detail: string;
  dueAt: string | null;
  allDay: boolean;
  assignee?: string | null;
  source: string;
};

export type CalendarInfo = {
  id: string;
  name: string;
  writable?: boolean;
};

export type CalendarEvent = {
  id: string;
  title: string;
  startAt: string;
  endAt: string | null;
  allDay: boolean;
  status: string;
  calendarId: string;
  calendarName: string;
  deepLink: string | null;
};

export type CalendarEventList = {
  calendars: CalendarInfo[];
  events: CalendarEvent[];
};

export type CalendarSyncResult = {
  taskId: number;
  calendarEventId: string;
  calendarUrl: string | null;
  alreadySynced: boolean;
};

export const listTasks = (accessToken: string, status?: TaskStatus): Promise<{ tasks: Task[] }> =>
  apiRequest(`/api/v1/tasks${status ? `?status=${status}` : ''}`, { accessToken });

export const confirmTask = (taskId: number, accessToken: string): Promise<Task> =>
  apiRequest(`/api/v1/tasks/${taskId}/confirm`, { method: 'POST', accessToken });

export const updateTask = (
  taskId: number,
  patch: { title?: string; detail?: string; dueAt?: string | null; allDay?: boolean },
  accessToken: string,
): Promise<Task> => apiRequest(`/api/v1/tasks/${taskId}`, { method: 'PATCH', accessToken, body: patch });

export const dismissTask = (taskId: number, accessToken: string): Promise<Task> =>
  apiRequest(`/api/v1/tasks/${taskId}/dismiss`, { method: 'POST', accessToken });

export const completeTask = (
  taskId: number,
  accessToken: string,
  actualMinutes?: number,
): Promise<Task> =>
  apiRequest(`/api/v1/tasks/${taskId}/complete`, {
    method: 'POST',
    accessToken,
    body: actualMinutes === undefined ? undefined : { actualMinutes },
  });

export const cancelTask = (taskId: number, accessToken: string): Promise<Task> =>
  apiRequest(`/api/v1/tasks/${taskId}/cancel`, { method: 'POST', accessToken });

/** Lấy task khỏi thùng rác. Backend đưa về 'proposed' và xoá mốc huỷ. */
export const restoreTask = (taskId: number, accessToken: string): Promise<Task> =>
  apiRequest(`/api/v1/tasks/${taskId}/restore`, { method: 'POST', accessToken });

export const createTaskFromSuggestion = (
  suggestion: TaskSuggestion,
  accessToken: string,
): Promise<Task> => apiRequest('/api/v1/tasks/from-suggestion', {
  method: 'POST',
  accessToken,
  body: {
    title: suggestion.title,
    detail: suggestion.detail,
    dueAt: suggestion.dueAt,
    allDay: suggestion.allDay,
    assignee: suggestion.assignee,
    source: suggestion.source,
  },
});

export const listCalendarEvents = (
  accessToken: string,
  timeFrom: string,
  timeTo: string,
): Promise<CalendarEventList> => {
  const params = new URLSearchParams({ timeFrom, timeTo });
  return apiRequest(`/api/v1/tasks/calendar-events?${params.toString()}`, { accessToken });
};

export type TaskBreakdownItem = {
  taskId: number;
  title: string;
  dueAt: string | null;
  shouldBreak: boolean;
  reason: string;
  steps: string[];
  contextNeeded: string[];
  aiPrompt: string;
};

export type TaskBreakdown = {
  generatedAt: string;
  summary: string;
  items: TaskBreakdownItem[];
};

export const buildTaskBreakdown = (accessToken: string): Promise<TaskBreakdown> =>
  apiRequest('/api/v1/tasks/breakdown', { method: 'POST', accessToken });

export const syncTaskToCalendar = (
  taskId: number,
  accessToken: string,
): Promise<CalendarSyncResult> =>
  apiRequest(`/api/v1/tasks/${taskId}/calendar-sync`, { method: 'POST', accessToken });
