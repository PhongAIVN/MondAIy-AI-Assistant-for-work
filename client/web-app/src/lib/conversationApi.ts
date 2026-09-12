import { apiRequest } from './apiClient';
import { API_BASE_URL } from './apiClient';
import {
  streamConversationMessageRequest,
  type AgentStreamHandlers,
  type TaskDraftAction,
  type TaskSuggestionAction,
} from './agentStream';
import type { ProductivityAction } from '../types/conversation';

export type ServerConversation = {
  id: number;
  title: string;
  createdAt: string;
  updatedAt: string;
  isFavorite: boolean;
  messages: ServerConversationMessage[];
};

export type ServerConversationMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  extras?: Record<string, unknown> | null;
  feedback?: 'helpful' | 'partly' | 'incorrect' | null;
  createdAt: string;
};

export type ServerConversationSummary = {
  id: number;
  title: string;
  messageCount: number;
  /** Dự án chứa hội thoại; null = chưa xếp. Danh sách dùng nó để biết chỗ nào
   *  đáng hiện huy hiệu gợi ý. */
  projectId?: number | null;
  isFavorite: boolean;
  createdAt: string;
  updatedAt: string;
};

export type SendConversationResponse = {
  conversationId: number;
  messageId: number;
  response: string;
  analysis: string;
  productivityAction?: ProductivityAction | null;
  taskDrafts: TaskDraftAction[];
  taskBacklogCount: number;
  taskSuggestions: TaskSuggestionAction[];
};

export function createServerConversation(title: string, accessToken: string) {
  return apiRequest<ServerConversation>('/api/v1/conversations', {
    method: 'POST',
    accessToken,
    body: { initialQuestion: title.trim() },
  });
}

/** Danh sách phiên chat thật của user, mới nhất trước — nguồn duy nhất cho
 * sidebar lịch sử (KHÔNG đọc localStorage). */
export function listConversations(accessToken: string) {
  return apiRequest<{ conversations: ServerConversationSummary[] }>('/api/v1/conversations', { accessToken });
}

export function getConversationDetail(conversationId: number, accessToken: string) {
  return apiRequest<ServerConversation>(`/api/v1/conversations/${conversationId}`, { accessToken });
}

export function renameServerConversation(conversationId: number, title: string, accessToken: string) {
  return apiRequest<ServerConversationSummary>(`/api/v1/conversations/${conversationId}`, {
    method: 'PATCH',
    accessToken,
    body: { title },
  });
}

export function setConversationFavorite(conversationId: number, isFavorite: boolean, accessToken: string) {
  return apiRequest<ServerConversationSummary>(`/api/v1/conversations/${conversationId}/favorite`, {
    method: 'PATCH',
    accessToken,
    body: { isFavorite },
  });
}

export function deleteServerConversation(conversationId: number, accessToken: string) {
  return apiRequest<void>(`/api/v1/conversations/${conversationId}`, { method: 'DELETE', accessToken });
}

export function shareServerConversation(
  conversationId: number,
  visibility: 'private' | 'public',
  accessToken: string,
) {
  return apiRequest<{ visibility: 'private' | 'public'; publicUrl: string | null; publicToken: string | null }>(
    `/api/v1/conversations/${conversationId}/share`,
    { method: 'POST', accessToken, body: { visibility } },
  );
}

export function approveProductivityAction(
  conversationId: number,
  messageId: number,
  accessToken: string,
) {
  return apiRequest<ProductivityAction>(
    `/api/v1/conversations/${conversationId}/messages/${messageId}/productivity-action/approve`,
    { method: 'POST', accessToken },
  );
}

export function rejectProductivityAction(
  conversationId: number,
  messageId: number,
  accessToken: string,
) {
  return apiRequest<ProductivityAction>(
    `/api/v1/conversations/${conversationId}/messages/${messageId}/productivity-action/reject`,
    { method: 'POST', accessToken },
  );
}

export function updateMessageFeedback(
  conversationId: number,
  messageId: number,
  feedback: 'helpful' | 'partly' | 'incorrect',
  accessToken: string,
) {
  return apiRequest<void>(`/api/v1/conversations/${conversationId}/messages/${messageId}/feedback`, {
    method: 'PATCH',
    accessToken,
    body: { feedback },
  });
}

export function appendServerTurn(
  conversationId: number,
  role: 'user' | 'assistant',
  content: string,
  accessToken: string,
) {
  return apiRequest<ServerConversationMessage>(`/api/v1/conversations/${conversationId}/turns`, {
    method: 'POST',
    accessToken,
    body: { role, content },
  });
}

export function sendConversationMessage(
  conversationId: number,
  message: string,
  accessToken: string,
) {
  return apiRequest<SendConversationResponse>(`/api/v1/conversations/${conversationId}/messages`, {
    method: 'POST',
    accessToken,
    body: { message },
  });
}

export function streamConversationMessage(
  conversationId: number,
  message: string,
  accessToken: string,
  handlers: AgentStreamHandlers,
) {
  return streamConversationMessageRequest(API_BASE_URL, conversationId, message, accessToken, handlers);
}
