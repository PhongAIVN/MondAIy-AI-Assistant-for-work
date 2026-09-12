// Client cho luồng đồng bộ lịch chương trình sang lịch cá nhân (ADR-009).
//
// Hai bước tách rời có chủ đích: `preview` không ghi gì lên Google, `apply` chỉ
// ghi đúng danh sách ID người dùng đã tick. Giao diện không được gộp hai lời gọi
// này thành một nút — bước xem trước chính là sự xác nhận.

import { apiRequest } from './apiClient';

export type ProgramSyncAction = 'create' | 'update' | 'unchanged';

export type ProgramSyncPlanItem = {
  programEventId: number;
  eventType: 'custom' | 'daily_deadline' | 'weekly_deadline' | 'gate_deadline' | 'mentor_duty';
  title: string;
  startAt: string;
  endAt: string | null;
  action: ProgramSyncAction;
  /** Vì sao mốc này ở trạng thái đó — luôn hiện cho người dùng, không nuốt. */
  reason: string;
};

export type ProgramSyncPreview = {
  items: ProgramSyncPlanItem[];
  cohortSlug: string;
};

export type ProgramSyncResult = {
  created: number;
  updated: number;
  /** Mốc không ghi được, kèm lý do. Rỗng nghĩa là đã ghi đủ. */
  skipped: string[];
};

export const previewProgramSync = (
  accessToken: string,
  body: { eventTypes?: string[]; timeFrom?: string; timeTo?: string } = {},
): Promise<ProgramSyncPreview> =>
  apiRequest<ProgramSyncPreview>('/api/v1/calendar/program-sync/preview', {
    method: 'POST',
    body,
    accessToken,
  });

export const applyProgramSync = (
  accessToken: string,
  body: { programEventIds: number[]; calendarId?: string },
): Promise<ProgramSyncResult> =>
  apiRequest<ProgramSyncResult>('/api/v1/calendar/program-sync/apply', {
    method: 'POST',
    body,
    accessToken,
  });
