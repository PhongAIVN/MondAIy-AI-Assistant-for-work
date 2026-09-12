import React from 'react';
import { CalendarRange, Globe } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { resolveTimezone, type RangePreset } from '../../stores/usePipelineRunStore';

export interface TimeRangePickerProps {
  preset: RangePreset;
  customFrom: string;
  customTo: string;
  disabled?: boolean;
  onPreset: (preset: RangePreset) => void;
  onCustom: (from: string, to: string) => void;
}

export const TimeRangePicker: React.FC<TimeRangePickerProps> = ({
  preset,
  customFrom,
  customTo,
  disabled = false,
  onPreset,
  onCustom,
}) => {
  const { t } = useTranslation();

  const options: { value: RangePreset; label: string }[] = [
    { value: '24h', label: t.pipeline.last24h },
    { value: '3d', label: t.pipeline.last3d },
    { value: '7d', label: t.pipeline.last7d },
    { value: 'custom', label: t.pipeline.custom },
  ];

  // Múi giờ quyết định "hôm nay" và "thứ sáu tuần sau" nghĩa là gì, nên phải
  // nhìn thấy được ngay cạnh ô chọn khoảng thời gian, không giấu trong Hồ sơ.
  const timezone = resolveTimezone();

  return (
    <section aria-labelledby="time-range-heading" className="space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <h2
          id="time-range-heading"
          className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading flex items-center gap-2"
        >
          <CalendarRange className="w-4 h-4 text-[var(--color-primary)]" aria-hidden="true" />
          {t.pipeline.rangeTitle}
        </h2>

        <span className="inline-flex items-center gap-1 text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC]">
          <Globe className="w-3.5 h-3.5" aria-hidden="true" />
          {t.pipeline.timezoneLabel}: <span className="font-semibold">{timezone}</span>
        </span>
      </div>

      <div role="radiogroup" aria-labelledby="time-range-heading" className="flex flex-wrap items-center gap-1.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={preset === option.value}
            disabled={disabled}
            onClick={() => onPreset(option.value)}
            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] disabled:opacity-50 disabled:cursor-not-allowed ${
              preset === option.value
                ? 'bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-2xs'
                : 'text-[var(--color-text-secondary)] bg-[var(--color-surface-muted)] border border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {preset === 'custom' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 rounded-xl bg-[var(--color-accent-soft)] border border-[var(--color-border)]">
          <div>
            <label
              htmlFor="range-from"
              className="block text-[11px] font-bold text-[var(--color-text-primary)] mb-1"
            >
              {t.pipeline.from}
            </label>
            <input
              id="range-from"
              type="date"
              value={customFrom}
              max={customTo || undefined}
              disabled={disabled}
              onChange={(event) => onCustom(event.target.value, customTo)}
              className="w-full p-2 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>

          <div>
            <label htmlFor="range-to" className="block text-[11px] font-bold text-[var(--color-text-primary)] mb-1">
              {t.pipeline.to}
            </label>
            <input
              id="range-to"
              type="date"
              value={customTo}
              min={customFrom || undefined}
              disabled={disabled}
              onChange={(event) => onCustom(customFrom, event.target.value)}
              className="w-full p-2 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>
        </div>
      )}
    </section>
  );
};
