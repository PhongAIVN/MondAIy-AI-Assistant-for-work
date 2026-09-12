import { apiRequest } from './apiClient';

// Hai kiểu trùng: cùng khoảng giờ nhưng khác việc, và cùng một việc xuất hiện
// hai lần. Khớp ConflictType phía backend (src/models/schemas.py).
export type ConflictType = 'time_overlap' | 'same_item';

export type ConflictStatus = 'open' | 'resolved' | 'superseded' | 'stale';

// 'undecided' chỉ hệ thống dùng: không đủ căn cứ thì không gợi ý bên nào.
export type ConflictSuggestion = 'prioritize_task' | 'prioritize_event' | 'undecided';

export type ConflictResolution = 'prioritize_task' | 'prioritize_event' | 'accept_both';

export type ConflictTaskSide = {
  taskId: number;
  title: string;
  dueAt: string | null;
  allDay: boolean;
  ambiguous: boolean;
  status: string;
  sourceCount: number;
  signalStrength: number;
};

export type ConflictEventSide = {
  title: string;
  calendarId: string;
  eventId: string;
  startsAt: string;
  endsAt: string | null;
  allDay: boolean;
  deepLink: string | null;
  syncedAt: string | null;
};

export type ScheduleConflict = {
  id: number;
  conflictType: ConflictType;
  status: ConflictStatus;
  overlapMinutes: number;
  suggestion: ConflictSuggestion;
  // Slug lý do, giao diện tự dịch — backend không trả câu tiếng Việt dựng sẵn.
  suggestionReasons: string[];
  resolution: ConflictResolution | null;
  resolutionNote: string;
  resolvedAt: string | null;
  detectedAt: string;
  task: ConflictTaskSide;
  event: ConflictEventSide;
};

export type ScheduleConflictList = {
  conflicts: ScheduleConflict[];
  openCount: number;
};

export const listScheduleConflicts = (
  accessToken: string,
  status?: ConflictStatus,
): Promise<ScheduleConflictList> =>
  apiRequest(`/api/v1/schedule-conflicts${status ? `?status=${status}` : ''}`, { accessToken });

// Quét một cửa sổ thời gian. Backend chỉ đọc bộ nhớ đệm lịch nên gọi lại mỗi
// lần đổi tuần không tốn hạn mức Google, và không sinh bản trùng.
export const detectScheduleConflicts = (
  accessToken: string,
  timeFrom: string,
  timeTo: string,
): Promise<ScheduleConflictList> => {
  const params = new URLSearchParams({ timeFrom, timeTo });
  return apiRequest(`/api/v1/schedule-conflicts/detect?${params.toString()}`, {
    method: 'POST',
    accessToken,
  });
};

export const resolveScheduleConflict = (
  conflictId: number,
  resolution: ConflictResolution,
  accessToken: string,
  note = '',
): Promise<ScheduleConflict> =>
  apiRequest(`/api/v1/schedule-conflicts/${conflictId}/resolve`, {
    method: 'POST',
    accessToken,
    body: { resolution, note },
  });
