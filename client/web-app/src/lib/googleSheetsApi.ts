import { apiRequest } from './apiClient';

export type GoogleSheetsTaskProposal = {
  rowNumber: number;
  externalKey: string;
  title: string;
  detail: string;
  assignee: string | null;
  dueAt: string | null;
  allDay: boolean;
  status: string | null;
  matchedUser: boolean;
  matchKind?: 'exact' | 'close' | 'possible' | 'none';
  needsConfirmation: boolean;
  clarificationQuestion: string | null;
  source: string;
  sourceUrl: string;
};

export type GoogleSheetsTaskProposalResponse = {
  spreadsheetId: string;
  sheetName: string;
  availableSheetNames: string[];
  timezone: string;
  proposals: GoogleSheetsTaskProposal[];
  /** true nếu bảng bị cắt trước khi vào LLM (cap 500 dòng x 20 cột / 20_000 ký tự). */
  truncated: boolean;
  /** Lượt đọc Docs+Sheets còn lại trong ngày, sau khi tính request này. */
  quotaRemaining: number;
};

export const scanGoogleSheetTasks = (
  spreadsheetUrl: string,
  sheetName: string,
  accessToken: string,
): Promise<GoogleSheetsTaskProposalResponse> =>
  apiRequest('/api/v1/google-sheets/task-proposals', {
    method: 'POST',
    accessToken,
    body: { spreadsheetUrl, sheetName },
  });

/** Đường vào thứ hai cho luồng chọn file Drive: quét bằng spreadsheetId thay
 * vì URL dán tay — cùng endpoint, chỉ khác field request (xem p004-CONTRACT.md mục 3). */
export const scanGoogleSheetTasksById = (
  spreadsheetId: string,
  sheetName: string,
  accessToken: string,
): Promise<GoogleSheetsTaskProposalResponse> =>
  apiRequest('/api/v1/google-sheets/task-proposals', {
    method: 'POST',
    accessToken,
    body: { spreadsheetId, sheetName },
  });
