import React, { useMemo, useState } from 'react';
import { CalendarDays, Check, Loader2 } from 'lucide-react';

import type { CalendarSuggestionAction } from '../../lib/visionApi';
import { createCalendarEventsBatch } from '../../lib/visionApi';
import { Button } from '../ui/Button';

type Props = {
  suggestions: CalendarSuggestionAction[];
  accessToken: string | null;
  language: string;
};

function localInputValue(value: string): string {
  const date = new Date(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isoFromLocal(value: string): string {
  return new Date(value).toISOString();
}

export const VisionCalendarBatchCard: React.FC<Props> = ({ suggestions, accessToken, language }) => {
  const vi = language === 'vi';
  const [items, setItems] = useState(() => suggestions.map((item) => ({
    ...item,
    selected: true,
    startInput: localInputValue(item.startAt),
    endInput: localInputValue(item.endAt),
  })));
  const [pending, setPending] = useState(false);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selected = useMemo(() => items.filter((item) => item.selected), [items]);

  const update = (index: number, patch: Partial<typeof items[number]>) => {
    setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  };

  const handleAdd = async () => {
    if (!accessToken || selected.length === 0) return;
    setPending(true);
    setError(null);
    try {
      const result = await createCalendarEventsBatch(accessToken, selected.map((item) => ({
        title: item.title,
        detail: item.detail,
        startAt: isoFromLocal(item.startInput),
        endAt: isoFromLocal(item.endInput),
        allDay: item.allDay,
      })));
      if (result.failed.length > 0) {
        setError(vi ? `Đã thêm ${result.created.length}/${selected.length}; ${result.failed.length} mục lỗi.` : `Added ${result.created.length}/${selected.length}; ${result.failed.length} failed.`);
      }
      if (result.created.length > 0) setAdded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : (vi ? 'Không thể thêm batch vào lịch.' : 'Could not add the batch to Calendar.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <section aria-label={vi ? 'Các mốc lịch đọc từ ảnh' : 'Calendar items read from image'} className="max-w-3xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 shadow-2xs">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">{vi ? 'Lịch đọc từ ảnh' : 'Calendar read from image'}</p>
          <h3 className="mt-1 font-semibold text-[var(--color-text-primary)]">{vi ? `${items.length} mốc được nhận ra` : `${items.length} items detected`}</h3>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">{vi ? 'Kiểm tra, bỏ chọn hoặc sửa giờ trước khi thêm.' : 'Review, deselect, or edit times before adding.'}</p>
        </div>
        <CalendarDays className="h-5 w-5 text-[var(--color-primary)]" />
      </div>
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <div key={`${item.title}-${item.startAt}-${index}`} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={item.selected} onChange={(event) => update(index, { selected: event.target.checked })} className="mt-1" />
              <span className="min-w-0 flex-1">
                <input value={item.title} onChange={(event) => update(index, { title: event.target.value })} className="w-full bg-transparent text-sm font-semibold text-[var(--color-text-primary)] outline-none" />
                {item.detail && <span className="mt-1 block text-xs text-[var(--color-text-secondary)]">{item.detail}</span>}
              </span>
            </label>
            <div className="mt-2 grid grid-cols-1 gap-2 pl-6 sm:grid-cols-2">
              <input aria-label={vi ? 'Bắt đầu' : 'Start'} type="datetime-local" value={item.startInput} onChange={(event) => update(index, { startInput: event.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1.5 text-xs" />
              <input aria-label={vi ? 'Kết thúc' : 'End'} type="datetime-local" value={item.endInput} onChange={(event) => update(index, { endInput: event.target.value })} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-2 py-1.5 text-xs" />
            </div>
          </div>
        ))}
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">{error}</p>}
      <div className="mt-4 flex items-center gap-2">
        {added ? <span className="inline-flex items-center text-sm font-semibold text-[var(--color-success)]"><Check className="mr-1.5 h-4 w-4" />{vi ? 'Đã thêm vào Google Calendar' : 'Added to Google Calendar'}</span> : <Button size="sm" onClick={() => void handleAdd()} disabled={!accessToken || pending || selected.length === 0}>{pending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}{pending ? (vi ? 'Đang thêm…' : 'Adding…') : (vi ? `Thêm ${selected.length} mốc vào lịch` : `Add ${selected.length} items to Calendar`)}</Button>}
      </div>
    </section>
  );
};
