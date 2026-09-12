import { apiRequest } from './apiClient';

export type GoogleDocsTaskProposal = {
  paragraphIndex: number;
  title: string;
  detail: string;
  assignee: string | null;
  dueAt: string | null;
  allDay: boolean;
  matchedUser: boolean;
  needsConfirmation: boolean;
  clarificationQuestion: string | null;
  source: string;
  sourceUrl: string;
};

export type GoogleDocsTaskProposalResponse = {
  documentId: string;
  timezone: string;
  proposals: GoogleDocsTaskProposal[];
  /** true nếu nội dung bị cắt trước khi vào LLM (cap 20_000 ký tự) — xem p004-CONTRACT.md mục 4. */
  truncated: boolean;
  /** Lượt đọc Docs+Sheets còn lại trong ngày, sau khi tính request này. */
  quotaRemaining: number;
};

export type GoogleDocsScanParams = { documentUrl: string } | { documentId: string };

/** POST /google-docs/task-proposals — xem hợp đồng API tại p004-CONTRACT.md mục 2. */
export const scanGoogleDocTasks = (
  params: GoogleDocsScanParams,
  accessToken: string,
): Promise<GoogleDocsTaskProposalResponse> =>
  apiRequest('/api/v1/google-docs/task-proposals', {
    method: 'POST',
    accessToken,
    body: params,
  });
