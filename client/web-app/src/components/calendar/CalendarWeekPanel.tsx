// Lưới tuần đọc từ bộ nhớ đệm, làm mới ở nền (FR-102).
//
// Bốn trạng thái đều phải hiện rõ, vì thiếu bất kỳ cái nào là người dùng hiểu
// sai dữ liệu mình đang đọc:
//   đang tải     — chưa có gì trong đệm để vẽ
//   rỗng         — đệm đọc được nhưng tuần này không có sự kiện
//   thiếu một phần — vài lịch đọc hỏng, tuần hiện ra chưa đủ (FR-045)
//   làm mới hỏng — vẫn hiện bản cũ, kèm mốc đồng bộ để tự đánh giá độ tin

import React, { useMemo } from 'react';
import { AlertTriangle, CalendarDays, Clock, ExternalLink, RefreshCw } from 'lucide-react';

import { useCalendarWeek } from '../../hooks/useCalendarWeek';
import { weekWindow, type CachedCalendarEvent } from '../../lib/calendarApi';
import { formatRelativeTime } from '../../lib/relativeTime';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

/** Nhóm sự kiện theo ngày địa phương, giữ nguyên thứ tự thời gian đã sắp sẵn. */
const nhomTheoNgay = (events: CachedCalendarEvent[]): Array<[string, CachedCalendarEvent[]]> => {
  const nhom = new Map<string, CachedCalendarEvent[]>();
  for (const event of events) {
    const ngay = new Date(event.startAt).toDateString();
    const danhSach = nhom.get(ngay);
    if (danhSach) danhSach.push(event);
    else nhom.set(ngay, [event]);
  }
  return [...nhom.entries()];
};

export const CalendarWeekPanel: React.FC = () => {
  const accessToken = useAuthStore((state) => state.accessToken);
  const { t, language } = useTranslation();
  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';

  // Cửa sổ phải ổn định giữa các lần render: dựng Date mới mỗi lần render sẽ
  // đổi tham chiếu và làm effect trong hook chạy lại vô hạn.
  const timeWindow = useMemo(() => weekWindow(), []);
  const {
    events,
    calendars,
    lastSyncedAt,
    failedCalendars,
    loading,
    refreshing,
    refreshError,
    loadError,
    refresh,
  } = useCalendarWeek(accessToken, timeWindow);

  const tenLich = useMemo(
    () => new Map(calendars.map((calendar) => [calendar.id, calendar.name])),
    [calendars],
  );

  const gio = (event: CachedCalendarEvent): string => {
    if (event.allDay) return t.calendarWeek.allDay;
    const batDau = new Date(event.startAt).toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
    });
    if (!event.endAt) return batDau;
    const ketThuc = new Date(event.endAt).toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
    });
    return `${batDau} – ${ketThuc}`;
  };

  const nhanDongBo = lastSyncedAt
    ? t.calendarWeek.syncedAt.replace('{time}', formatRelativeTime(lastSyncedAt, language))
    : t.calendarWeek.neverSynced;

  return (
    <section
      aria-labelledby="calendar-week-heading"
      className="rounded-2xl border border-[#D5DDEB] dark:border-[#1A2A42] p-4 sm:p-5 space-y-3"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2
            id="calendar-week-heading"
            className="font-bold text-[#0F1F38] dark:text-white flex items-center gap-2"
          >
            <CalendarDays className="w-4 h-4" /> {t.calendarWeek.heading}
          </h2>
          {/* Mốc đồng bộ luôn hiện cạnh dữ liệu, không giấu trong tooltip:
              đây là thứ duy nhất cho biết bản đang đọc cũ tới mức nào. */}
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            {refreshing ? t.calendarWeek.refreshing : nhanDongBo}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing || !accessToken}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] text-xs font-semibold text-[#2563A6] disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {t.calendarWeek.refresh}
        </button>
      </div>

      {failedCalendars.length > 0 && (
        <p
          role="status"
          className="text-xs text-amber-800 dark:text-amber-200 flex items-start gap-1.5 bg-amber-50 dark:bg-amber-950/30 rounded-xl p-3"
        >
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {t.calendarWeek.partial.replace(
            '{calendars}',
            failedCalendars.map((id) => tenLich.get(id) ?? id).join(', '),
          )}
        </p>
      )}

      {refreshError && (
        <p
          role="status"
          className="text-xs text-amber-800 dark:text-amber-200 flex items-start gap-1.5 bg-amber-50 dark:bg-amber-950/30 rounded-xl p-3"
        >
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {t.calendarWeek.refreshFailed} {refreshError}
        </p>
      )}

      {loadError && events.length === 0 && (
        <p
          role="alert"
          className="text-xs text-red-700 dark:text-red-300 flex items-start gap-1.5 bg-red-50 dark:bg-red-950/30 rounded-xl p-3"
        >
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {t.calendarWeek.loadFailed}{' '}
          {loadError}
        </p>
      )}

      {loading && events.length === 0 && (
        <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{t.calendarWeek.loading}</p>
      )}

      {!loading && !loadError && events.length === 0 && (
        <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB] space-y-1">
          <p>{t.calendarWeek.empty}</p>
          <p>{t.calendarWeek.emptyHint}</p>
        </div>
      )}

      {events.length > 0 && (
        <div className="space-y-4">
          {nhomTheoNgay(events).map(([ngay, trongNgay]) => (
            <div key={ngay} className="space-y-2">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-[#5A6A85] dark:text-[#8B98AB]">
                {new Date(ngay).toLocaleDateString(locale, {
                  weekday: 'long',
                  day: '2-digit',
                  month: 'short',
                })}
              </h3>
              <ul className="divide-y divide-[#D5DDEB] dark:divide-[#1A2A42]">
                {trongNgay.map((event) => (
                  <li
                    key={`${event.calendarId}:${event.id}`}
                    className="py-2 flex items-start justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-[#0F1F38] dark:text-white truncate">
                        {event.title}
                      </div>
                      <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB] flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 shrink-0" />
                        {gio(event)}
                        {tenLich.has(event.calendarId) && (
                          <span className="truncate">· {tenLich.get(event.calendarId)}</span>
                        )}
                      </div>
                    </div>
                    {event.deepLink && (
                      <a
                        href={event.deepLink}
                        target="_blank"
                        rel="noreferrer"
                        className="shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-[#2563A6]"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span className="sr-only sm:not-sr-only">
                          {t.calendarWeek.openInGoogle}
                        </span>
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
