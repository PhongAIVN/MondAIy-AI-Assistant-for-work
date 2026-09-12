import { API_BASE_URL, ApiError, apiRequest } from './apiClient.ts';
import { streamAgentRequest, type AgentStreamHandlers } from './agentStream';

export type AgentReply = {
  response: string;
  analysis: string;
};

/**
 * Gọi agent thật ở backend.
 *
 * Câu trả lời là văn xuôi, không có các trường summary/whatChanged/source như
 * dữ liệu mock. Giao diện phải chịu được cả hai dạng: mock cũ có cấu trúc, và
 * câu trả lời thật chỉ có text.
 */
export async function askAgent(message: string, accessToken: string): Promise<AgentReply> {
  return apiRequest<AgentReply>('/api/v1/chat', {
    method: 'POST',
    accessToken,
    body: { message },
  });
}

/** Stream agent text via fetch + SSE; EventSource cannot attach Bearer auth. */
export async function streamAgent(
  message: string,
  accessToken: string,
  handlers: AgentStreamHandlers,
): Promise<void> {
  try {
    await streamAgentRequest(API_BASE_URL, message, accessToken, handlers);
  } catch (error) {
    if (error instanceof Error && error.message === 'Unable to open agent response stream.') {
      throw new ApiError(0, error.message);
    }
    throw error;
  }
}
