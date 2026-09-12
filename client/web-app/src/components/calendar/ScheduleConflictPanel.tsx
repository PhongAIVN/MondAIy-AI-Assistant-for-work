import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CalendarDays,
  Check,
  Copy,
  ExternalLink,
  HelpCircle,
  Inbox,
  RefreshCw,
} from 'lucide-react';

import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useTranslation } from '../../i18n/useTranslation';
import { ApiError } from '../../lib/apiClient';
import {
  detectScheduleConflicts,
  resolveScheduleConflict,
  type ConflictResolution,
  type ScheduleConflict,
} from '../../lib/scheduleConflictsApi';

type Props = {
  accessToken: string | null;
  // Cửa sổ tuần đang xem trên lưới lịch — panel quét đúng khoảng đó nên người
  // dùng chỉ thấy xung đột của những ngày họ đang nhìn.
  timeFrom: Date;
  timeTo: Date;
  locale: string;
  // Tăng sau khi trang cha đồng bộ calendar cache; detect trước mốc này có
  // thể chạy đua với request tải event và trả về danh sách rỗng.
  calendarSyncVersion?: number;
  // Gọi lại sau khi resolve xong: quyết định kiểu same_item có thể đổi trạng
  // thái task, nên trang cha phải tải lại danh sách task.
  onResolved?: () => void;
};

// Hai bên của một lần trùng, dùng chung một khối hiển thị để không bên nào trông
// quan trọng hơn bên nào trước khi người dùng quyết (PRD §12: không được tự chọn
// một bên rồi trình bày như điều chắc chắn).
type SideProps = {
  icon: React.ReactNode;
  label: string;
  title: string;
  timeText: string;
  metaText: string;
  href?: string | null;
  highlighted: boolean;
  highlightLabel: string;
};

const ConflictSide: React.FC<SideProps> = ({
  icon,
  label,
  title,
  timeText,
  metaText,
  href,
  highlighted,
  highlightLabel,
}) => (
  <div
    className={`min-w-0 flex-1 rounded-xl border p-3 ${
      highlighted
        ? 'border-[var(--color-primary)] bg-[var(--color-accent-soft)]'
        : 'border-[var(--color-border)] bg-[var(--color-surface)]'
    }`}
  >
    <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
      {icon}
      {label}
      {highlighted && (
        <Badge variant="purple" className="ml-auto normal-case tracking-normal">
          {highlightLabel}
        </Badge>
      )}
    </div>
    <p className="mt-2 truncate text-sm font-semibold text-[var(--color-text-primary)]" title={title}>
      {title}
    </p>
    <p className="mt-1 text-[11px] tabular-nums text-[var(--color-text-secondary)]">{timeText}</p>
    <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">{metaText}</p>
    {href && (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-[var(--color-primary)] hover:underline focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
      >
        <ExternalLink className="h-3 w-3" /> {label}
      </a>
    )}
  </div>
);

export const ScheduleConflictPanel: React.FC<Props> = ({
  accessToken,
  timeFrom,
  timeTo,
  locale,
  calendarSyncVersion = 0,
  onResolved,
}) => {
  const { t } = useTranslation();
  const copy = t.scheduleConflicts;

  const [conflicts, setConflicts] = useState<ScheduleConflict[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});

  const fromIso = timeFrom.toISOString();
  const toIso = timeTo.toISOString();

  const load = useCallback(async () => {
    if (!accessToken) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await detectScheduleConflicts(accessToken, fromIso, toIso);
      setConflicts(result.conflicts);
    } catch (requestError) {
      setConflicts([]);
      setError(requestError instanceof ApiError ? requestError.message : copy.loadError);
    } finally {
      setLoading(false);
    }
  }, [accessToken, copy.loadError, fromIso, toIso]);

  useEffect(() => {
    void load();
  }, [calendarSyncVersion, load]);

  const formatDateTime = (value: string | null, allDay: boolean): string => {
    if (!value) return copy.timeUnknown;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return copy.timeUnknown;
    return allDay
      ? parsed.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' })
      : parsed.toLocaleString(locale, {
          weekday: 'short',
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        });
  };

  const eventTimeText = (conflict: ScheduleConflict): string => {
    const start = formatDateTime(conflict.event.startsAt, conflict.event.allDay);
    if (conflict.event.allDay || !conflict.event.endsAt) return start;
    const end = new Date(conflict.event.endsAt);
    if (Number.isNaN(end.getTime())) return start;
    return `${start} – ${end.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}`;
  };

  // Lý do gợi ý là slug, dịch ở đây. Slug lạ (backend thêm luật mới trước khi
  // giao diện kịp dịch) thì hiện nguyên slug chứ không bỏ đi, để người dùng vẫn
  // thấy có một lý do và người phát triển thấy ngay thiếu bản dịch.
  const reasonText = (slug: string): string => copy.reasons[slug as keyof typeof copy.reasons] ?? slug;

  const suggestionText = (conflict: ScheduleConflict): string => {
    if (conflict.suggestion === 'prioritize_task') return copy.suggestTask;
    if (conflict.suggestion === 'prioritize_event') return copy.suggestEvent;
    return copy.suggestUndecided;
  };

  const resolve = async (conflict: ScheduleConflict, resolution: ConflictResolution) => {
    if (!accessToken) return;
    setPendingId(conflict.id);
    try {
      await resolveScheduleConflict(conflict.id, resolution, accessToken, notes[conflict.id] ?? '');
      setConflicts((current) => current.filter((row) => row.id !== conflict.id));
      onResolved?.();
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : copy.resolveError);
    } finally {
      setPendingId(null);
    }
  };

  const openCount = conflicts.length;
  const header = useMemo(
    () => (
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 font-heading text-lg font-semibold tracking-[-0.02em] text-[var(--color-text-primary)]">
            <AlertTriangle className="h-4 w-4 text-[var(--color-danger)]" />
            {copy.title}
            {openCount > 0 && (
              <span className="rounded-md bg-[var(--color-danger-soft)] px-1.5 py-0.5 text-[11px] tabular-nums text-[var(--color-danger)]">
                {openCount}
              </span>
            )}
          </h2>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{copy.subtitle}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          icon={<RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />}
          onClick={() => void load()}
          disabled={loading}
        >
          {copy.rescan}
        </Button>
      </div>
    ),
    [copy.rescan, copy.subtitle, copy.title, load, loading, openCount],
  );

  if (!accessToken) return null;

  return (
    <section
      aria-label={copy.title}
      className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
    >
      {header}

      {error && (
        <p className="mt-3 rounded-lg bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</p>
      )}

      {loading ? (
        <div className="mt-3 space-y-2" aria-label={copy.loading}>
          {[0, 1].map((row) => (
            <div key={row} className="h-28 animate-pulse rounded-xl bg-[var(--color-surface-muted)]" />
          ))}
        </div>
      ) : conflicts.length === 0 ? (
        <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">{copy.empty}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {conflicts.map((conflict) => {
            const isSameItem = conflict.conflictType === 'same_item';
            const busy = pendingId === conflict.id;
            return (
              <li
                key={conflict.id}
                className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)]/45 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge
                    variant={isSameItem ? 'info' : 'warning'}
                    icon={isSameItem ? <Copy className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                  >
                    {isSameItem ? copy.typeSameItem : copy.typeTimeOverlap}
                  </Badge>
                  {!isSameItem && conflict.overlapMinutes > 0 && (
                    <span className="text-[11px] tabular-nums text-[var(--color-text-secondary)]">
                      {copy.overlapMinutes.replace('{count}', String(conflict.overlapMinutes))}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex flex-col gap-2 lg:flex-row">
                  <ConflictSide
                    icon={<Inbox className="h-3 w-3" />}
                    label={copy.taskSide}
                    title={conflict.task.title}
                    timeText={
                      conflict.task.ambiguous
                        ? copy.timeUnknown
                        : formatDateTime(conflict.task.dueAt, conflict.task.allDay)
                    }
                    metaText={copy.taskMeta
                      .replace('{status}', copy.taskStatus[conflict.task.status as keyof typeof copy.taskStatus] ?? conflict.task.status)
                      .replace('{sources}', String(conflict.task.sourceCount))}
                    highlighted={conflict.suggestion === 'prioritize_task'}
                    highlightLabel={copy.suggestedBadge}
                  />
                  <ConflictSide
                    icon={<CalendarDays className="h-3 w-3" />}
                    label={copy.eventSide}
                    title={conflict.event.title}
                    timeText={eventTimeText(conflict)}
                    metaText={copy.eventMeta.replace('{calendar}', conflict.event.calendarId)}
                    href={conflict.event.deepLink}
                    highlighted={conflict.suggestion === 'prioritize_event'}
                    highlightLabel={copy.suggestedBadge}
                  />
                </div>

                <p className="mt-3 flex items-start gap-2 rounded-lg bg-[var(--color-surface)] p-2.5 text-xs text-[var(--color-text-secondary)]">
                  {conflict.suggestion === 'undecided' ? (
                    <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-text-muted)]" />
                  ) : (
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-primary)]" />
                  )}
                  <span>
                    <span className="font-semibold text-[var(--color-text-primary)]">{suggestionText(conflict)}</span>
                    {conflict.suggestionReasons.length > 0 && (
                      <span> — {conflict.suggestionReasons.map(reasonText).join('; ')}</span>
                    )}
                  </span>
                </p>

                <label className="mt-3 block">
                  <span className="text-[11px] font-medium text-[var(--color-text-secondary)]">{copy.noteLabel}</span>
                  <input
                    type="text"
                    value={notes[conflict.id] ?? ''}
                    maxLength={500}
                    onChange={(changeEvent) =>
                      setNotes((current) => ({ ...current, [conflict.id]: changeEvent.target.value }))
                    }
                    placeholder={copy.notePlaceholder}
                    className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                  />
                </label>

                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => void resolve(conflict, 'accept_both')}
                    disabled={busy}
                  >
                    {isSameItem ? copy.actionNotDuplicate : copy.actionKeepBoth}
                  </Button>
                  <Button
                    variant="outline"
                    size="xs"
                    icon={<CalendarDays className="h-3.5 w-3.5" />}
                    onClick={() => void resolve(conflict, 'prioritize_event')}
                    disabled={busy}
                  >
                    {isSameItem ? copy.actionEventIsCanonical : copy.actionPrioritizeEvent}
                  </Button>
                  <Button
                    variant="primary"
                    size="xs"
                    icon={<Inbox className="h-3.5 w-3.5" />}
                    onClick={() => void resolve(conflict, 'prioritize_task')}
                    disabled={busy}
                  >
                    {isSameItem ? copy.actionTaskIsCanonical : copy.actionPrioritizeTask}
                  </Button>
                </div>

                <p className="mt-2 text-[11px] text-[var(--color-text-muted)]">
                  {isSameItem ? copy.sameItemEffectHint : copy.timeOverlapEffectHint}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};
