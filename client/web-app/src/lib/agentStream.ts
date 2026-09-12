import type { ProductivityAction } from '../types/conversation.js';
export type TaskDraftAction = {
  id: number;
  title: string;
  detail?: string;
  dueAt: string | null;
  allDay: boolean;
  status: 'proposed' | 'confirmed' | 'dismissed';
  calendarWriteReady: boolean;
  calendarEventId: string | null;
  // Optional for historic conversation messages saved before this field existed.
  calendarRequested?: boolean;
  /** Nhãn nguồn hiện ở đầu thẻ ("Gmail", "Jira", "2 nguồn · Gmail, Jira").
   * Optional vì các tin nhắn cũ lưu trước khi có field này không có nó. */
  sourceLabel?: string;
};

export type TaskSuggestionAction = {
  title: string;
  detail: string;
  dueAt: string | null;
  allDay: boolean;
  assignee?: string | null;
  source: string;
};

/** Bằng chứng có thể mở trực tiếp từ câu trả lời grounded. */
export type AgentSourceCitation = {
  tool?: string;
  title?: string;
  url: string;
  occurred_at?: string;
};

export type AgentStreamReply = {
  response: string;
  analysis: string;
  messageId?: number;
  productivityAction?: ProductivityAction;
  taskDrafts: TaskDraftAction[];
  taskBacklogCount?: number;
  taskSuggestions: TaskSuggestionAction[];
  groundingStatus?: 'grounded' | 'uncertain' | 'abstain' | 'reject';
  programQuestionHandoffEligible?: boolean;
  sources?: AgentSourceCitation[];
};

export type AgentProgressPhase = 'thinking' | 'calling' | 'observing' | 'responding';

export type AgentProgressEvent = {
  phase: AgentProgressPhase;
  tool?: string;
};

export type AgentStreamHandlers = {
  onToken: (delta: string) => void;
  onProgress?: (progress: AgentProgressEvent) => void;
  onDone?: (reply: AgentStreamReply) => void;
  signal?: AbortSignal;
};

export class AgentStreamError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'AgentStreamError';
    this.status = status;
  }
}

async function responseError(response: Response): Promise<AgentStreamError> {
  let message = response.statusText || 'Unable to open agent response stream.';
  try {
    const payload = await response.json() as { detail?: string };
    if (typeof payload.detail === 'string') message = payload.detail;
  } catch {
    // Some proxies return an empty or non-JSON error page.
  }
  return new AgentStreamError(response.status, message);
}

async function streamSseRequest(
  url: string,
  message: string,
  accessToken: string,
  handlers: AgentStreamHandlers,
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ message }),
    signal: handlers.signal,
  });
  if (!response.ok) throw await responseError(response);
  if (!response.body) throw new AgentStreamError(response.status, 'Agent response stream is empty.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.search(/\r?\n\r?\n/);
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary).replace(/^\r?\n\r?\n/, '');
      const event = frame.match(/^event:\s*(\S+)/m)?.[1];
      const data = frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');
      if (data) {
        const payload = JSON.parse(data) as {
          delta?: string;
          response?: string;
          analysis?: string;
          message?: string;
          phase?: AgentProgressPhase;
          tool?: string;
          messageId?: number;
          productivityAction?: ProductivityAction;
          taskDrafts?: TaskDraftAction[];
          taskBacklogCount?: number;
          taskSuggestions?: TaskSuggestionAction[];
          groundingStatus?: AgentStreamReply['groundingStatus'];
          programQuestionHandoffEligible?: boolean;
          sources?: AgentSourceCitation[];
        };
        if (event === 'progress' && payload.phase) {
          handlers.onProgress?.({ phase: payload.phase, tool: payload.tool });
        }
        if (event === 'token' && payload.delta) handlers.onToken(payload.delta);
        if (event === 'error') throw new Error(payload.message || 'Agent stream failed.');
        if (event === 'done') {
          handlers.onDone?.({
            response: payload.response || '',
            analysis: payload.analysis || '',
            messageId: payload.messageId,
            productivityAction: payload.productivityAction,
            taskDrafts: payload.taskDrafts || [],
            taskBacklogCount: payload.taskBacklogCount || 0,
            taskSuggestions: payload.taskSuggestions || [],
            groundingStatus: payload.groundingStatus,
            programQuestionHandoffEligible: payload.programQuestionHandoffEligible,
            sources: payload.sources || [],
          });
        }
      }
      boundary = buffer.search(/\r?\n\r?\n/);
    }
  }
}

export async function streamAgentRequest(
  apiBaseUrl: string,
  message: string,
  accessToken: string,
  handlers: AgentStreamHandlers,
): Promise<void> {
  return streamSseRequest(`${apiBaseUrl}/api/v1/chat/stream`, message, accessToken, handlers);
}

/** Stream a persisted conversation message; the server saves both turns on done. */
export async function streamConversationMessageRequest(
  apiBaseUrl: string,
  conversationId: number,
  message: string,
  accessToken: string,
  handlers: AgentStreamHandlers,
): Promise<void> {
  return streamSseRequest(
    `${apiBaseUrl}/api/v1/conversations/${conversationId}/messages/stream`,
    message,
    accessToken,
    handlers,
  );
}
