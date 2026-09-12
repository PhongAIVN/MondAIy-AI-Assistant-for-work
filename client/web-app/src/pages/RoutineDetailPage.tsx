import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { CalendarDays, ChevronLeft, Clock3, LoaderCircle, Pause, Play, Sparkles, Trash2 } from 'lucide-react';

import { Button } from '../components/ui/Button';
import { MarkdownBody } from '../components/marketing/MarkdownBody';
import {
  deleteRoutine,
  getRoutine,
  listRoutineRuns,
  runRoutineNow,
  updateRoutine,
  type Routine,
  type RoutineRun,
} from '../lib/routinesApi';
import { useAuthStore } from '../stores/useAuthStore';
import { useAppStore } from '../stores/useAppStore';
import { useRoutineStore } from '../stores/useRoutineStore';
import { useTranslation } from '../i18n/useTranslation';

/**
 * Trang riêng cho 1 routine — bấm vào card ở /routines vào đây thay vì mở
 * rộng tại chỗ. Bên trái hiện nội dung của lần chạy đang chọn (hoặc trạng
 * thái đang tạo), bên phải là nút "Chạy ngay" + lịch sử các lần chạy để bấm
 * xem lại. Nội dung luôn là kết quả thật từ `run_routine` (agent thật), kể
 * cả lúc "đang tạo" — không có state giả lập chờ trong lúc chưa có kết quả.
 */
export const RoutineDetailPage: React.FC = () => {
  const { routineId } = useParams<{ routineId: string }>();
  const navigate = useNavigate();
  const accessToken = useAuthStore((state) => state.accessToken);
  const { addToast } = useAppStore();
  const { upsertRoutine, removeRoutine, prependRecentRun } = useRoutineStore();
  const { language } = useTranslation();
  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';

  const copy = language === 'vi'
    ? {
        back: 'Routines', notFound: 'Không tìm thấy routine.', runNow: 'Chạy ngay', running: 'Đang chạy...', history: 'Lịch sử chạy', selectDay: 'Chọn ngày', allDays: 'Tất cả', schedule: 'Lịch chạy', instructions: 'Hướng dẫn',
        generatingTitle: 'Đang tạo ghi chú của bạn...', generatingSubtitle: 'Đang thu thập ngữ cảnh và viết báo cáo. Thường mất dưới 1 phút.',
        noRunsYet: 'Chưa chạy lần nào — bấm "Chạy ngay" để xem kết quả đầu tiên.',
        pause: 'Tạm dừng', resume: 'Bật lại', deleteRoutine: 'Xoá routine', errorPrefix: 'Lần chạy này bị lỗi:',
        saveError: 'Không chạy được routine. Hãy thử lại.', deleteConfirm: 'Xoá routine này? Không hoàn tác được.',
      }
    : {
        back: 'Routines', notFound: 'Routine not found.', runNow: 'Run now', running: 'Running...', history: 'Run history', selectDay: 'Select day', allDays: 'All days', schedule: 'Schedule', instructions: 'Instructions',
        generatingTitle: 'Generating your note...', generatingSubtitle: 'Gathering context and writing your report. This usually takes under a minute.',
        noRunsYet: 'Hasn\'t run yet — click "Run now" to see the first result.',
        pause: 'Pause', resume: 'Resume', deleteRoutine: 'Delete routine', errorPrefix: 'This run failed:',
        saveError: 'Could not run the routine. Please retry.', deleteConfirm: 'Delete this routine? This cannot be undone.',
      };

  const [routine, setRoutine] = useState<Routine | null>(null);
  const [runs, setRuns] = useState<RoutineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);

  const load = async () => {
    if (!accessToken || !routineId) return;
    setLoading(true);
    setNotFound(false);
    try {
      const [routineDetail, runList] = await Promise.all([
        getRoutine(accessToken, Number(routineId)),
        listRoutineRuns(accessToken, Number(routineId)),
      ]);
      setRoutine(routineDetail);
      upsertRoutine(routineDetail);
      setRuns(runList);
      setSelectedRunId((current) => current ?? runList[0]?.id ?? null);
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [accessToken, routineId]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const runDays = Array.from(new Set(runs.map((run) => run.startedAt.slice(0, 10))));
  const visibleRuns = selectedDay ? runs.filter((run) => run.startedAt.slice(0, 10) === selectedDay) : runs;
  const frequencyLabel = routine?.frequency === 'weekly' ? 'Weekly' : routine?.frequency === 'monthly' ? 'Monthly' : 'Daily';

  const handleRunNow = async () => {
    if (!accessToken || !routine) return;
    setTriggering(true);
    try {
      const run = await runRoutineNow(accessToken, routine.id);
      setRuns((prev) => [run, ...prev]);
      prependRecentRun({ ...run, routineName: routine.name });
      setSelectedRunId(run.id);
    } catch (error) {
      const message = error instanceof Error && error.message ? error.message : copy.saveError;
      addToast({ type: 'error', title: routine.name, message });
    } finally {
      setTriggering(false);
    }
  };

  // 2026-08-25: bỏ tự chạy khi mở trang — run đã lưu trong DB (outputText),
  // mở trang chỉ hiển thị run mới nhất; "Run now" là hành động chủ động.
  // Tự chạy mỗi lần mở khiến người dùng lúc nào cũng thấy trạng thái generating
  // và sinh run rác trong lịch sử.

  const toggleEnabled = async () => {
    if (!accessToken || !routine) return;
    const updated = await updateRoutine(accessToken, routine.id, { enabled: !routine.enabled });
    setRoutine(updated);
    upsertRoutine(updated);
  };

  const handleDelete = async () => {
    if (!accessToken || !routine) return;
    if (!window.confirm(copy.deleteConfirm)) return;
    await deleteRoutine(accessToken, routine.id);
    removeRoutine(routine.id);
    navigate('/routines');
  };

  const previewOf = (run: RoutineRun): string => {
    if (run.status === 'running') return copy.generatingTitle;
    if (run.status === 'error') return `${copy.errorPrefix} ${run.errorMessage ?? ''}`;
    return (run.outputText ?? '').slice(0, 80);
  };

  if (loading) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-12">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-[var(--color-surface-muted)]" />
        <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]"><div className="h-96 animate-pulse rounded-2xl bg-[var(--color-surface-muted)]" /><div className="h-64 animate-pulse rounded-2xl bg-[var(--color-surface-muted)]" /></div>
      </main>
    );
  }

  if (notFound || !routine) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
        <p role="alert" className="text-sm text-[var(--color-text-secondary)]">{copy.notFound}</p>
        <Button className="mt-4" variant="outline" icon={<ChevronLeft className="h-4 w-4" />} onClick={() => navigate('/routines')}>
          {copy.back}
        </Button>
      </main>
    );
  }

  const showGenerating = triggering || selectedRun?.status === 'running';

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:py-12">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <button type="button" className="mb-5 flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-primary)]" onClick={() => navigate('/routines')}><ChevronLeft className="h-4 w-4" /> {copy.back}</button>
          <div className="flex min-w-0 items-start gap-3">
            <div className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${routine.enabled ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]' : 'bg-[var(--color-surface-muted)] text-[var(--color-text-muted)]'}`}><Sparkles className="h-5 w-5" /></div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2"><h1 className="truncate font-display text-3xl tracking-tight text-[var(--color-text-primary)]">{routine.name}</h1><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${routine.enabled ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' : 'bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)]'}`}>{routine.enabled ? 'Active' : 'Paused'}</span></div>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-secondary)]"><span className="flex items-center gap-1.5"><Clock3 className="h-3.5 w-3.5" />{frequencyLabel} · {String(routine.hour).padStart(2, '0')}:00</span><span>{routine.timezone}</span></div>
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button size="sm" icon={triggering ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} onClick={() => void handleRunNow()} disabled={triggering}>{triggering ? copy.running : copy.runNow}</Button>
          <button type="button" className="app-icon-button p-1.5 rounded-lg" aria-label={routine.enabled ? copy.pause : copy.resume} title={routine.enabled ? copy.pause : copy.resume} onClick={() => void toggleEnabled()}>
            {routine.enabled ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </button>
          <button type="button" className="app-icon-button p-1.5 rounded-lg" aria-label={copy.deleteRoutine} title={copy.deleteRoutine} onClick={() => void handleDelete()}>
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section data-testid="routine-run-content" className="min-w-0 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 shadow-[var(--shadow-sm)] sm:p-8">
          {showGenerating ? (
            <div>
              <div className="flex items-center gap-2 text-lg font-semibold text-[var(--color-text-primary)]">
                <Sparkles className="h-5 w-5 animate-spin text-[var(--color-primary)]" />
                {copy.generatingTitle}
              </div>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{copy.generatingSubtitle}</p>
              <div className="mt-6 space-y-3" aria-hidden>
                {[100, 92, 84, 76, 60, 88, 70].map((width, index) => (
                  <div key={index} className="h-3 animate-pulse rounded-full bg-[var(--color-accent-soft)]" style={{ width: `${width}%` }} />
                ))}
              </div>
            </div>
          ) : selectedRun ? (
            selectedRun.status === 'error' ? (
              <p className="text-sm text-red-700 dark:text-red-300">{copy.errorPrefix} {selectedRun.errorMessage}</p>
            ) : (
              <div>
                <p className="mb-4 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
                  {new Date(selectedRun.startedAt).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })}
                </p>
                <MarkdownBody
                  source={selectedRun.outputText ?? ''}
                  className="space-y-4 text-sm leading-relaxed text-[var(--color-text-primary)]"
                />
              </div>
            )
          ) : (
            <div className="flex min-h-72 flex-col items-center justify-center text-center"><div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--color-accent-soft)] text-[var(--color-primary)]"><Sparkles className="h-5 w-5" /></div><p className="mt-4 max-w-sm text-sm text-[var(--color-text-secondary)]">{copy.noRunsYet}</p></div>
          )}
        </section>

        <aside className="flex flex-col gap-4">
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
            <div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]"><CalendarDays className="h-4 w-4 text-[var(--color-primary)]" />{copy.selectDay}</h2><span className="text-xs text-[var(--color-text-muted)]">{runs.length}</span></div>
            <div className="mt-3 flex flex-wrap gap-1.5"><button type="button" onClick={() => setSelectedDay(null)} className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${selectedDay === null ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}`}>{copy.allDays}</button>{runDays.map((day) => <button key={day} type="button" onClick={() => setSelectedDay(day)} className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${selectedDay === day ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'}`}>{new Date(`${day}T00:00:00`).toLocaleDateString(locale, { day: 'numeric', month: 'short' })}</button>)}</div>
          </div>
          <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">{copy.history}</h2>
            <div className="mt-3 flex flex-col gap-1.5">
            {visibleRuns.map((run) => (
              <button
                key={`${run.id}-${run.startedAt}`}
                type="button"
                onClick={() => setSelectedRunId(run.id)}
                className={`rounded-lg border px-3 py-2 text-left text-xs ${
                  run.id === selectedRunId
                    ? 'border-[var(--color-primary)] bg-[var(--color-accent-soft)]'
                    : 'border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)]'
                }`}
              >
                <p className="font-semibold text-[var(--color-text-primary)]">
                  {new Date(run.startedAt).toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' })}
                </p>
                <p className="mt-0.5 truncate text-[var(--color-text-secondary)]">{previewOf(run)}</p>
              </button>
            ))}
            {visibleRuns.length === 0 && <p className="py-4 text-xs text-[var(--color-text-secondary)]">{copy.noRunsYet}</p>}
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
};
