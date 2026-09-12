// Bảng cài đặt thông báo lưu ở máy chủ.
//
// Trước component này, tab Thông báo chỉ ghi vào localStorage: các công tắc
// trông như đang tắt bớt thông báo nhưng backend không hề biết, nên người dùng
// vẫn nhận đủ mọi thứ họ vừa tắt. Đây là kiểu hỏng tệ hơn cả không có tính
// năng, vì nó làm người dùng tin là mình đã xử lý xong.
//
// Ba nhóm cài đặt, đúng ba câu hỏi khác nhau:
//   kênh        — nhận Ở ĐÂU (tiện ích, Telegram, ứng dụng đã cài)
//   loại        — nhận VỀ CHUYỆN GÌ
//   giờ yên lặng/tổng hợp — nhận VÀO LÚC NÀO
//
// Lưu ngay mỗi lần đổi thay vì có nút Lưu: mỗi thay đổi là một field độc lập và
// PATCH của backend chỉ ghi đúng field được gửi, nên không có trạng thái nửa
// vời nào để phải gom lại.

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

import { Toggle } from '../ui/Toggle';
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  type NotificationKind,
  type NotificationPreferences,
  type NotificationPreferencesPatch,
} from '../../lib/reminderApi';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

/** Thứ tự hiển thị các loại thông báo: việc gấp trước, tổng hợp cuối cùng. */
const KIND_ORDER: NotificationKind[] = [
  'task_due',
  'task_proposed',
  'conflict_schedule',
  'conflict_evidence',
  'calendar_changed',
  'daily_brief',
];

const HOURS = Array.from({ length: 24 }, (_, hour) => hour);

/** "07" thay vì "7" để hai ô giờ không nhảy độ rộng khi đổi giá trị. */
const formatHour = (hour: number): string => `${String(hour).padStart(2, '0')}:00`;

const selectClass =
  'text-xs font-bold bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-2 py-1 text-[var(--color-text-primary)]';

export const NotificationPreferencesPanel: React.FC = () => {
  const accessToken = useAuthStore((state) => state.accessToken);
  const { t } = useTranslation();
  const labels = t.notificationPrefs;

  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const latestPrefsRef = useRef<NotificationPreferences | null>(null);
  const fieldVersionRef = useRef<Record<string, number>>({});

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void getNotificationPreferences(accessToken)
      .then((value) => {
        if (!cancelled) {
          latestPrefsRef.current = value;
          setPrefs(value);
        }
      })
      .catch(() => {
        if (!cancelled) setErrorMessage(labels.loadError);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, labels.loadError]);

  /**
   * Gửi một thay đổi lên máy chủ và lấy trạng thái thật về.
   *
   * Cập nhật lạc quan trước để công tắc phản hồi ngay, rồi ghi đè bằng phản hồi
   * của máy chủ — máy chủ mới là bên quyết định (nó kẹp giá trị, bỏ trùng trong
   * danh sách loại). Lỗi thì trả giao diện về đúng trạng thái trước đó thay vì
   * để lại một công tắc nói dối.
   */
  const save = useCallback(
    async (patch: NotificationPreferencesPatch, optimisticPatch: Partial<NotificationPreferences>) => {
      const currentPrefs = latestPrefsRef.current;
      if (!accessToken || !currentPrefs) return;
      const fields = Object.keys(optimisticPatch) as Array<keyof NotificationPreferences>;
      const requestVersions = Object.fromEntries(
        fields.map((key) => {
          const nextVersion = (fieldVersionRef.current[key] ?? 0) + 1;
          fieldVersionRef.current[key] = nextVersion;
          return [key, nextVersion];
        }),
      ) as Partial<Record<keyof NotificationPreferences, number>>;
      const optimisticPrefs = { ...currentPrefs, ...optimisticPatch };
      latestPrefsRef.current = optimisticPrefs;
      setPrefs(optimisticPrefs);
      setErrorMessage(null);
      try {
        const serverPrefs = await updateNotificationPreferences(accessToken, patch);
        setPrefs((renderedPrefs) => {
          if (!renderedPrefs) return renderedPrefs;
          const nextPrefs = { ...renderedPrefs };
          const nextRecord = nextPrefs as unknown as Record<string, unknown>;
          const serverRecord = serverPrefs as unknown as Record<string, unknown>;
          for (const key of fields) {
            if (fieldVersionRef.current[key] === requestVersions[key]) {
              nextRecord[key] = serverRecord[key];
            }
          }
          latestPrefsRef.current = nextPrefs;
          return nextPrefs;
        });
      } catch {
        const isCurrentRequest = fields.some(
          (key) => fieldVersionRef.current[key] === requestVersions[key],
        );
        setPrefs((renderedPrefs) => {
          if (!renderedPrefs) return renderedPrefs;
          const nextPrefs = { ...renderedPrefs };
          const nextRecord = nextPrefs as unknown as Record<string, unknown>;
          const previousRecord = currentPrefs as unknown as Record<string, unknown>;
          for (const key of fields) {
            if (fieldVersionRef.current[key] === requestVersions[key]) {
              nextRecord[key] = previousRecord[key];
            }
          }
          latestPrefsRef.current = nextPrefs;
          return nextPrefs;
        });
        if (isCurrentRequest) setErrorMessage(labels.saveError);
      }
    },
    [accessToken, labels.saveError],
  );

  if (!prefs) {
    return errorMessage ? (
      <p role="alert" className="text-[11px] text-red-700 dark:text-red-300 flex items-start gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {errorMessage}
      </p>
    ) : null;
  }

  const toggleChannel = (
    key: 'extensionEnabled' | 'telegramEnabled' | 'webPushEnabled',
    enabled: boolean,
  ) => void save({ [key]: enabled }, { [key]: enabled });

  const toggleKind = (kind: NotificationKind, enabled: boolean) => {
    // Giao diện hỏi "có muốn nhận không", máy chủ lưu "đã tắt những gì" — đảo
    // chiều ở đúng một chỗ này để phần còn lại của UI đọc thuận.
    const currentMutedKinds = latestPrefsRef.current?.mutedKinds ?? prefs.mutedKinds;
    const mutedKinds = enabled
      ? currentMutedKinds.filter((item) => item !== kind)
      : [...currentMutedKinds, kind];
    void save({ mutedKinds }, { mutedKinds });
  };

  return (
    <div className="space-y-4 text-xs">
      <section className="space-y-2">
        <div>
          <h4 className="font-bold text-[var(--color-text-primary)]">{labels.channelsTitle}</h4>
          <p className="text-[11px] text-[var(--color-text-secondary)]">{labels.channelsHint}</p>
        </div>
        {(
          [
            ['extensionEnabled', labels.extension],
            ['telegramEnabled', labels.telegram],
            ['webPushEnabled', labels.webPush],
          ] as const
        ).map(([key, label]) => (
          <div
            key={key}
            className="flex items-center justify-between p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl"
          >
            <span className="font-bold text-[var(--color-text-primary)]">{label}</span>
            <Toggle checked={prefs[key]} onChange={(enabled) => toggleChannel(key, enabled)} aria-label={label} />
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <div>
          <h4 className="font-bold text-[var(--color-text-primary)]">{labels.kindsTitle}</h4>
          <p className="text-[11px] text-[var(--color-text-secondary)]">{labels.kindsHint}</p>
        </div>
        {KIND_ORDER.map((kind) => (
          <div
            key={kind}
            className="flex items-center justify-between p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl"
          >
            <span className="font-bold text-[var(--color-text-primary)]">{labels.kind[kind]}</span>
            <Toggle
              checked={!prefs.mutedKinds.includes(kind)}
              onChange={(enabled) => toggleKind(kind, enabled)}
              aria-label={labels.kind[kind]}
            />
          </div>
        ))}
      </section>

      <section className="space-y-2">
        <div>
          <h4 className="font-bold text-[var(--color-text-primary)]">{labels.quietHoursTitle}</h4>
          <p className="text-[11px] text-[var(--color-text-secondary)]">{labels.quietHoursHint}</p>
        </div>
        <div className="flex items-center gap-2 p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
          <span className="text-[var(--color-text-secondary)]">{labels.from}</span>
          <select
            aria-label={`${labels.quietHoursTitle} — ${labels.from}`}
            className={selectClass}
            value={prefs.quietHoursStart}
            onChange={(event) => {
              const hour = Number(event.target.value);
              void save({ quietHoursStart: hour }, { quietHoursStart: hour });
            }}
          >
            {HOURS.map((hour) => (
              <option key={hour} value={hour}>
                {formatHour(hour)}
              </option>
            ))}
          </select>
          <span className="text-[var(--color-text-secondary)]">{labels.to}</span>
          <select
            aria-label={`${labels.quietHoursTitle} — ${labels.to}`}
            className={selectClass}
            value={prefs.quietHoursEnd}
            onChange={(event) => {
              const hour = Number(event.target.value);
              void save({ quietHoursEnd: hour }, { quietHoursEnd: hour });
            }}
          >
            {HOURS.map((hour) => (
              <option key={hour} value={hour}>
                {formatHour(hour)}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="space-y-2">
        <h4 className="font-bold text-[var(--color-text-primary)]">{labels.dailyBriefTitle}</h4>
        <div className="flex items-center gap-2 p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
          <span className="text-[var(--color-text-secondary)]">{labels.dailyBriefAt}</span>
          <select
            aria-label={labels.dailyBriefTitle}
            className={selectClass}
            value={prefs.dailyBriefHour === null ? 'off' : String(prefs.dailyBriefHour)}
            onChange={(event) => {
              const value = event.target.value;
              // Tắt phải gửi cờ riêng: bỏ trống dailyBriefHour ở backend nghĩa
              // là "không đổi", không phải "tắt".
              if (value === 'off') {
                void save({ disableDailyBrief: true }, { dailyBriefHour: null });
                return;
              }
              const hour = Number(value);
              void save({ dailyBriefHour: hour }, { dailyBriefHour: hour });
            }}
          >
            <option value="off">{labels.dailyBriefOff}</option>
            {HOURS.map((hour) => (
              <option key={hour} value={hour}>
                {formatHour(hour)}
              </option>
            ))}
          </select>
        </div>
      </section>

      {errorMessage && (
        <p role="alert" className="text-[11px] text-red-700 dark:text-red-300 flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {errorMessage}
        </p>
      )}
    </div>
  );
};
