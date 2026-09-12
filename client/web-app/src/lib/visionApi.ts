import type { TaskSuggestionAction } from './agentStream.js';
import { apiRequest } from './apiClient.js';

export type VisionActionResponse = {
  actionType: 'task' | 'calendar_event' | 'mixed' | 'unclear';
  response: string;
  analysis: string;
  sources: Array<Record<string, unknown>>;
  taskSuggestions: TaskSuggestionAction[];
  calendarSuggestions?: CalendarSuggestionAction[];
  warnings: string[];
  visualContextUsed: boolean;
};

export type CalendarSuggestionAction = {
  title: string;
  detail: string;
  startAt: string;
  endAt: string;
  allDay: boolean;
  source: string;
};

export type CalendarBatchWriteResponse = {
  created: Array<{ operationId: number }>;
  failed: Array<{ index: number; detail: string }>;
};

export async function createCalendarEventsBatch(
  accessToken: string,
  events: Array<Pick<CalendarSuggestionAction, 'title' | 'detail' | 'startAt' | 'endAt' | 'allDay'>>,
  calendarId = 'primary',
): Promise<CalendarBatchWriteResponse> {
  return apiRequest<CalendarBatchWriteResponse>('/api/v1/calendar/events/batch', {
    method: 'POST',
    accessToken,
    body: {
      calendarId,
      events: events.map((event) => ({
        title: event.title,
        description: event.detail,
        startAt: event.startAt,
        endAt: event.endAt,
        allDay: event.allDay,
      })),
    },
  });
}

export async function runVisionAction(
  apiBaseUrl: string,
  accessToken: string,
  imageDataUrl: string,
  message: string,
): Promise<VisionActionResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/vision/actions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ imageDataUrl, message }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || `Vision request failed (${response.status})`);
  }
  return await response.json() as VisionActionResponse;
}
