// Đọc lịch tuần theo lối đệm-trước, làm mới ở nền (FR-102).
//
// Ba nguyên tắc quyết định mọi thứ trong file này:
//   1. Vẽ bằng dữ liệu đã lưu trước, luôn luôn. Người dùng thấy tuần của mình
//      gần như tức thì kể cả khi Google chậm hoặc đang lỗi.
//   2. Làm mới nền không bao giờ được xoá dữ liệu đang hiển thị. Lỗi làm mới
//      hiện thành cảnh báo bên cạnh bản cũ, không phải màn hình trắng.
//   3. Nói rõ dữ liệu cũ tới đâu. Đệm mà giấu mốc đồng bộ là nói dối người dùng.

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchCalendarWeek,
  type CalendarInfo,
  type CachedCalendarEvent,
  type CalendarWindow,
} from '../lib/calendarApi';

/**
 * Ngưỡng coi bộ đệm là còn tươi. Dưới ngưỡng này thì mở lại trang không gọi
 * Google nữa — lật qua lại giữa các trang mà lần nào cũng làm mới là đốt hạn
 * mức API cho một thay đổi gần như chắc chắn không có. Nút làm mới tay bỏ qua
 * ngưỡng, vì lúc đó người dùng đã nói rõ họ muốn dữ liệu mới.
 */
export const FRESH_FOR_MS = 5 * 60 * 1000;

export type CalendarWeekState = {
  events: CachedCalendarEvent[];
  calendars: CalendarInfo[];
  lastSyncedAt: string | null;
  failedCalendars: string[];
  /** Chưa có gì để vẽ — chỉ đúng ở lần đọc đệm đầu tiên. */
  loading: boolean;
  /** Đang gọi Google ở nền; màn hình vẫn đang hiện dữ liệu cũ. */
  refreshing: boolean;
  /** Lỗi của lần làm mới. Dữ liệu cũ vẫn còn nguyên bên cạnh. */
  refreshError: string | null;
  /** Lỗi của lần đọc đệm — trường hợp này thật sự không có gì để hiện. */
  loadError: string | null;
  refresh: () => void;
};

const moTaLoi = (err: unknown): string =>
  err instanceof Error && err.message ? err.message : 'Không gọi được máy chủ.';

/** Bộ đệm đã quá hạn tươi chưa; chưa từng đồng bộ thì luôn coi là quá hạn. */
const canLamMoi = (lastSyncedAt: string | null): boolean => {
  if (!lastSyncedAt) return true;
  const moc = new Date(lastSyncedAt).getTime();
  if (Number.isNaN(moc)) return true;
  return Date.now() - moc > FRESH_FOR_MS;
};

/**
 * Cơ chế: mỗi lần `window` hoặc token đổi, hook chạy hai bước nối tiếp — đọc
 * đệm (refresh=false) rồi mới làm mới nền (refresh=true) nếu đệm đã cũ. Một
 * AbortController cho cả hai bước, huỷ khi effect dọn dẹp, nên phản hồi của
 * cửa sổ cũ không bao giờ ghi đè cửa sổ đang xem.
 */
export function useCalendarWeek(
  accessToken: string | null,
  timeWindow: CalendarWindow,
): CalendarWeekState {
  const [events, setEvents] = useState<CachedCalendarEvent[]>([]);
  const [calendars, setCalendars] = useState<CalendarInfo[]>([]);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [failedCalendars, setFailedCalendars] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Giữ controller của lượt đang chạy để nút làm mới tay huỷ được lượt nền còn
  // dở, tránh hai lời gọi Google chồng nhau cho cùng một cửa sổ.
  const controllerRef = useRef<AbortController | null>(null);
  const { timeFrom, timeTo } = timeWindow;

  const lamMoi = useCallback(
    async (signal: AbortSignal) => {
      if (!accessToken) return;
      setRefreshing(true);
      setRefreshError(null);
      try {
        const data = await fetchCalendarWeek(
          accessToken,
          { timeFrom, timeTo },
          { refresh: true, signal },
        );
        if (signal.aborted) return;
        setEvents(data.events);
        setCalendars(data.calendars);
        setLastSyncedAt(data.lastSyncedAt);
        setFailedCalendars(data.failedCalendars);
      } catch (err) {
        if (signal.aborted) return;
        // Cố tình KHÔNG đụng tới `events`: chưa nối Google (409) hay mạng rớt
        // đều không làm dữ liệu đã lưu sai đi, và xoá nó chỉ khiến người dùng
        // mất luôn thứ đang đọc được.
        setRefreshError(moTaLoi(err));
      } finally {
        if (!signal.aborted) setRefreshing(false);
      }
    },
    [accessToken, timeFrom, timeTo],
  );

  useEffect(() => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    controllerRef.current = controller;
    const { signal } = controller;

    void (async () => {
      setLoading(true);
      setLoadError(null);
      let mocDaLuu: string | null = null;
      try {
        const cached = await fetchCalendarWeek(accessToken, { timeFrom, timeTo }, { signal });
        if (signal.aborted) return;
        setEvents(cached.events);
        setCalendars(cached.calendars);
        setLastSyncedAt(cached.lastSyncedAt);
        setFailedCalendars(cached.failedCalendars);
        mocDaLuu = cached.lastSyncedAt;
      } catch (err) {
        if (signal.aborted) return;
        setLoadError(moTaLoi(err));
      } finally {
        if (!signal.aborted) setLoading(false);
      }
      if (signal.aborted) return;
      // Đệm còn tươi thì dừng ở đây — bước làm mới chỉ tồn tại để bù phần cũ.
      if (canLamMoi(mocDaLuu)) await lamMoi(signal);
    })();

    return () => controller.abort();
  }, [accessToken, timeFrom, timeTo, lamMoi]);

  const refresh = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    void lamMoi(controller.signal);
  }, [lamMoi]);

  return {
    events,
    calendars,
    lastSyncedAt,
    failedCalendars,
    loading,
    refreshing,
    refreshError,
    loadError,
    refresh,
  };
}
