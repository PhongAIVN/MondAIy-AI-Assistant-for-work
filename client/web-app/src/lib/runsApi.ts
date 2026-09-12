import { API_BASE_URL, ApiError, apiRequest } from './apiClient';

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export type SyncSourceRef = {
  connectionId: number;
  sourceId: string;
};

export type RunCreateRequest = {
  sources: SyncSourceRef[];
  timeFrom: string;
  timeTo: string;
  timezone: string;
  /** Ngôn ngữ title/summary/detail LLM viết cho lần Run này. */
  language: 'vi' | 'en';
  idempotencyKey: string;
};

export type Run = {
  id: number;
  status: RunStatus;
  errorMessage: string | null;
  createdAt: string;
};

export type RunNodeEvent = {
  node: string;
  /** 'item' chỉ xuất hiện ở node 'fetch' — báo tiến trình theo từng item
   * tải được, bắn liên tục trong lúc fetch còn chạy (không đợi node xong). */
  status: 'ok' | 'error' | 'item';
  count: number | null;
  message: string | null;
  at: string;
};

export type Brief = {
  id: number;
  runId: number;
  summary: string;
  topPriority: { taskId: number; title: string; dueAt: string | null }[];
  scheduleConflicts: unknown[];
  createdAt: string;
};

export const createRun = (body: RunCreateRequest, accessToken: string): Promise<Run> =>
  apiRequest('/api/v1/runs', { method: 'POST', body, accessToken });

export const getRun = (runId: number, accessToken: string): Promise<Run> =>
  apiRequest(`/api/v1/runs/${runId}`, { accessToken });

export const getRunBrief = (runId: number, accessToken: string): Promise<Brief> =>
  apiRequest(`/api/v1/runs/${runId}/brief`, { accessToken });

// EventSource không cho set header Authorization — dùng fetch + ReadableStream
// tự parse khung SSE "data: {...}\n\n".
export async function streamRunEvents(
  runId: number,
  accessToken: string,
  onEvent: (event: RunNodeEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/runs/${runId}/events`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, 'Could not open sync progress stream.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex = buffer.indexOf('\n\n');
    while (sepIndex !== -1) {
      const frame = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      const line = frame.split('\n').find((l) => l.startsWith('data:'));
      if (line) {
        onEvent(JSON.parse(line.slice(5).trim()) as RunNodeEvent);
      }
      sepIndex = buffer.indexOf('\n\n');
    }
  }
}

/** Kết quả hỏi server "câu chat này có cần kéo đồng bộ không". */
export type ChatSyncResult = {
  triggered: boolean;
  /** Lý do máy đọc (first_chat_of_day, recent_enough, no_sources...) — dùng để
   * debug, không phải câu chữ hiển thị cho người dùng. */
  reason: string;
  run: Run | null;
};

/**
 * Người dùng không còn bấm Sync tay (nút đã ẩn): mỗi câu chat đi qua đây, và
 * server quyết định có kéo đồng bộ hay không.
 *
 * Luật nằm hoàn toàn ở server (src/services/chat_sync.py) để web, mobile và
 * extension cư xử giống nhau, sửa luật không phải deploy lại từng client.
 *
 * Không bao giờ ném lỗi: câu chat vẫn phải trả lời được kể cả khi đồng bộ hỏng.
 */
export async function triggerChatSync(
  accessToken: string,
  message: string,
  language: string,
): Promise<ChatSyncResult> {
  try {
    return await apiRequest<ChatSyncResult>('/api/v1/runs/chat-trigger', {
      method: 'POST',
      accessToken,
      body: {
        message,
        language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      },
      // Ngắn hơn hẳn timeout mặc định: đây mới chỉ là câu hỏi "có cần đồng bộ
      // không". Backend chậm hay không với tới thì phải bỏ qua nhanh rồi trả
      // lời bằng dữ liệu sẵn có — không được giam câu chat của người dùng.
      timeoutMs: 8000,
    });
  } catch (error) {
    void error;
    return { triggered: false, reason: 'request_failed', run: null };
  }
}
