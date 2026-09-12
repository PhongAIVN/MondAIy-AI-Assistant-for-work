import React, { useCallback, useState } from 'react';
import { AlertTriangle, Archive, Bell, CheckCircle2, Eye, EyeOff, Lock, Plus, RefreshCw, RotateCcw } from 'lucide-react';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';
import { Dialog } from '../../components/ui/Dialog';
import {
  actOnProgramEvent,
  createProgramEvent,
  listProgramEvents,
  updateProgramEvent,
  type AdminProgramEventList,
  type AdminProgramEventMutationResult,
  type AdminProgramEventRow,
} from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

/** Input được diễn giải theo múi giờ của thiết bị; giao diện ghi rõ để tránh admin hiểu nhầm. */
const toLocalInput = (iso: string): string => {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const fromLocalInput = (value: string): string => new Date(value).toISOString();

function fill(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce(
    (out, [key, value]) => out.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

type EventForm = {
  title: string;
  eventType: AdminProgramEventRow['eventType'];
  visibility: AdminProgramEventRow['visibility'];
  host: string;
  locationUrl: string;
  startAt: string;
  endAt: string;
  description: string;
  notifyUsers: boolean;
  changeNote: string;
};

const emptyForm = (): EventForm => ({
  title: '',
  eventType: 'custom',
  visibility: 'program',
  host: '',
  locationUrl: '',
  startAt: '',
  endAt: '',
  description: '',
  notifyUsers: false,
  changeNote: '',
});

const formFromEvent = (event: AdminProgramEventRow): EventForm => ({
  title: event.title,
  eventType: event.eventType,
  visibility: event.visibility,
  host: event.host ?? '',
  locationUrl: event.locationUrl ?? '',
  startAt: toLocalInput(event.startAt),
  endAt: event.endAt ? toLocalInput(event.endAt) : '',
  description: event.description,
  notifyUsers: false,
  changeNote: '',
});

const notificationCountFrom = (result: AdminProgramEventMutationResult | AdminProgramEventRow): number =>
  'notificationCount' in result ? (result.notificationCount ?? 0) : 0;

export const AdminProgramEventsPage: React.FC = () => {
  const { t, language } = useTranslation();
  const p = t.admin.programEventsPage;
  const scheduleTemplates: Array<Pick<EventForm, 'eventType' | 'title' | 'description'>> = [
    { eventType: 'daily_deadline', title: p.eventTypeDailyDeadline, description: p.quickDailyDescription },
    { eventType: 'weekly_deadline', title: p.eventTypeWeeklyDeadline, description: p.quickWeeklyDescription },
    { eventType: 'gate_deadline', title: p.eventTypeGateDeadline, description: p.quickGateDescription },
    { eventType: 'custom', title: p.quickWorkshopTitle, description: p.quickWorkshopDescription },
  ];
  const accessToken = useAuthStore((state) => state.accessToken);
  const [status, setStatus] = useState<string>('');
  const [conflictsOnly, setConflictsOnly] = useState(false);
  const [editingEvent, setEditingEvent] = useState<AdminProgramEventRow | null>(null);
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [publishingEvent, setPublishingEvent] = useState<AdminProgramEventRow | null>(null);
  const [form, setForm] = useState<EventForm>(emptyForm());
  const [operationError, setOperationError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const formatVietnamTime = useCallback(
    (iso: string | null): string =>
      iso
        ? new Date(iso).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US', {
            dateStyle: 'short',
            timeStyle: 'short',
            timeZone: 'Asia/Ho_Chi_Minh',
          })
        : '—',
    [language],
  );

  const eventTypeLabels: Record<AdminProgramEventRow['eventType'], string> = {
    custom: p.eventTypeCustom,
    daily_deadline: p.eventTypeDailyDeadline,
    weekly_deadline: p.eventTypeWeeklyDeadline,
    gate_deadline: p.eventTypeGateDeadline,
    mentor_duty: p.eventTypeMentorDuty,
  };

  const statusLabels: Record<AdminProgramEventRow['status'], string> = {
    draft: p.statusDraft,
    published: p.statusPublished,
    archived: p.statusArchived,
  };

  const statusStyles: Record<AdminProgramEventRow['status'], string> = {
    draft: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
    published: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
    archived: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  };

  const loadEvents = useCallback(
    (token: string) => listProgramEvents(token, { status: status || undefined, conflictsOnly, limit: 200 }),
    [status, conflictsOnly],
  );
  const { data, loading, error, reload } = useAdminData<AdminProgramEventList>(loadEvents, [status, conflictsOnly]);

  const runOperation = async (
    operation: () => Promise<AdminProgramEventMutationResult | AdminProgramEventRow>,
    success: (notificationCount: number) => string,
  ): Promise<boolean> => {
    if (!accessToken) return false;
    setRunning(true);
    setOperationError(null);
    setSuccessMessage(null);
    try {
      const result = await operation();
      setSuccessMessage(success(notificationCountFrom(result)));
      reload();
      return true;
    } catch (operationFailure) {
      setOperationError(
        operationFailure instanceof Error ? operationFailure.message : p.genericError,
      );
      return false;
    } finally {
      setRunning(false);
    }
  };

  const validateForm = (): boolean => {
    if (!form.title.trim() || !form.startAt) {
      setValidationError(p.validationRequired);
      return false;
    }
    if (form.endAt && new Date(form.endAt).getTime() <= new Date(form.startAt).getTime()) {
      setValidationError(p.validationEndBeforeStart);
      return false;
    }
    setValidationError(null);
    return true;
  };

  const saveEvent = async () => {
    if (!validateForm()) return;
    const publishedProgramEvent = editingEvent?.status === 'published' && form.visibility === 'program';
    const notifyUsers = Boolean(publishedProgramEvent && form.notifyUsers);
    const payload = {
      title: form.title.trim(),
      eventType: form.eventType,
      visibility: form.visibility,
      host: form.host.trim() || null,
      locationUrl: form.locationUrl.trim() || null,
      description: form.description.trim(),
      startAt: fromLocalInput(form.startAt),
      endAt: form.endAt ? fromLocalInput(form.endAt) : null,
      notifyUsers,
      changeNote: notifyUsers ? form.changeNote.trim() : undefined,
      expectedUpdatedAt: editingEvent?.updatedAt,
    };
    const saved = editingEvent
      ? await runOperation(
          () => updateProgramEvent(accessToken!, editingEvent.id, payload),
          (count) => count > 0 ? fill(p.savedWithNotifications, { count }) : p.savedNoRecipients,
        )
      : await runOperation(
          () => createProgramEvent(accessToken!, payload),
          () => p.createdDraft,
        );
    if (saved) {
      setEditingEvent(null);
      setCreatingEvent(false);
    }
  };

  const publishEvent = async () => {
    if (!publishingEvent) return;
    const published = await runOperation(
      () => actOnProgramEvent(accessToken!, publishingEvent.id, 'publish', {
        notifyUsers: false,
        changeNote: undefined,
        expectedUpdatedAt: publishingEvent.updatedAt,
      }),
      () => p.publishedNoRecipients,
    );
    if (published) {
      setPublishingEvent(null);
    }
  };

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">{t.admin.programEvents}</h1>
          <p className="mt-1 max-w-2xl text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            {p.subtitlePrefix} <strong>{p.subtitleEmphasis}</strong> {p.subtitleSuffix}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setForm(emptyForm());
              setCreatingEvent(true);
              setOperationError(null);
              setValidationError(null);
            }}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#2563A6] px-3 py-2 text-xs font-semibold text-white"
          >
            <Plus className="h-3.5 w-3.5" /> {p.addEvent}
          </button>
          <button type="button" onClick={reload} className="inline-flex items-center gap-1.5 rounded-xl border border-[#D5DDEB] px-3 py-2 text-xs font-semibold text-[#2563A6] dark:border-[#1A2A42]">
            <RefreshCw className="h-3.5 w-3.5" /> {p.reload}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {(['', 'published', 'draft', 'archived'] as const).map((value) => (
          <button
            key={value || 'all'}
            type="button"
            aria-pressed={status === value}
            onClick={() => setStatus(value)}
            className={`rounded-xl border px-3 py-1.5 text-xs font-semibold ${status === value ? 'border-[#2563A6] bg-[#2563A6] text-white' : 'border-[#D5DDEB] text-[#5A6A85] dark:border-[#1A2A42]'}`}
          >
            {value === '' ? p.filterAll : statusLabels[value]}
          </button>
        ))}
        <label className="ml-2 inline-flex items-center gap-1.5 text-xs text-[#5A6A85] dark:text-[#8B98AB]">
          <input type="checkbox" checked={conflictsOnly} onChange={(event) => setConflictsOnly(event.target.checked)} />
          {p.conflictsOnlyLabel}
          {(data?.conflictCount ?? 0) > 0 && <span className="rounded-lg bg-red-100 px-1.5 py-0.5 font-semibold text-red-700">{data?.conflictCount}</span>}
        </label>
      </div>

      {operationError && !editingEvent && !creatingEvent && <AdminError message={operationError} onRetry={reload} />}
      {successMessage && (
        <div role="status" className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">
          <CheckCircle2 className="h-4 w-4" /> {successMessage}
        </div>
      )}
      {loading && <AdminLoading label={p.loadingLabel} />}
      {error && <AdminError message={error} onRetry={reload} />}
      {data && items.length === 0 && <AdminEmpty title={p.emptyTitle} hint={p.emptyHint} />}

      <div className="space-y-2">
        {items.map((event) => (
          <article key={event.id} className={`rounded-2xl border p-4 ${event.sourceConflict ? 'border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-950/20' : 'border-[#D5DDEB] dark:border-[#1A2A42]'}`}>
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className={`rounded-lg px-2 py-0.5 text-[11px] font-semibold ${statusStyles[event.status]}`}>{statusLabels[event.status]}</span>
              <span className="text-[11px] text-[#5A6A85]">{eventTypeLabels[event.eventType]}</span>
              {event.origin === 'admin' && <span className="rounded-lg bg-[#EDF2FB] px-2 py-0.5 text-[11px] text-[#2563A6] dark:bg-[#0A1628]">{p.originAdminBadge}</span>}
              {event.lockedFields.length > 0 && <span className="inline-flex items-center gap-1 text-[11px] text-amber-700 dark:text-amber-300"><Lock className="h-3 w-3" /> {fill(p.lockedFieldsLabel, { fields: event.lockedFields.join(', ') })}</span>}
              {event.visibility === 'team' && <span className="text-[11px] text-[#5A6A85]">{p.visibilityTeamBadge}</span>}
            </div>
            <h2 className="text-sm font-semibold text-[#0F1F38] dark:text-white">{event.title}</h2>
            <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
              {formatVietnamTime(event.startAt)}{event.endAt ? ` → ${formatVietnamTime(event.endAt)}` : ''}{event.host ? ` ${fill(p.hostedBy, { host: event.host })}` : ''} {p.vietnamTimeSuffix}
            </div>
            {event.sourceConflict && event.feedPayload && (
              <div className="mt-2 flex items-start gap-1.5 text-xs text-red-700 dark:text-red-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{fill(p.conflictNotice, { title: event.feedPayload.title ?? '', date: formatVietnamTime(event.feedPayload.starts_at ?? null) })}</span>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => { setForm(formFromEvent(event)); setEditingEvent(event); setOperationError(null); setValidationError(null); }} className="rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#2563A6] dark:border-[#1A2A42]">{p.edit}</button>
              {event.status !== 'published' ? (
                <button type="button" disabled={running} onClick={() => setPublishingEvent(event)} className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50"><Eye className="h-3.5 w-3.5" /> {p.publish}</button>
              ) : (
                <button type="button" disabled={running} onClick={() => runOperation(() => actOnProgramEvent(accessToken!, event.id, 'unpublish'), () => p.unpublished)} className="inline-flex items-center gap-1 rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42] disabled:opacity-50"><EyeOff className="h-3.5 w-3.5" /> {p.unpublish}</button>
              )}
              {event.status !== 'archived' && <button type="button" disabled={running} onClick={() => runOperation(() => actOnProgramEvent(accessToken!, event.id, 'archive'), () => p.archived)} className="inline-flex items-center gap-1 rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42] disabled:opacity-50"><Archive className="h-3.5 w-3.5" /> {p.archive}</button>}
              {event.origin === 'feed' && event.lockedFields.length > 0 && <button type="button" disabled={running} onClick={() => runOperation(() => actOnProgramEvent(accessToken!, event.id, 'revert-to-source'), () => p.reverted)} className="inline-flex items-center gap-1 rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42] disabled:opacity-50"><RotateCcw className="h-3.5 w-3.5" /> {p.revert}</button>}
            </div>
          </article>
        ))}
      </div>

      <Dialog
        isOpen={Boolean(editingEvent || creatingEvent)}
        onClose={() => { if (!running) { setEditingEvent(null); setCreatingEvent(false); } }}
        title={creatingEvent ? p.dialogCreateTitle : p.dialogEditTitle}
        description={p.dialogDescription}
        maxWidth="lg"
        footer={<><button type="button" disabled={running} onClick={() => { setEditingEvent(null); setCreatingEvent(false); }} className="rounded-xl border border-[#D5DDEB] px-3 py-2 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42]">{p.cancel}</button><button type="button" disabled={running || !form.title.trim() || !form.startAt} onClick={saveEvent} className="rounded-xl bg-[#2563A6] px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">{creatingEvent ? p.createDraft : p.saveChanges}</button></>}
      >
        {editingEvent?.origin === 'feed' && <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-700 dark:bg-amber-950/20 dark:text-amber-300">{p.feedOriginNotice}</p>}
        {validationError && <div role="alert" className="rounded-xl bg-red-50 p-3 text-xs text-red-700">{validationError}</div>}
        {operationError && <AdminError message={operationError} />}
        {creatingEvent && (
          <div className="rounded-xl border border-[#D5DDEB] p-3 dark:border-[#1A2A42]">
            <p className="text-[11px] font-semibold text-[#5A6A85] dark:text-[#8B98AB]">{p.quickTemplatesLabel}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {scheduleTemplates.map((template) => (
                <button
                  key={template.eventType}
                  type="button"
                  onClick={() => setForm((current) => ({ ...current, ...template }))}
                  className="rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#2563A6] dark:border-[#1A2A42]"
                >
                  {template.title}
                </button>
              ))}
            </div>
          </div>
        )}
        <label className="block text-xs text-[#5A6A85]">{p.fieldTitle}<input data-autofocus value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-[#5A6A85]">{p.fieldEventType}<select value={form.eventType} onChange={(event) => setForm({ ...form, eventType: event.target.value as EventForm['eventType'] })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]">{(Object.entries(eventTypeLabels) as [AdminProgramEventRow['eventType'], string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="block text-xs text-[#5A6A85]">{p.fieldVisibility}<select value={form.visibility} onChange={(event) => setForm({ ...form, visibility: event.target.value as EventForm['visibility'], notifyUsers: event.target.value === 'team' ? false : form.notifyUsers })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"><option value="program">{p.visibilityProgramOption}</option><option value="team">{p.visibilityTeamOption}</option></select></label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-[#5A6A85]">{p.fieldStart}<input type="datetime-local" value={form.startAt} onChange={(event) => setForm({ ...form, startAt: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
          <label className="block text-xs text-[#5A6A85]">{p.fieldEnd}<input type="datetime-local" value={form.endAt} onChange={(event) => setForm({ ...form, endAt: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-[#5A6A85]">{p.fieldHost}<input value={form.host} onChange={(event) => setForm({ ...form, host: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
          <label className="block text-xs text-[#5A6A85]">{p.fieldLocationUrl}<input type="url" value={form.locationUrl} onChange={(event) => setForm({ ...form, locationUrl: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        </div>
        <label className="block text-xs text-[#5A6A85]">{p.fieldDescription}<textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        {editingEvent?.status === 'published' && (
          <div className="rounded-xl border border-[#D5DDEB] p-3 dark:border-[#1A2A42]">
            <label className="flex items-start gap-2 text-xs font-semibold text-[#0F1F38] dark:text-white"><input type="checkbox" checked={form.notifyUsers} disabled={form.visibility === 'team'} onChange={(event) => setForm({ ...form, notifyUsers: event.target.checked })} /><span><Bell className="mr-1 inline h-3.5 w-3.5" />{p.notifyLabel}</span></label>
            {form.visibility === 'team' && <p className="mt-1 text-[11px] text-[#5A6A85]">{p.notifyTeamUnsupported}</p>}
            {form.notifyUsers && <label className="mt-2 block text-xs text-[#5A6A85]">{p.changeNoteLabel}<input value={form.changeNote} onChange={(event) => setForm({ ...form, changeNote: event.target.value })} placeholder={p.changeNotePlaceholder} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>}
          </div>
        )}
      </Dialog>

      <Dialog
        isOpen={Boolean(publishingEvent)}
        onClose={() => !running && setPublishingEvent(null)}
        title={p.confirmPublishTitle}
        description={publishingEvent ? fill(p.confirmPublishDesc, { title: publishingEvent.title }) : undefined}
        maxWidth="sm"
        footer={<><button type="button" disabled={running} onClick={() => setPublishingEvent(null)} className="rounded-xl border border-[#D5DDEB] px-3 py-2 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42]">{p.cancel}</button><button type="button" disabled={running} onClick={publishEvent} className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">{p.confirmPublishButton}</button></>}
      >
        <p data-autofocus tabIndex={-1} className="text-xs text-[#5A6A85]">
          {p.confirmPublishBody}
        </p>
      </Dialog>
    </div>
  );
};
