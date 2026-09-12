import { API_BASE_URL, apiRequest } from './apiClient';

export type BriefResponse = {
  id: number;
  runId: number;
  summary: string;
  topPriority: Array<{ taskId: number; title: string; dueAt: string | null }>;
  scheduleConflicts: Array<Record<string, unknown>>;
  evidence: Array<{
    messageId: string;
    threadId: string | null;
    source: string;
    sourceUrl: string;
    quote: string;
    importance: string;
    importanceScore: number;
    reasons: string[];
  }>;
  createdAt: string;
};

type RunResponse = { id: number; status: 'queued' | 'running' | 'succeeded' | 'failed'; errorMessage: string | null };

export function extractGmailDateRange(input: string): { timeFrom: string; timeTo: string } | null {
  const match = input.match(/(?:ngày\s*)?(\d{1,2})[-/](\d{1,2})[-/](\d{4})/i);
  if (!match) return null;
  const day = Number(match[1]); const month = Number(match[2]); const year = Number(match[3]);
  const start = new Date(year, month - 1, day);
  if (start.getFullYear() !== year || start.getMonth() !== month - 1 || start.getDate() !== day) return null;
  const end = new Date(start); end.setDate(end.getDate() + 1);
  return { timeFrom: start.toISOString(), timeTo: end.toISOString() };
}

export async function createGmailRun(
  accessToken: string,
  connectionId: number,
  sourceIds: string[],
  dateRange?: { timeFrom: string; timeTo: string } | null,
): Promise<RunResponse> {
  const end = new Date();
  const start = new Date(end.getTime() - 14 * 24 * 60 * 60 * 1000);
  return apiRequest<RunResponse>('/api/v1/runs', {
    method: 'POST',
    accessToken,
    body: {
      sources: sourceIds.map((sourceId) => ({ connectionId, sourceId })),
      timeFrom: dateRange?.timeFrom || start.toISOString(),
      timeTo: dateRange?.timeTo || end.toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      idempotencyKey: `gmail-brief-${Date.now()}`,
      mode: 'summary',
    },
  });
}

export async function waitForRun(accessToken: string, runId: number, signal?: AbortSignal): Promise<void> {
  const abortError = () => new DOMException('Aborted', 'AbortError');
  for (let attempt = 0; attempt < 180; attempt += 1) {
    if (signal?.aborted) throw abortError();
    const run = await apiRequest<RunResponse>(`/api/v1/runs/${runId}`, { accessToken, signal });
    if (run.status === 'succeeded') return;
    if (run.status === 'failed') throw new Error(run.errorMessage || 'Gmail briefing run failed.');
    if (signal?.aborted) throw abortError();
    await new Promise((resolve, reject) => {
      const timer = window.setTimeout(resolve, 1000);
      signal?.addEventListener(
        'abort',
        () => {
          window.clearTimeout(timer);
          reject(abortError());
        },
        { once: true },
      );
    });
  }
  throw new Error('Gmail briefing timed out while waiting for the backend.');
}

export async function getRunBrief(accessToken: string, runId: number): Promise<BriefResponse> {
  return apiRequest<BriefResponse>(`/api/v1/runs/${runId}/brief`, { accessToken });
}

export async function streamRunEvents(
  accessToken: string,
  runId: number,
  onEvent: (event: { node?: string; status?: string; message?: string | null; count?: number | null }) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/runs/${runId}/events`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok || !response.body) throw new Error('Unable to stream Gmail run events.');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.split('\n').find((value) => value.startsWith('data: '));
      if (!line) continue;
      try { onEvent(JSON.parse(line.slice(6))); } catch { /* ignore malformed SSE frame */ }
    }
  }
}
