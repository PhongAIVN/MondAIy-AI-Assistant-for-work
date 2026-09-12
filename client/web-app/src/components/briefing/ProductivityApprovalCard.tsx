import {
  CalendarDays,
  Check,
  Clock3,
  ExternalLink,
  ListTodo,
  LoaderCircle,
  X,
} from 'lucide-react';

import type { ProductivityAction } from '../../types/conversation';
import { useEffect, useState } from 'react';

type Props = {
  action: ProductivityAction;
  language: 'en' | 'vi';
  busy?: 'approve' | 'reject' | null;
  onApprove: () => void;
  onReject: () => void;
  onSubmitClarification?: (message: string) => void;
};

function formatMoment(value: string | undefined, language: 'en' | 'vi'): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(language === 'vi' ? 'vi-VN' : 'en-US', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function ProductivityApprovalCard({
  action,
  language,
  busy = null,
  onApprove,
  onReject,
  onSubmitClarification,
}: Props) {
  const clarification = action.status === 'needs_clarification';
  const [title, setTitle] = useState(action.draft?.title || '');
  const [startsAt, setStartsAt] = useState(action.draft?.starts_at || '');
  const [endsAt, setEndsAt] = useState(action.draft?.ends_at || '');
  const [duration, setDuration] = useState(action.draft?.duration_minutes?.toString() || '');
  const [deadlineInput, setDeadlineInput] = useState(action.draft?.deadline || '');
  const [attendeesInput, setAttendeesInput] = useState((action.draft?.attendees || []).join(', '));

  useEffect(() => {
    setTitle(action.draft?.title || '');
    setStartsAt(action.draft?.starts_at || '');
    setEndsAt(action.draft?.ends_at || '');
    setDuration(action.draft?.duration_minutes?.toString() || '');
    setDeadlineInput(action.draft?.deadline || '');
    setAttendeesInput((action.draft?.attendees || []).join(', '));
  }, [action]);

  if (!clarification && !['pending_approval', 'created', 'rejected'].includes(action.status)) return null;

  if (clarification) {
    const isCalendarDraft = action.kind === 'calendar_event';
    const toNaturalDate = (value: string) => value ? new Date(value).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US') : '';
    const submitClarification = () => {
      if (!onSubmitClarification) return;
      const parts = [
        title.trim() && `tiêu đề: ${title.trim()}`,
        isCalendarDraft && startsAt && `bắt đầu: ${toNaturalDate(startsAt)}`,
        isCalendarDraft && endsAt && `kết thúc: ${toNaturalDate(endsAt)}`,
        isCalendarDraft && !endsAt && duration && `thời lượng: ${duration} phút`,
        isCalendarDraft && attendeesInput.trim() && `người tham dự: ${attendeesInput.trim()}`,
        !isCalendarDraft && deadlineInput && `deadline: ${toNaturalDate(deadlineInput)}`,
      ].filter(Boolean);
      if (parts.length) onSubmitClarification(parts.join('; '));
    };
    const canSubmit = Boolean(title.trim()) && (isCalendarDraft ? Boolean(startsAt && (endsAt || duration)) : Boolean(deadlineInput));
    return (
      <section aria-label={language === 'vi' ? 'Bản nháp cần bổ sung' : 'Draft needs details'} className="max-w-2xl rounded-2xl border border-[var(--color-primary)]/30 bg-[var(--color-surface)] p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent-soft)] text-[var(--color-primary)]"><CalendarDays className="h-4.5 w-4.5" /></div>
          <div><h3 className="font-semibold text-[var(--color-text-primary)]">{language === 'vi' ? 'Mình đã hiểu yêu cầu, cần bạn xác nhận thêm' : 'I understood the request, but need a few details'}</h3><p className="mt-1 text-xs leading-relaxed text-[var(--color-text-muted)]">{action.message}</p></div>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-[var(--color-text-secondary)] sm:col-span-2">{language === 'vi' ? 'Tiêu đề' : 'Title'} <span className="text-[var(--color-danger)]">*</span><input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>
          {isCalendarDraft && <label className="text-xs font-medium text-[var(--color-text-secondary)]">{language === 'vi' ? 'Bắt đầu' : 'Starts'} <span className="text-[var(--color-danger)]">*</span><input type="datetime-local" value={startsAt.slice(0, 16)} onChange={(e) => setStartsAt(e.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>}
          {isCalendarDraft && <label className="text-xs font-medium text-[var(--color-text-secondary)]">{language === 'vi' ? 'Kết thúc' : 'Ends'}<input type="datetime-local" value={endsAt.slice(0, 16)} onChange={(e) => { setEndsAt(e.target.value); setDuration(''); }} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>}
          {isCalendarDraft && <label className="text-xs font-medium text-[var(--color-text-secondary)] sm:col-span-2">{language === 'vi' ? 'Hoặc thời lượng (phút)' : 'Or duration (minutes)'}<input type="number" min="1" value={duration} onChange={(e) => { setDuration(e.target.value); setEndsAt(''); }} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>}
          {isCalendarDraft && <label className="text-xs font-medium text-[var(--color-text-secondary)] sm:col-span-2">{language === 'vi' ? 'Người tham dự (email, cách nhau bởi dấu phẩy)' : 'Attendees (comma-separated emails)'}<input type="text" value={attendeesInput} onChange={(e) => setAttendeesInput(e.target.value)} placeholder="lan@gmail.com, minh@gmail.com" className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>}
          {!isCalendarDraft && <label className="text-xs font-medium text-[var(--color-text-secondary)] sm:col-span-2">{language === 'vi' ? 'Hạn chót' : 'Deadline'} <input type="datetime-local" value={deadlineInput.slice(0, 16)} onChange={(e) => setDeadlineInput(e.target.value)} className="mt-1 w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-3 py-2 text-sm" /></label>}
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--color-border-subtle)] pt-3"><p className="text-xs text-[var(--color-text-muted)]">{language === 'vi' ? 'Chưa có gì được tạo. Bạn sẽ xem lại proposal trước khi submit.' : 'Nothing will be created yet. You will review a proposal before submitting.'}</p><button type="button" onClick={submitClarification} disabled={!canSubmit} className="rounded-xl bg-[var(--color-primary)] px-4 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{language === 'vi' ? 'Gửi thông tin' : 'Submit details'}</button></div>
      </section>
    );
  }

  const isCalendar = action.kind === 'calendar_event';
  const pending = action.status === 'pending_approval';
  const created = action.status === 'created';
  const start = formatMoment(action.draft?.starts_at, language);
  const end = formatMoment(action.draft?.ends_at, language);
  const deadline = formatMoment(action.draft?.deadline, language);
  const kindLabel = isCalendar
    ? 'Google Calendar'
    : action.kind === 'todo'
      ? 'Todo'
      : language === 'vi' ? 'Nhiệm vụ' : 'Task';

  return (
    <section
      aria-label={language === 'vi' ? 'Yêu cầu xác nhận hành động' : 'Action approval request'}
      className="relative max-w-2xl overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm"
    >
      <div
        className={`absolute inset-y-0 left-0 w-1 ${
          created
            ? 'bg-[var(--color-success)]'
            : action.status === 'rejected'
              ? 'bg-[var(--color-text-muted)]'
              : 'bg-[var(--color-primary)]'
        }`}
        aria-hidden="true"
      />

      <div className="space-y-4 px-4 py-4 sm:px-5">
        <header className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
              {isCalendar ? <CalendarDays className="h-4.5 w-4.5" /> : <ListTodo className="h-4.5 w-4.5" />}
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold tracking-[0.08em] text-[var(--color-text-muted)] uppercase">
                {kindLabel}
              </p>
              <h3 className="mt-0.5 text-[15px] font-semibold tracking-[-0.01em] text-[var(--color-text-primary)]">
                {action.draft?.title || (language === 'vi' ? 'Nội dung chưa đặt tên' : 'Untitled item')}
              </h3>
            </div>
          </div>

          <span className="inline-flex shrink-0 items-center gap-1.5 text-xs font-medium text-[var(--color-text-muted)]">
            {created ? (
              <><Check className="h-3.5 w-3.5 text-[var(--color-success)]" />{language === 'vi' ? 'Đã thực hiện' : 'Completed'}</>
            ) : action.status === 'rejected' ? (
              <><X className="h-3.5 w-3.5" />{language === 'vi' ? 'Đã từ chối' : 'Rejected'}</>
            ) : (
              <><Clock3 className="h-3.5 w-3.5 text-[var(--color-primary)]" />{language === 'vi' ? 'Chờ bạn duyệt' : 'Awaiting approval'}</>
            )}
          </span>
        </header>

        <dl className="grid gap-2 rounded-xl bg-[var(--color-surface-muted)] px-3.5 py-3 text-xs sm:grid-cols-2">
          {start && <div><dt className="text-[var(--color-text-muted)]">{language === 'vi' ? 'Bắt đầu' : 'Starts'}</dt><dd className="mt-0.5 font-medium tabular-nums text-[var(--color-text-primary)]">{start}</dd></div>}
          {end && <div><dt className="text-[var(--color-text-muted)]">{language === 'vi' ? 'Kết thúc' : 'Ends'}</dt><dd className="mt-0.5 font-medium tabular-nums text-[var(--color-text-primary)]">{end}</dd></div>}
          {deadline && <div className="sm:col-span-2"><dt className="text-[var(--color-text-muted)]">{language === 'vi' ? 'Hạn chót' : 'Deadline'}</dt><dd className="mt-0.5 font-medium tabular-nums text-[var(--color-text-primary)]">{deadline}</dd></div>}
          {(action.draft?.attendees?.length ?? 0) > 0 && <div className="sm:col-span-2"><dt className="text-[var(--color-text-muted)]">{language === 'vi' ? 'Người tham dự' : 'Attendees'}</dt><dd className="mt-0.5 font-medium text-[var(--color-text-primary)]">{action.draft?.attendees?.join(', ')}</dd></div>}
          {action.draft?.description && <div className="sm:col-span-2"><dt className="text-[var(--color-text-muted)]">{language === 'vi' ? 'Ghi chú' : 'Notes'}</dt><dd className="mt-0.5 leading-relaxed text-[var(--color-text-primary)]">{action.draft.description}</dd></div>}
        </dl>

        {pending && (
          <div className="flex flex-col gap-3 border-t border-[var(--color-border-subtle)] pt-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="max-w-md text-xs leading-relaxed text-[var(--color-text-muted)]">
              {language === 'vi'
                ? 'Chưa có thay đổi nào được thực hiện. Kiểm tra thông tin trước khi chấp nhận.'
                : 'Nothing has been changed yet. Review the details before approving.'}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={onReject}
                disabled={busy !== null}
                className="rounded-xl px-3.5 py-2 text-xs font-semibold text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === 'reject' && <LoaderCircle className="mr-1.5 inline h-3.5 w-3.5 animate-spin" />}
                {language === 'vi' ? 'Từ chối' : 'Reject'}
              </button>
              <button
                type="button"
                onClick={onApprove}
                disabled={busy !== null}
                className="rounded-xl bg-[var(--color-primary)] px-4 py-2 text-xs font-semibold text-white shadow-sm transition-transform hover:-translate-y-0.5 active:translate-y-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {busy === 'approve' && <LoaderCircle className="mr-1.5 inline h-3.5 w-3.5 animate-spin" />}
                {language === 'vi' ? 'Chấp nhận' : 'Approve'}
              </button>
            </div>
          </div>
        )}

        {created && action.result?.calendar_url && (
          <a
            href={action.result.calendar_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-primary)] hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-primary)]"
          >
            {language === 'vi' ? 'Mở trong Google Calendar' : 'Open in Google Calendar'}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
    </section>
  );
}
