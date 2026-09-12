import { apiRequest } from './apiClient';
import type { Task } from './tasksApi';

export type MeetingNoteStatus = 'open' | 'summarized';
export type MeetingActionItemStatus = 'suggested' | 'accepted' | 'dismissed';

export type MeetingActionItem = {
  id: number;
  title: string;
  detail: string;
  assignee: string | null;
  assigneeAmbiguous: boolean;
  timeExpression: string;
  dueAt: string | null;
  allDay: boolean;
  ambiguous: boolean;
  evidenceQuote: string;
  status: MeetingActionItemStatus;
  taskId: number | null;
};

export type MeetingNote = {
  id: number;
  title: string;
  notes: string;
  transcript: string;
  status: MeetingNoteStatus;
  summary: string;
  decisions: string;
  startedAt: string;
  endedAt: string | null;
  createdAt: string;
  updatedAt: string;
  actionItems: MeetingActionItem[];
};

/** Bản rút gọn cho danh sách — không kèm notes/transcript. */
export type MeetingNoteListItem = {
  id: number;
  title: string;
  status: MeetingNoteStatus;
  startedAt: string;
  endedAt: string | null;
  updatedAt: string;
  actionItemCount: number;
  openActionItemCount: number;
};

export const listMeetingNotes = (accessToken: string): Promise<{ meetings: MeetingNoteListItem[] }> =>
  apiRequest('/api/v1/meeting-notes', { accessToken });

export const createMeetingNote = (
  accessToken: string,
  payload: { title?: string; notes?: string; transcript?: string } = {},
): Promise<MeetingNote> =>
  apiRequest('/api/v1/meeting-notes', { method: 'POST', accessToken, body: payload });

export const getMeetingNote = (id: number, accessToken: string): Promise<MeetingNote> =>
  apiRequest(`/api/v1/meeting-notes/${id}`, { accessToken });

/**
 * Chỉ gửi field vừa đổi. Gửi cả khối sẽ ghi đè phần người dùng đang gõ ở ô còn
 * lại khi hai lần autosave chồng lên nhau.
 */
export const updateMeetingNote = (
  id: number,
  accessToken: string,
  payload: { title?: string; notes?: string; transcript?: string },
): Promise<MeetingNote> =>
  apiRequest(`/api/v1/meeting-notes/${id}`, { method: 'PATCH', accessToken, body: payload });

export const deleteMeetingNote = (id: number, accessToken: string): Promise<void> =>
  apiRequest(`/api/v1/meeting-notes/${id}`, { method: 'DELETE', accessToken });

/** Kết thúc cuộc họp: backend gọi LLM tóm tắt và trích việc cần làm. */
export const endMeetingNote = (id: number, accessToken: string): Promise<MeetingNote> =>
  apiRequest(`/api/v1/meeting-notes/${id}/end`, { method: 'POST', accessToken });

export const acceptActionItem = (
  noteId: number,
  itemId: number,
  accessToken: string,
): Promise<Task> =>
  apiRequest(`/api/v1/meeting-notes/${noteId}/action-items/${itemId}/accept`, {
    method: 'POST',
    accessToken,
  });

export const dismissActionItem = (
  noteId: number,
  itemId: number,
  accessToken: string,
): Promise<MeetingActionItem> =>
  apiRequest(`/api/v1/meeting-notes/${noteId}/action-items/${itemId}/dismiss`, {
    method: 'POST',
    accessToken,
  });
