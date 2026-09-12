import { apiRequest } from './apiClient';

export type GoogleDriveFileKind = 'document' | 'spreadsheet';

export type GoogleDriveFile = {
  id: string;
  name: string;
  kind: GoogleDriveFileKind;
  modifiedTime: string;
  webViewLink: string;
};

export type GoogleDriveFileListResponse = {
  files: GoogleDriveFile[];
  nextPageToken: string | null;
};

export type GoogleDriveFileListParams = {
  q?: string;
  /** 'all' bỏ qua filter phía server — không gửi query param `kind`. */
  kind?: GoogleDriveFileKind | 'all';
  pageToken?: string | null;
  pageSize?: number;
};

/** GET /google-drive/files — xem hợp đồng API tại p004-CONTRACT.md mục 1. */
export const listGoogleDriveFiles = (
  params: GoogleDriveFileListParams,
  accessToken: string,
): Promise<GoogleDriveFileListResponse> => {
  const search = new URLSearchParams();
  if (params.q?.trim()) search.set('q', params.q.trim());
  if (params.kind && params.kind !== 'all') search.set('kind', params.kind);
  if (params.pageToken) search.set('pageToken', params.pageToken);
  search.set('pageSize', String(params.pageSize ?? 20));
  return apiRequest(`/api/v1/google-drive/files?${search.toString()}`, { accessToken });
};
