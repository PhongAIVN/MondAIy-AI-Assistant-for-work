export type CalendarHandoffPayload = {
  taskId: number;
  icsUrl: string;
  googleCalendarUrl: string;
  opened: boolean;
  openedAt: string | null;
};

export type CalendarHandoffBlockReason =
  | 'task_not_confirmed'
  | 'request_pending'
  | 'missing_due_at';

export function calendarHandoffBlockReason(
  taskStatus: string,
  dueAt: string | null,
  pending: boolean,
): CalendarHandoffBlockReason | null {
  if (taskStatus !== 'confirmed') return 'task_not_confirmed';
  if (pending) return 'request_pending';
  if (!dueAt) return 'missing_due_at';
  return null;
}

type ApiRequestOptions = {
  method?: 'GET' | 'POST';
  accessToken?: string | null;
};

type ApiRequest = <T>(path: string, options?: ApiRequestOptions) => Promise<T>;

type LoadCalendarHandoffOptions = {
  taskId: number;
  accessToken: string | null;
  apiRequest: ApiRequest;
  fetchIcs?: typeof fetch;
  createObjectUrl?: (blob: Blob) => string;
};

/**
 * Lấy handoff task-scoped rồi tải .ics bằng Bearer token. URL backend không
 * thể gắn thẳng vào thẻ <a> vì endpoint download vẫn được bảo vệ bởi auth.
 */
export async function loadCalendarHandoff({
  taskId,
  accessToken,
  apiRequest,
  fetchIcs = fetch,
  createObjectUrl = (blob) => URL.createObjectURL(blob),
}: LoadCalendarHandoffOptions): Promise<CalendarHandoffPayload & { filename: string }> {
  const handoff = await apiRequest<CalendarHandoffPayload>(
    `/api/v1/tasks/${taskId}/calendar-handoff`,
    { accessToken },
  );
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetchIcs(handoff.icsUrl, { headers });
  if (!response.ok) {
    throw new Error(response.statusText || 'Could not download calendar handoff');
  }

  return {
    ...handoff,
    icsUrl: createObjectUrl(await response.blob()),
    filename: `mondaiy-task-${taskId}.ics`,
  };
}

export function recordCalendarHandoffOpened(
  taskId: number,
  accessToken: string | null,
  apiRequest: ApiRequest,
): Promise<CalendarHandoffPayload> {
  return apiRequest<CalendarHandoffPayload>(
    `/api/v1/tasks/${taskId}/calendar-handoff/opened`,
    { method: 'POST', accessToken },
  );
}
