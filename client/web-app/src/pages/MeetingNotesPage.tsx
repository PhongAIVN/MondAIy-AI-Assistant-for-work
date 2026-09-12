import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, Clock, ListChecks, Plus, Search, SlidersHorizontal, Trash2 } from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useTranslation } from '../i18n/useTranslation';
import {
  formatDuration,
  meetingDurationMs,
  meetingPhase,
} from '../lib/meetingDisplay';
import {
  createMeetingNote,
  deleteMeetingNote,
  listMeetingNotes,
  type MeetingNoteListItem,
} from '../lib/meetingNotesApi';

/**
 * Gom cuộc họp theo ngày bắt đầu để danh sách đọc được như một dòng thời gian.
 * Trả về mảng đã giữ nguyên thứ tự mới-nhất-trước của backend thay vì sort lại,
 * vì sort theo nhãn ngày đã format sẽ sai khi đổi ngôn ngữ.
 */
function groupByDay(
  meetings: MeetingNoteListItem[],
  language: 'en' | 'vi',
): Array<{ key: string; label: string; items: MeetingNoteListItem[] }> {
  const groups = new Map<string, MeetingNoteListItem[]>();
  for (const meeting of meetings) {
    const date = new Date(meeting.startedAt);
    const key = Number.isNaN(date.getTime()) ? 'unknown' : date.toDateString();
    const bucket = groups.get(key);
    if (bucket) bucket.push(meeting);
    else groups.set(key, [meeting]);
  }

  const locale = language === 'vi' ? 'vi-VN' : 'en-US';
  return Array.from(groups.entries()).map(([key, items]) => ({
    key,
    label:
      key === 'unknown'
        ? '—'
        : new Date(key).toLocaleDateString(locale, { weekday: 'long', day: 'numeric', month: 'short' }),
    items,
  }));
}

function formatTime(value: string, language: 'en' | 'vi'): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(language === 'vi' ? 'vi-VN' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Ngày giờ bắt đầu đầy đủ, dùng cho tooltip và cho hàng không thuộc hôm nay. */
function formatDateTime(value: string, language: 'en' | 'vi'): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export const MeetingNotesPage: React.FC = () => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const accessToken = useAuthStore((state) => state.accessToken);
  const { addToast } = useAppStore();

  const [meetings, setMeetings] = useState<MeetingNoteListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'summarized'>('all');
  const [isCreating, setIsCreating] = useState(false);
  // Đồng hồ chạy cho cuộc họp đang ghi: không có nó thì thời lượng đứng im cho
  // tới lần load lại trang. 30 giây một nhịp là đủ vì thời lượng hiện theo phút.
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  const load = useCallback(async () => {
    if (!accessToken) return;
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await listMeetingNotes(accessToken);
      setMeetings(data.meetings);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : t.meetingNotes.loadFailed);
    } finally {
      setIsLoading(false);
    }
  }, [accessToken, t.meetingNotes.loadFailed]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    if (!accessToken || isCreating) return;
    setIsCreating(true);
    try {
      const note = await createMeetingNote(accessToken);
      navigate(`/meeting-notes/${note.id}`);
    } catch (error) {
      addToast({
        type: 'error',
        title: t.meetingNotes.newNote,
        message: error instanceof Error ? error.message : t.meetingNotes.loadFailed,
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (meeting: MeetingNoteListItem, event: React.MouseEvent) => {
    // Nút xoá nằm trong hàng bấm được — chặn nổi bọt để không mở luôn cuộc họp
    // vừa xoá.
    event.stopPropagation();
    if (!accessToken) return;
    if (!window.confirm(t.meetingNotes.deleteConfirm)) return;
    try {
      await deleteMeetingNote(meeting.id, accessToken);
      setMeetings((current) => current.filter((row) => row.id !== meeting.id));
      addToast({ type: 'success', title: t.meetingNotes.title, message: t.meetingNotes.deleted });
    } catch (error) {
      addToast({
        type: 'error',
        title: t.meetingNotes.delete,
        message: error instanceof Error ? error.message : t.meetingNotes.loadFailed,
      });
    }
  };

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return meetings.filter((meeting) => {
      const matchesQuery = !needle || meeting.title.toLowerCase().includes(needle);
      const matchesStatus = statusFilter === 'all' || meeting.status === statusFilter;
      return matchesQuery && matchesStatus;
    });
  }, [meetings, query, statusFilter]);

  const groups = useMemo(() => groupByDay(filtered, language), [filtered, language]);

  return (
    <div className="mx-auto max-w-5xl space-y-7 animate-in fade-in duration-200">
      <div data-tour-id="meeting-notes-header" className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <CalendarDays className="w-4 h-4" /> {t.nav.meetingNotes}
          </div>
          <h1 className="text-4xl font-semibold tracking-tight text-[var(--color-text-primary)] font-heading">
            {t.meetingNotes.title}
          </h1>
        </div>
        <Button onClick={handleCreate} disabled={isCreating} icon={<Plus className="w-4 h-4" />}>
          {t.meetingNotes.newNote}
        </Button>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" />
          <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t.meetingNotes.searchPlaceholder}
          className="w-full pl-9 pr-3 py-2.5 text-sm rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
          />
        </div>
        <label className="inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-[var(--color-border)] px-3 text-xs text-[var(--color-text-secondary)]">
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          <span className="sr-only">{language === 'vi' ? 'Lọc cuộc họp' : 'Filter meetings'}</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
            aria-label={language === 'vi' ? 'Lọc cuộc họp' : 'Filter meetings'}
            className="bg-transparent text-[var(--color-text-primary)] outline-none"
          >
            <option value="all">{language === 'vi' ? 'Tất cả' : 'All'}</option>
            <option value="open">{language === 'vi' ? 'Đang mở' : 'Open'}</option>
            <option value="summarized">{language === 'vi' ? 'Đã tóm tắt' : 'Summarized'}</option>
          </select>
        </label>
      </div>

      {isLoading && (
        <p className="text-sm text-[var(--color-text-secondary)]">{t.meetingNotes.loading}</p>
      )}

      {!isLoading && loadError && (
        <div className="p-4 rounded-xl border border-[var(--color-danger)] text-sm text-[var(--color-danger)]">
          {loadError}
        </div>
      )}

      {!isLoading && !loadError && filtered.length === 0 && (
        <EmptyState
          title={t.meetingNotes.emptyTitle}
          description={t.meetingNotes.emptyBody}
          actionLabel={t.meetingNotes.newNote}
          onAction={handleCreate}
          icon={<CalendarDays className="w-10 h-10 text-[#8B98AB]" />}
        />
      )}

      {!isLoading &&
        !loadError &&
        groups.map((group) => (
          <section key={group.key} className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
              {group.label}
            </h2>
            <ul className="divide-y divide-[var(--color-border)] border-y border-[var(--color-border)]">
              {group.items.map((meeting) => {
                const phase = meetingPhase(meeting, now);
                const durationMs = meetingDurationMs(meeting, phase, now);
                const statusLabel = {
                  recording: t.meetingNotes.statusOpen,
                  stalled: t.meetingNotes.statusStalled,
                  recorded: t.meetingNotes.statusRecorded,
                  summarized: t.meetingNotes.statusSummarized,
                }[phase];
                const endLabel = meeting.endedAt ? formatTime(meeting.endedAt, language) : null;
                return (
                <li key={meeting.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/meeting-notes/${meeting.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        navigate(`/meeting-notes/${meeting.id}`);
                      }
                    }}
                    className="group w-full flex items-center gap-4 px-2 py-4 text-left hover:bg-[var(--color-surface-hover)] cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[var(--color-focus-ring)]"
                  >
                    <span className="p-2 rounded-lg bg-[var(--color-surface-hover)] shrink-0">
                      <ListChecks className="w-4 h-4 text-[var(--color-primary)]" />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-medium text-[var(--color-text-primary)] truncate">
                        {meeting.title || t.meetingNotes.untitled}
                      </span>
                      <span
                        className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-xs text-[var(--color-text-secondary)]"
                        title={formatDateTime(meeting.startedAt, language)}
                      >
                        <span
                          className={
                            phase === 'recording'
                              ? 'inline-flex items-center gap-1.5 font-medium text-[var(--color-danger)]'
                              : 'inline-flex items-center gap-1.5'
                          }
                        >
                          {phase === 'recording' && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-danger)] animate-pulse" />
                          )}
                          {statusLabel}
                        </span>
                        <span aria-hidden>·</span>
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatTime(meeting.startedAt, language)}
                          {endLabel && ` – ${endLabel}`}
                        </span>
                        {durationMs !== null && (
                          <>
                            <span aria-hidden>·</span>
                            <span>
                              {formatDuration(durationMs, {
                                hour: t.meetingNotes.durationHour,
                                minute: t.meetingNotes.durationMinute,
                                lessThanMinute: t.meetingNotes.durationLessThanMinute,
                              })}
                            </span>
                          </>
                        )}
                        {meeting.actionItemCount > 0 && (
                          <>
                            <span aria-hidden>·</span>
                            <span>
                              {meeting.actionItemCount} {t.meetingNotes.actionCount}
                            </span>
                          </>
                        )}
                      </span>
                    </span>
                    {meeting.openActionItemCount > 0 && (
                      <Badge variant="warning">
                        {meeting.openActionItemCount} {t.meetingNotes.openActionCount}
                      </Badge>
                    )}
                    <button
                      type="button"
                      aria-label={t.meetingNotes.delete}
                      onClick={(event) => handleDelete(meeting, event)}
                      className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 focus:opacity-100 text-[var(--color-text-secondary)] hover:text-[var(--color-danger)] transition-opacity"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </li>
                );
              })}
            </ul>
          </section>
        ))}
    </div>
  );
};
