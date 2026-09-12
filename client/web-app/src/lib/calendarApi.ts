// Client đọc lịch tuần từ bộ nhớ đệm của backend (FR-102).
//
// `GET /calendar/events` có hai chế độ và giao diện phải dùng cả hai:
//   refresh=false — trả ngay dữ liệu đã lưu, không chạm Google, gần như tức thì
//   refresh=true  — gọi Google rồi ghi lại bộ đệm, chậm và tốn hạn mức API
// Màn hình luôn vẽ bằng lần gọi thứ nhất rồi mới làm mới ở nền. Gọi thẳng
// refresh=true để vẽ lần đầu là vứt bỏ toàn bộ lợi ích của lớp đệm.

import { apiRequest } from './apiClient';

export type CachedCalendarEvent = {
  id: string;
  calendarId: string;
  title: string;
  description: string;
  startAt: string;
  endAt: string | null;
  allDay: boolean;
  status: string;
  deepLink: string | null;
  /** Mốc bản ghi này được ghi vào đệm — để giao diện không giả vờ realtime. */
  syncedAt: string;
};

export type CalendarInfo = {
  id: string;
  name: string;
  /**
   * Ghi được vào lịch này không (Google accessRole). Lịch ngày lễ và lịch được
   * chia sẻ dạng chỉ xem có `false` — sửa/xoá chắc chắn ăn 403 nên đừng mời
   * người dùng bấm. Optional: phản hồi đọc từ đệm không kèm danh sách lịch.
   */
  writable?: boolean;
};

export type CalendarWeek = {
  events: CachedCalendarEvent[];
  /** Chỉ có dữ liệu ở phản hồi `refreshed`; đọc đệm không biết tên lịch. */
  calendars: CalendarInfo[];
  origin: 'cache' | 'refreshed';
  lastSyncedAt: string | null;
  /** Lịch không đọc được lần này — FR-045 buộc nói rõ dữ liệu có thể thiếu. */
  failedCalendars: string[];
};

export type CalendarWindow = {
  timeFrom: string;
  timeTo: string;
};

export type CalendarEventWrite = {
  calendarId: string;
  title?: string;
  description?: string;
  startAt?: string;
  endAt?: string;
  allDay?: boolean;
};

export type CalendarWriteResult = {
  event: CachedCalendarEvent | null;
  operationId: number;
  undoExpiresAt: string;
};

/**
 * Cửa sổ một tuần chứa mốc `reference`, tính theo giờ máy người dùng.
 *
 * Cơ chế: lùi về thứ Hai gần nhất (getDay() trả 0 cho Chủ nhật nên phải quy
 * về 7 rồi mới trừ), đặt về 00:00 rồi cộng đúng 7 ngày. Dùng ngày địa phương
 * chứ không phải UTC vì người dùng nghĩ theo tuần của họ, và backend nhận ISO
 * có sẵn offset nên không mất thông tin múi giờ.
 */
export function weekWindow(reference: Date = new Date()): CalendarWindow {
  const start = new Date(reference);
  const thu = start.getDay() === 0 ? 7 : start.getDay();
  start.setDate(start.getDate() - (thu - 1));
  start.setHours(0, 0, 0, 0);

  const end = new Date(start);
  end.setDate(end.getDate() + 7);

  return { timeFrom: start.toISOString(), timeTo: end.toISOString() };
}

/**
 * Đọc lịch trong một cửa sổ. `refresh` quyết định có gọi Google hay không.
 *
 * `signal` để huỷ lời gọi đã lỗi thời khi người dùng lật tuần khác hoặc rời
 * trang: không huỷ thì một phản hồi cũ về muộn sẽ ghi đè dữ liệu mới hơn.
 */
export const fetchCalendarWeek = (
  accessToken: string,
  window: CalendarWindow,
  options: { refresh?: boolean; signal?: AbortSignal } = {},
): Promise<CalendarWeek> => {
  const query = new URLSearchParams({
    timeFrom: window.timeFrom,
    timeTo: window.timeTo,
  });
  if (options.refresh) query.set('refresh', 'true');

  return apiRequest<CalendarWeek>(`/api/v1/calendar/events?${query.toString()}`, {
    accessToken,
    signal: options.signal,
  });
};

/** Các ghi này chỉ dành cho thao tác trực tiếp của người dùng trên lưới lịch. */
export const createCalendarEvent = (
  payload: CalendarEventWrite,
  accessToken: string,
): Promise<CalendarWriteResult> => apiRequest('/api/v1/calendar/events', {
  method: 'POST', accessToken, body: payload,
});

export const updateCalendarEvent = (
  eventId: string,
  payload: CalendarEventWrite,
  accessToken: string,
): Promise<CalendarWriteResult> => apiRequest(`/api/v1/calendar/events/${encodeURIComponent(eventId)}`, {
  method: 'PATCH', accessToken, body: payload,
});

export const deleteCalendarEvent = (
  eventId: string,
  calendarId: string,
  accessToken: string,
): Promise<CalendarWriteResult> => {
  const query = new URLSearchParams({ calendarId });
  return apiRequest(`/api/v1/calendar/events/${encodeURIComponent(eventId)}?${query.toString()}`, {
    method: 'DELETE', accessToken,
  });
};

export const undoCalendarOperation = (
  operationId: number,
  accessToken: string,
): Promise<CalendarWriteResult> => apiRequest(`/api/v1/calendar/operations/${operationId}/undo`, {
  method: 'POST', accessToken,
});
