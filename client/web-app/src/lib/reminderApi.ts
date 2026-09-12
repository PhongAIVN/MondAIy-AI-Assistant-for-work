import { apiRequest } from './apiClient';

// 6 loai thong bao chung 1 pipe — khop ReminderKind trong
// src/models/schemas.py. conflict_evidence/daily_brief/calendar_changed khong
// gan 1 task cu the nen taskId/dueAt co the null; payload mang du lieu rieng
// theo kind.
export type NotificationKind =
  | 'task_due'
  | 'task_proposed'
  | 'conflict_schedule'
  | 'conflict_evidence'
  | 'daily_brief'
  | 'calendar_changed';

// 1 dong trong Trung tam thong bao (web) — moi nhat truoc, ca da doc lan
// chua doc (khac /due o backend, chi tra thong bao CHUA giao cho kenh push).
export type NotificationEntry = {
  reminderId: number;
  kind: NotificationKind;
  title: string;
  milestone: string;
  taskId: number | null;
  dueAt: string | null;
  scheduledAt: string;
  evidenceDeepLink: string | null;
  payload: Record<string, unknown>;
  isRead: boolean;
};

type NotificationListResponse = { notifications: NotificationEntry[] };
type RecordDeliveriesResponse = { recorded: number[] };

/** Trung tam thong bao (web) — ca da doc lan chua doc, moi nhat truoc. */
export async function listNotifications(accessToken: string, limit = 50): Promise<NotificationEntry[]> {
  const body = await apiRequest<NotificationListResponse>(`/api/v1/reminders/notifications?limit=${limit}`, {
    accessToken,
  });
  return body.notifications;
}

/**
 * Cấu hình thông báo lưu ở máy chủ — khớp NotificationPreferenceResponse.
 *
 * Đây là nguồn chuẩn duy nhất cho việc "người dùng bị làm phiền tới mức nào":
 * cả ba kênh giao (tiện ích, Telegram, Web Push) đều đọc chung nó ở backend,
 * nên đổi ở đây là đổi thật, không phải chỉ đổi trên máy đang mở.
 */
export type NotificationPreferences = {
  timezone: string;
  quietHoursStart: number;
  quietHoursEnd: number;
  hourlyCap: number;
  batchWindowMinutes: number;
  /** null = tắt tổng hợp cuối ngày. */
  dailyBriefHour: number | null;
  extensionEnabled: boolean;
  telegramEnabled: boolean;
  webPushEnabled: boolean;
  mutedKinds: NotificationKind[];
};

/** PATCH từng phần: field bỏ trống nghĩa là giữ nguyên, không phải xoá. */
export type NotificationPreferencesPatch = Partial<
  Pick<
    NotificationPreferences,
    | 'timezone'
    | 'quietHoursStart'
    | 'quietHoursEnd'
    | 'hourlyCap'
    | 'batchWindowMinutes'
    | 'extensionEnabled'
    | 'telegramEnabled'
    | 'webPushEnabled'
    | 'mutedKinds'
  >
> & {
  dailyBriefHour?: number;
  /** Tắt tổng hợp cuối ngày phải nói tường minh: dailyBriefHour bỏ trống chỉ là "không đổi". */
  disableDailyBrief?: boolean;
};

export const getNotificationPreferences = (accessToken: string): Promise<NotificationPreferences> =>
  apiRequest<NotificationPreferences>('/api/v1/reminders/preferences', { accessToken });

export const updateNotificationPreferences = (
  accessToken: string,
  patch: NotificationPreferencesPatch,
): Promise<NotificationPreferences> =>
  apiRequest<NotificationPreferences>('/api/v1/reminders/preferences', {
    accessToken,
    method: 'PATCH',
    body: patch,
  });

/** Idempotent theo reminder_id — goi lai voi id da ghi khong tao trung. */
export async function recordReminderDeliveries(accessToken: string, reminderIds: number[]): Promise<number[]> {
  if (reminderIds.length === 0) return [];
  const body = await apiRequest<RecordDeliveriesResponse>('/api/v1/reminders/deliveries', {
    accessToken,
    method: 'POST',
    body: { reminderIds },
  });
  return body.recorded;
}

export type ReminderPreferences = {
  timezone: string;
  quietHoursStart: number;
  quietHoursEnd: number;
  hourlyCap: number;
  batchWindowMinutes: number;
  /** null = daily brief tự động đang tắt. */
  dailyBriefHour: number | null;
};

export type UpdateReminderPreferences = {
  timezone?: string;
  dailyBriefHour?: number;
  disableDailyBrief?: boolean;
};

/** Đọc cấu hình nhắc việc thật của user (giờ daily brief, quiet hours...). */
export function getReminderPreferences(accessToken: string): Promise<ReminderPreferences> {
  return apiRequest('/api/v1/reminders/preferences', { accessToken });
}

/** PATCH từng phần — field bỏ trống giữ nguyên giá trị cũ (theo UpdateNotificationPreferenceRequest phía backend). */
export function updateReminderPreferences(
  updates: UpdateReminderPreferences,
  accessToken: string,
): Promise<ReminderPreferences> {
  return apiRequest('/api/v1/reminders/preferences', {
    accessToken,
    method: 'PATCH',
    body: updates,
  });
}
