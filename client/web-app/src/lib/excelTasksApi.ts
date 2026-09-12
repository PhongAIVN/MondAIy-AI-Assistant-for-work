import { API_BASE_URL, ApiError } from './apiClient';
import type { GoogleSheetsTaskProposal } from './googleSheetsApi';

export type ExcelTaskProposalResponse = {
  fileNames: string[];
  timezone: string;
  proposals: GoogleSheetsTaskProposal[];
  agentResponse: string;
  agentAnalysis: string;
  agentWarning: string | null;
  searchedName: string;
  needsNameQuery: boolean;
  suggestedNames: string[];
};

/** Gửi multipart trực tiếp để không biến binary Excel thành JSON/base64. */
export const uploadExcelTaskFile = async (
  files: File[],
  accessToken: string,
  searchName = '',
): Promise<ExcelTaskProposalResponse> => {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  if (searchName.trim()) form.append('search_name', searchName.trim());
  const response = await fetch(`${API_BASE_URL}/api/v1/excel/task-proposals`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}` },
    body: form,
  });
  if (!response.ok) {
    let message = response.statusText || 'Không thể đọc tệp Excel.';
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') message = body.detail;
    } catch {
      // Phản hồi lỗi không có JSON vẫn dùng message mặc định.
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<ExcelTaskProposalResponse>;
};
