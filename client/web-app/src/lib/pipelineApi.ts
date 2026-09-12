// Lớp gọi API cho trang /run.
//
// Backend thật đã có `/integrations`, `/runs`, `/runs/{id}/events`, `/tasks`,
// `/runs/{id}/brief` và Calendar handoff theo từng task.
//
// Mọi hàm báo lại transport ('live' | 'mock') để UI hiện băng cảnh báo — điều
// kiện dừng Checkpoint 3 là "không mock", nên trạng thái này phải nhìn thấy
// được chứ không im lặng.

import { API_BASE_URL, ApiError, apiRequest } from './apiClient';
import { loadCalendarHandoff, recordCalendarHandoffOpened } from './calendarHandoffClient';
import { MOCK_BRIEF, MOCK_NODE_COUNTS, MOCK_TASKS } from '../data/pipelineFixture';
import {
  DEFAULT_RUN_LIMITS,
  MOCK_SOURCE_PREFIX,
  PIPELINE_NODES,
  isMockSourceId,
  type Brief,
  type AutoSyncPreference,
  type CalendarHandoffRequest,
  type CalendarHandoffResponse,
  type ConnectionListResponse,
  type IntegrationListResponse,
  type IntegrationSourcesResponse,
  type RunCreateRequest,
  type RunLimits,
  type RunNodeEventPayload,
  type RunResponse,
  type Task,
  type TaskListResponse,
} from '../types/pipeline';

export type PipelineTransport = 'live' | 'mock';

/** Backend chưa dựng route thì trả các mã này — coi là "chưa có", không phải lỗi. */
const NOT_IMPLEMENTED_STATUS = [404, 405, 501];

const mockForced = (): boolean => import.meta.env.VITE_PIPELINE_MOCK === '1';

const isNotImplemented = (error: unknown): boolean =>
  error instanceof ApiError && NOT_IMPLEMENTED_STATUS.includes(error.status);

const sleep = (ms: number, signal?: AbortSignal): Promise<void> =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });

// --- Kết nối nguồn (màn Thư viện nguồn) ---

export const listConnections = (accessToken: string | null): Promise<ConnectionListResponse> =>
  apiRequest<ConnectionListResponse>('/api/v1/connections', { accessToken });

export const createConnectIntent = (
  provider: string,
  extRedirectUri: string,
  accessToken: string | null,
): Promise<{ authorizeUrl: string }> =>
  apiRequest<{ authorizeUrl: string }>(`/api/v1/connections/${provider}/intent`, {
    method: 'POST',
    body: { extRedirectUri },
    accessToken,
  });

export const disconnectProvider = (provider: string, accessToken: string | null): Promise<void> =>
  apiRequest<void>(`/api/v1/connections/${provider}/disconnect`, {
    method: 'POST',
    accessToken,
  });

// --- Integration + nguồn con (dùng khi chạy pipeline) ---

export const listIntegrations = (accessToken: string | null): Promise<IntegrationListResponse> =>
  apiRequest<IntegrationListResponse>('/api/v1/integrations', { accessToken });

/**
 * Đọc hạn mức Sync từ server để UI chặn ngay lúc người dùng tick nguồn.
 *
 * Backend cũ chưa có route này thì trả 404/405 — coi là "chưa có" và dùng
 * DEFAULT_RUN_LIMITS, đúng cách các hàm khác trong file này xử lý capability
 * chưa sẵn sàng. Không được để cả trang chọn nguồn chết chỉ vì thiếu hạn mức.
 */
export async function fetchRunLimits(accessToken: string | null): Promise<RunLimits> {
  try {
    return await apiRequest<RunLimits>('/api/v1/runs/limits', { accessToken });
  } catch (error) {
    if (isNotImplemented(error)) return DEFAULT_RUN_LIMITS;
    throw error;
  }
}

/** Đọc lựa chọn auto-sync của caller, tách khỏi trạng thái global hiệu lực. */
export const fetchAutoSyncPreference = (accessToken: string | null): Promise<AutoSyncPreference> =>
  apiRequest<AutoSyncPreference>('/api/v1/runs/auto-sync-preference', { accessToken });

/** Chỉ thay đổi công tắc consent của caller; không thể sửa nguồn hay config chung. */
export const updateAutoSyncPreference = (
  autoSyncEnabled: boolean,
  accessToken: string | null,
): Promise<AutoSyncPreference> =>
  apiRequest<AutoSyncPreference>('/api/v1/runs/auto-sync-preference', {
    method: 'PATCH',
    body: { autoSyncEnabled },
    accessToken,
  });

/** Nguồn giả dựng tại chỗ khi backend chưa liệt kê được nguồn con thật. */
const mockSource = (label: string) => ({
  id: `${MOCK_SOURCE_PREFIX}${label}`,
  name: 'Sample source',
  itemCount: null,
});

export type SourceListResult = {
  sources: IntegrationSourcesResponse['sources'];
  warnings?: string[];
  /** Lý do backend chưa liệt kê được nguồn thật; có giá trị thì `sources` là giả. */
  unsupported?: string;
};

/**
 * Liệt kê nguồn con của một integration (nhãn Gmail, Calendar, project Jira).
 *
 * Backend hỗ trợ Google (Gmail + Calendar) và Jira; Discord trả 400
 * (TAPB-130 chưa xong), upstream lỗi trả 502. Đây là capability chưa sẵn sàng,
 * không phải lỗi render của FE.
 *
 * Khi backend chưa liệt kê được, vẫn trả về một nguồn giả kèm lý do — nếu
 * không thì Discord không chọn được và cả trang đứng ở bước chọn nguồn.
 * Discord là nguồn Mức A duy nhất trong hai tuần build (Program Frame PF-04),
 * nên chặn ở đây là chặn luôn phần demo quan trọng nhất của Gate 2.
 */
export async function listIntegrationSources(
  integrationId: number,
  accessToken: string | null,
): Promise<SourceListResult> {
  if (mockForced()) {
    return { sources: [mockSource(String(integrationId))], unsupported: 'VITE_PIPELINE_MOCK=1' };
  }

  try {
    return await apiRequest<IntegrationSourcesResponse>(`/api/v1/integrations/${integrationId}/sources`, {
      accessToken,
    });
  } catch (error) {
    if (error instanceof ApiError && (error.status === 400 || error.status === 502)) {
      return { sources: [mockSource(String(integrationId))], unsupported: error.message };
    }
    throw error;
  }
}

// --- Việc đã trích xuất ---

export const listTasks = (accessToken: string | null): Promise<TaskListResponse> =>
  apiRequest<TaskListResponse>('/api/v1/tasks', { accessToken });

export const confirmTask = (taskId: number, accessToken: string | null): Promise<Task> =>
  apiRequest<Task>(`/api/v1/tasks/${taskId}/confirm`, { method: 'POST', accessToken });

export const dismissTask = (taskId: number, accessToken: string | null): Promise<Task> =>
  apiRequest<Task>(`/api/v1/tasks/${taskId}/dismiss`, { method: 'POST', accessToken });

// --- Chạy pipeline ---

export type RunOptions = {
  accessToken: string | null;
  signal: AbortSignal;
  onEvent: (event: RunNodeEventPayload) => void;
  onTransport: (transport: PipelineTransport, reason?: string) => void;
  onResult: (tasks: Task[], brief: Brief | null) => void;
};

/**
 * Tách stream SSE thành từng payload.
 *
 * Dùng fetch chứ không dùng EventSource vì EventSource không gắn được header
 * Authorization, mà nhét token vào query string thì token lọt vào access log.
 */
async function readSseStream(response: Response, onEvent: (event: RunNodeEventPayload) => void): Promise<void> {
  if (!response.body) throw new Error('Stream rỗng.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Khung SSE kết thúc bằng dòng trống; \r\n\r\n cho proxy chèn CR.
    let boundary = buffer.search(/\r?\n\r?\n/);
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary).replace(/^\r?\n\r?\n/, '');

      const data = frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');

      if (data) {
        try {
          onEvent(JSON.parse(data) as RunNodeEventPayload);
        } catch {
          onEvent({
            node: 'error',
            status: 'error',
            count: null,
            message: `Sự kiện SSE không phải JSON hợp lệ: ${data.slice(0, 120)}`,
            at: new Date().toISOString(),
          });
        }
      }

      boundary = buffer.search(/\r?\n\r?\n/);
    }
  }
}

async function runLive(request: RunCreateRequest, options: RunOptions): Promise<RunResponse> {
  const run = await apiRequest<RunResponse>('/api/v1/runs', {
    method: 'POST',
    body: request,
    accessToken: options.accessToken,
  });

  const response = await fetch(`${API_BASE_URL}/api/v1/runs/${run.id}/events`, {
    headers: {
      Accept: 'text/event-stream',
      ...(options.accessToken ? { Authorization: `Bearer ${options.accessToken}` } : {}),
    },
    signal: options.signal,
  });

  if (!response.ok) {
    throw new ApiError(response.status, `Could not open SSE: ${response.statusText}`);
  }

  await readSseStream(response, options.onEvent);

  // Việc và brief không đi qua SSE — lấy sau khi stream đóng.
  const { tasks } = await listTasks(options.accessToken);
  let brief: Brief | null = null;
  try {
    brief = await apiRequest<Brief>(`/api/v1/runs/${run.id}/brief`, { accessToken: options.accessToken });
  } catch (error) {
    // 404 nghĩa là run lỗi giữa chừng nên chưa có brief — không phải sự cố FE.
    if (!(error instanceof ApiError && error.status === 404)) throw error;
  }
  options.onResult(tasks, brief);

  return run;
}

async function runMock(options: RunOptions): Promise<RunResponse> {
  const { onEvent, signal } = options;

  for (const node of PIPELINE_NODES) {
    await sleep(node === 'extract_batch' || node === 'reduce' ? 700 : 260, signal);
    onEvent({
      node,
      status: 'ok',
      count: MOCK_NODE_COUNTS[node],
      message: null,
      at: new Date().toISOString(),
    });
  }

  onEvent({ node: 'done', status: 'ok', count: MOCK_TASKS.length, message: null, at: new Date().toISOString() });
  options.onResult(MOCK_TASKS, MOCK_BRIEF);

  return {
    id: 0,
    status: 'succeeded',
    errorMessage: null,
    createdAt: new Date().toISOString(),
  };
}

/** Tạo run, bơm event SSE ra ngoài, rồi trả việc + brief qua `onResult`. */
export async function runPipeline(request: RunCreateRequest, options: RunOptions): Promise<RunResponse> {
  if (mockForced()) {
    options.onTransport('mock', 'VITE_PIPELINE_MOCK=1');
    return runMock(options);
  }

  // Chọn nguồn giả thì cả lần chạy phải đi đường dữ liệu mẫu — gửi id giả lên
  // backend chỉ tạo ra một run chắc chắn lỗi.
  if (request.sources.some((source) => isMockSourceId(source.sourceId))) {
    options.onTransport('mock', 'Sample source selected because live nested sources are unavailable');
    return runMock(options);
  }

  try {
    const run = await runLive(request, options);
    options.onTransport('live');
    return run;
  } catch (error) {
    if (!isNotImplemented(error)) throw error;
    options.onTransport('mock', 'Backend /api/v1/runs is not available yet');
    return runMock(options);
  }
}

// --- Calendar handoff: chỉ gọi sau khi user bấm Xác nhận ---

const pad = (value: number): string => String(value).padStart(2, '0');

const toIcsStamp = (iso: string): string => {
  const d = new Date(iso);
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`
  );
};

const escapeIcsText = (value: string): string =>
  value.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r?\n/g, '\\n');

/** Gấp dòng ở 74 octet theo RFC 5545 — tiêu đề tiếng Việt rất dễ vượt ngưỡng. */
const foldIcsLine = (line: string): string => {
  const bytes = new TextEncoder().encode(line);
  if (bytes.length <= 74) return line;

  const chunks: string[] = [];
  let current = '';
  let currentBytes = 0;

  for (const char of line) {
    const size = new TextEncoder().encode(char).length;
    if (currentBytes + size > 74) {
      chunks.push(current);
      current = '';
      currentBytes = 0;
    }
    current += char;
    currentBytes += size;
  }
  if (current) chunks.push(current);

  return chunks.join('\r\n ');
};

function buildLocalIcs(request: CalendarHandoffRequest): CalendarHandoffResponse {
  const endsAt = request.endsAt ?? new Date(new Date(request.startsAt).getTime() + 60 * 60 * 1000).toISOString();
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//mondaiy//P-004 calendar handoff//VI',
    'BEGIN:VEVENT',
    `UID:task-${request.taskId}@mondaiy.local`,
    `DTSTAMP:${toIcsStamp(new Date().toISOString())}`,
    `DTSTART:${toIcsStamp(request.startsAt)}`,
    `DTEND:${toIcsStamp(endsAt)}`,
    `SUMMARY:${escapeIcsText(request.title)}`,
    ...(request.description ? [`DESCRIPTION:${escapeIcsText(request.description)}`] : []),
    'END:VEVENT',
    'END:VCALENDAR',
  ].map(foldIcsLine);

  const blob = new Blob([lines.join('\r\n')], { type: 'text/calendar;charset=utf-8' });
  return {
    taskId: request.taskId,
    icsUrl: URL.createObjectURL(blob),
    googleCalendarUrl: '',
    opened: false,
    openedAt: null,
    filename: `mondaiy-task-${request.taskId}.ics`,
  };
}

export async function createCalendarHandoff(
  request: CalendarHandoffRequest,
  accessToken: string | null,
  onTransport: (transport: PipelineTransport, reason?: string) => void,
): Promise<CalendarHandoffResponse> {
  if (mockForced()) {
    onTransport('mock', 'VITE_PIPELINE_MOCK=1');
    return buildLocalIcs(request);
  }

  const response = await loadCalendarHandoff({
    taskId: request.taskId,
    accessToken,
    apiRequest,
  });
  onTransport('live');
  return response;
}

export const markCalendarHandoffOpened = (
  taskId: number,
  accessToken: string | null,
): Promise<CalendarHandoffResponse> =>
  recordCalendarHandoffOpened(taskId, accessToken, apiRequest);
