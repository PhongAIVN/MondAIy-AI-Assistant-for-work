import React, { useCallback, useMemo, useState } from 'react';
import { Archive, BookOpenCheck, CalendarDays, CheckCircle2, HelpCircle, Pencil, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';
import { Dialog } from '../../components/ui/Dialog';
import {
  actOnProgramInformation,
  createProgramInformation,
  listProgramInformation,
  listProgramInformationRequests,
  resolveProgramInformationRequest,
  updateProgramInformation,
  type AdminProgramInformationItem,
  type AdminProgramInformationCategory,
  type AdminProgramInformationRequest,
} from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

type WorkspaceData = {
  information: AdminProgramInformationItem[];
  requests: AdminProgramInformationRequest[];
};

type InformationForm = {
  category: AdminProgramInformationCategory;
  title: string;
  body: string;
  aliases: string;
  sourceUrl: string;
  visibility: AdminProgramInformationItem['visibility'];
};

const emptyForm = (): InformationForm => ({
  category: 'overview',
  title: '',
  body: '',
  aliases: '',
  sourceUrl: '',
  visibility: 'program',
});

const formFromItem = (item: AdminProgramInformationItem): InformationForm => ({
  category: item.category,
  title: item.title,
  body: item.body,
  aliases: item.aliases.join(', '),
  sourceUrl: item.sourceUrl ?? '',
  visibility: item.visibility,
});

function fill(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce(
    (out, [key, value]) => out.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

export const AdminProgramsPage: React.FC = () => {
  const { t, language } = useTranslation();
  const p = t.admin.programsPage;
  const accessToken = useAuthStore((state) => state.accessToken);
  const [activeTab, setActiveTab] = useState<'information' | 'requests'>('information');
  const [statusFilter, setStatusFilter] = useState<'all' | AdminProgramInformationItem['status']>('all');
  const [editingItem, setEditingItem] = useState<AdminProgramInformationItem | null>(null);
  const [answeringRequest, setAnsweringRequest] = useState<AdminProgramInformationRequest | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<InformationForm>(emptyForm());
  const [operationError, setOperationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [resolutionByRequest, setResolutionByRequest] = useState<Record<number, string>>({});

  const formatDate = useCallback(
    (iso: string): string =>
      new Date(iso).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-US', { dateStyle: 'short', timeStyle: 'short' }),
    [language],
  );

  const statusFilterLabels: Record<'all' | AdminProgramInformationItem['status'], string> = {
    all: p.filterAll,
    published: p.filterPublished,
    draft: p.filterDraft,
    archived: p.filterArchived,
  };

  const categoryLabels: Record<AdminProgramInformationCategory, string> = {
    overview: p.categoryOverview,
    schedule: p.categorySchedule,
    policy: p.categoryPolicy,
    submission: p.categorySubmission,
    support: p.categorySupport,
    other: p.categoryOther,
  };

  const loadWorkspace = useCallback(async (token: string): Promise<WorkspaceData> => {
    const [information, requests] = await Promise.all([
      listProgramInformation(token, { limit: 200 }),
      listProgramInformationRequests(token, { status: 'open', limit: 200 }),
    ]);
    return { information: information.items, requests: requests.items };
  }, []);
  const { data, loading, error, reload } = useAdminData<WorkspaceData>(loadWorkspace);

  const information = data?.information ?? [];
  const openRequests = useMemo(
    () => (data?.requests ?? []).filter((request) => request.status === 'open'),
    [data?.requests],
  );
  const hasUnpublishedChanges = (item: AdminProgramInformationItem): boolean =>
    item.version !== item.publishedVersion;
  const visibleInformation = information.filter((item) => {
    if (statusFilter === 'all') return true;
    if (statusFilter === 'draft') return item.status === 'draft' || hasUnpublishedChanges(item);
    return item.status === statusFilter && !hasUnpublishedChanges(item);
  });
  const publishedInformation = information.filter(
    (item) => item.status === 'published' && !hasUnpublishedChanges(item),
  );

  const openCreateDialog = (request?: AdminProgramInformationRequest) => {
    setEditingItem(null);
    setAnsweringRequest(request ?? null);
    setForm({ ...emptyForm(), title: request?.sharedQuestion ?? '' });
    setOperationError(null);
    setFormOpen(true);
  };

  const openEditDialog = (item: AdminProgramInformationItem) => {
    setEditingItem(item);
    setAnsweringRequest(null);
    setForm(formFromItem(item));
    setOperationError(null);
    setFormOpen(true);
  };

  const runOperation = async (operation: () => Promise<unknown>, message: string) => {
    if (!accessToken) return false;
    setSaving(true);
    setOperationError(null);
    setSuccessMessage(null);
    try {
      await operation();
      setSuccessMessage(message);
      reload();
      return true;
    } catch (operationFailure) {
      setOperationError(
        operationFailure instanceof Error ? operationFailure.message : p.errorGeneric,
      );
      return false;
    } finally {
      setSaving(false);
    }
  };

  const saveInformation = async () => {
    const payload = {
      category: form.category,
      title: form.title.trim(),
      body: form.body.trim(),
      aliases: form.aliases.split(',').map((alias) => alias.trim()).filter(Boolean),
      sourceUrl: form.sourceUrl.trim() || null,
      visibility: form.visibility,
    };
    let savedItem: AdminProgramInformationItem | null = null;
    const saved = await runOperation(
        async () => {
          savedItem = editingItem
            ? await updateProgramInformation(accessToken!, editingItem.id, {
              ...payload,
              expectedVersion: editingItem.version,
            })
            : await createProgramInformation(accessToken!, payload);
          return savedItem;
        },
        editingItem ? p.savedMessage : p.createdDraftMessage,
      );
    if (saved) {
      if (answeringRequest && savedItem) {
        setResolutionByRequest((current) => ({
          ...current,
          [answeringRequest.id]: String(savedItem!.id),
        }));
        setSuccessMessage(p.draftFromRequestMessage);
      }
      setFormOpen(false);
      setEditingItem(null);
      setAnsweringRequest(null);
    }
  };

  const resolveRequest = async (request: AdminProgramInformationRequest) => {
    const itemId = Number(resolutionByRequest[request.id]);
    if (!itemId) {
      setOperationError(p.selectPublishedError);
      return;
    }
    const selectedItem = publishedInformation.find((item) => item.id === itemId);
    if (!selectedItem?.publishedVersion) {
      setOperationError(p.invalidPublishedVersionError);
      return;
    }
    await runOperation(
      () => resolveProgramInformationRequest(
        accessToken!,
        request.id,
        itemId,
        selectedItem.publishedVersion!,
      ),
      p.resolvedMessage,
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.programs}
          </h1>
          <p className="mt-1 max-w-2xl text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            {p.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/admin/program-events"
            className="inline-flex items-center gap-1.5 rounded-xl border border-[#D5DDEB] px-3 py-2 text-xs font-semibold text-[#2563A6] dark:border-[#1A2A42]"
          >
            <CalendarDays className="h-4 w-4" /> {p.updateSchedule}
          </Link>
          <button
            type="button"
            onClick={() => openCreateDialog()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-[#2563A6] px-3 py-2 text-xs font-semibold text-white"
          >
            <Plus className="h-4 w-4" /> {p.addInformation}
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-[#D5DDEB] p-4 dark:border-[#1A2A42]">
          <div className="text-2xl font-bold text-[#0F1F38] dark:text-white">{publishedInformation.length}</div>
          <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{p.statPublished}</div>
        </div>
        <div className="rounded-2xl border border-[#D5DDEB] p-4 dark:border-[#1A2A42]">
          <div className="text-2xl font-bold text-amber-700 dark:text-amber-300">{openRequests.length}</div>
          <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{p.statOpenRequests}</div>
        </div>
        <div className="rounded-2xl border border-[#D5DDEB] p-4 dark:border-[#1A2A42]">
          <div className="text-2xl font-bold text-[#0F1F38] dark:text-white">
            {information.filter((item) => item.status === 'draft' || hasUnpublishedChanges(item)).length}
          </div>
          <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{p.statDrafts}</div>
        </div>
      </div>

      <div className="flex gap-2 border-b border-[#D5DDEB] dark:border-[#1A2A42]">
        <button
          type="button"
          aria-pressed={activeTab === 'information'}
          onClick={() => setActiveTab('information')}
          className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold ${activeTab === 'information' ? 'border-b-2 border-[#2563A6] text-[#2563A6]' : 'text-[#5A6A85]'}`}
        >
          <BookOpenCheck className="h-4 w-4" /> {p.tabVerified}
        </button>
        <button
          type="button"
          aria-pressed={activeTab === 'requests'}
          onClick={() => setActiveTab('requests')}
          className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-semibold ${activeTab === 'requests' ? 'border-b-2 border-[#2563A6] text-[#2563A6]' : 'text-[#5A6A85]'}`}
        >
          <HelpCircle className="h-4 w-4" /> {p.tabRequests}
          {openRequests.length > 0 && <span className="rounded-full bg-amber-100 px-1.5 text-amber-800">{openRequests.length}</span>}
        </button>
      </div>

      {operationError && !formOpen && <AdminError message={operationError} onRetry={reload} />}
      {successMessage && (
        <div role="status" className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200">
          <CheckCircle2 className="h-4 w-4" /> {successMessage}
        </div>
      )}
      {loading && <AdminLoading label={p.loadingLabel} />}
      {error && <AdminError message={error} onRetry={reload} />}

      {!loading && !error && activeTab === 'information' && (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {(['all', 'published', 'draft', 'archived'] as const).map((filter) => (
              <button
                key={filter}
                type="button"
                aria-pressed={statusFilter === filter}
                onClick={() => setStatusFilter(filter)}
                className={`rounded-xl border px-3 py-1.5 text-xs font-semibold ${statusFilter === filter ? 'border-[#2563A6] bg-[#2563A6] text-white' : 'border-[#D5DDEB] text-[#5A6A85] dark:border-[#1A2A42]'}`}
              >
                {statusFilterLabels[filter]}
              </button>
            ))}
          </div>
          {visibleInformation.length === 0 ? (
            <AdminEmpty title={p.emptyInformationTitle} hint={p.emptyInformationHint} />
          ) : visibleInformation.map((item) => (
            <article key={item.id} className="rounded-2xl border border-[#D5DDEB] p-4 dark:border-[#1A2A42]">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="rounded-lg bg-[#EDF2FB] px-2 py-0.5 text-[#2563A6] dark:bg-[#0A1628]">{categoryLabels[item.category]}</span>
                    <span className={item.status === 'published' && !hasUnpublishedChanges(item) ? 'text-emerald-700' : 'text-amber-700'}>
                      {hasUnpublishedChanges(item) ? p.statusUnpublishedChanges : item.status === 'published' ? p.statusPublished : item.status === 'draft' ? p.statusDraft : p.statusArchived}
                    </span>
                    {item.visibility === 'public' && <span className="text-[#5A6A85]">{p.visibilityPublic}</span>}
                  </div>
                  <h2 className="text-sm font-bold text-[#0F1F38] dark:text-white">{item.title}</h2>
                  <p className="mt-1 whitespace-pre-wrap text-xs text-[#5A6A85] dark:text-[#8B98AB]">{item.body}</p>
                  <div className="mt-2 text-[11px] text-[#5A6A85]">{fill(p.versionLabel, { version: item.version, date: formatDate(item.updatedAt) })}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => openEditDialog(item)} className="inline-flex items-center gap-1 rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#2563A6] dark:border-[#1A2A42]">
                    <Pencil className="h-3.5 w-3.5" /> {p.edit}
                  </button>
                  {item.status !== 'archived' && hasUnpublishedChanges(item) && (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => runOperation(() => actOnProgramInformation(accessToken!, item.id, 'publish', item.version), p.publishedMessage)}
                      className="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      {p.publish}
                    </button>
                  )}
                  {item.status !== 'archived' && (
                    <button
                      type="button"
                      disabled={saving}
                      onClick={() => runOperation(() => actOnProgramInformation(accessToken!, item.id, 'archive', item.version), p.archivedMessage)}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#D5DDEB] px-2.5 py-1 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42] disabled:opacity-50"
                    >
                      <Archive className="h-3.5 w-3.5" /> {p.archive}
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && !error && activeTab === 'requests' && (
        <div className="space-y-3">
          {openRequests.length === 0 ? (
            <AdminEmpty title={p.emptyRequestsTitle} hint={p.emptyRequestsHint} />
          ) : openRequests.map((request) => (
            <article key={request.id} className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4 dark:border-amber-900 dark:bg-amber-950/10">
              <div className="text-[11px] text-[#5A6A85]">{fill(p.askedAt, { date: formatDate(request.createdAt) })}</div>
              <h2 className="mt-1 text-sm font-bold text-[#0F1F38] dark:text-white">{request.sharedQuestion}</h2>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <button type="button" onClick={() => openCreateDialog(request)} className="rounded-xl bg-[#2563A6] px-3 py-2 text-xs font-semibold text-white">
                  {p.composeAnswer}
                </button>
                <select
                  aria-label={fill(p.resolutionSelectAriaLabel, { question: request.sharedQuestion })}
                  value={resolutionByRequest[request.id] ?? ''}
                  onChange={(event) => setResolutionByRequest((current) => ({ ...current, [request.id]: event.target.value }))}
                  className="min-w-0 flex-1 rounded-xl border border-[#D5DDEB] bg-white px-3 py-2 text-xs dark:border-[#1A2A42] dark:bg-[#0A1628]"
                >
                  <option value="">{p.resolutionPlaceholder}</option>
                  {publishedInformation.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                </select>
                <button type="button" disabled={saving || !resolutionByRequest[request.id]} onClick={() => resolveRequest(request)} className="rounded-xl border border-[#2563A6] px-3 py-2 text-xs font-semibold text-[#2563A6] disabled:opacity-40">
                  {p.markAnswered}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}

      <Dialog
        isOpen={formOpen}
        onClose={() => !saving && setFormOpen(false)}
        title={editingItem ? p.dialogEditTitle : p.dialogCreateTitle}
        description={answeringRequest ? fill(p.dialogAnsweringDesc, { question: answeringRequest.sharedQuestion }) : p.dialogDefaultDesc}
        maxWidth="lg"
        footer={(
          <>
            <button type="button" onClick={() => setFormOpen(false)} disabled={saving} className="rounded-xl border border-[#D5DDEB] px-3 py-2 text-xs font-semibold text-[#5A6A85] dark:border-[#1A2A42]">{p.cancel}</button>
            <button type="button" onClick={saveInformation} disabled={saving || !form.title.trim() || !form.body.trim()} className="rounded-xl bg-[#2563A6] px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">
              {editingItem ? p.saveChanges : p.createDraft}
            </button>
          </>
        )}
      >
        {operationError && <AdminError message={operationError} />}
        <label className="block text-xs text-[#5A6A85]">{p.fieldTitle}<input data-autofocus value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        <label className="block text-xs text-[#5A6A85]">{p.fieldBody}<textarea rows={6} value={form.body} onChange={(event) => setForm({ ...form, body: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-[#5A6A85]">{p.fieldCategory}<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value as AdminProgramInformationCategory })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]">{(Object.entries(categoryLabels) as [AdminProgramInformationCategory, string][]).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="block text-xs text-[#5A6A85]">{p.fieldVisibility}<select value={form.visibility} onChange={(event) => setForm({ ...form, visibility: event.target.value as InformationForm['visibility'] })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"><option value="program">{p.visibilityProgramOption}</option><option value="public">{p.visibilityPublicOption}</option></select></label>
        </div>
        <label className="block text-xs text-[#5A6A85]">{p.fieldAliases}<input value={form.aliases} onChange={(event) => setForm({ ...form, aliases: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
        <label className="block text-xs text-[#5A6A85]">{p.fieldSourceUrl}<input type="url" value={form.sourceUrl} onChange={(event) => setForm({ ...form, sourceUrl: event.target.value })} className="mt-1 w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]" /></label>
      </Dialog>
    </div>
  );
};
