import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowUp,
  FileText,
  Folder,
  LogOut,
  MessagesSquare,
  Mic,
  MoreHorizontal,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from 'lucide-react';

import { useTranslation } from '../i18n/useTranslation';
import {
  fetchProjectOverview,
  removeConversationFromProject,
  type ProjectOverview,
} from '../lib/projectsApi';
import { useAppStore } from '../stores/useAppStore';
import { useAuthStore } from '../stores/useAuthStore';

type ProjectTab = 'chats' | 'notes';

export const ProjectDetailPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const { language } = useTranslation();
  const vi = language === 'vi';
  const navigate = useNavigate();
  const accessToken = useAuthStore((s) => s.accessToken);
  const addToast = useAppStore((s) => s.addToast);

  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ProjectTab>('chats');
  const [filter, setFilter] = useState<'all' | 'chats' | 'notes'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [question, setQuestion] = useState('');

  const load = useCallback(
    async (refresh = false) => {
      if (!accessToken || !projectId) return;
      if (refresh) setRefreshing(true);
      else setLoading(true);
      setLoadError(null);
      try {
        setOverview(await fetchProjectOverview(accessToken, Number(projectId), { refresh, language }));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setLoadError(message);
        addToast({ type: 'error', title: vi ? 'Không tải được dự án' : 'Could not load project', message });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [accessToken, projectId, language, addToast, vi],
  );

  useEffect(() => { void load(); }, [load]);

  const handleRemove = async (conversationId: number) => {
    if (!accessToken) return;
    try {
      await removeConversationFromProject(accessToken, conversationId);
      await load();
    } catch (error) {
      addToast({
        type: 'error',
        title: vi ? 'Không gỡ được hội thoại' : 'Could not remove conversation',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const handleAsk = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (question.trim()) navigate('/briefing');
  };

  const filteredConversations = useMemo(() => {
    const normalized = searchQuery.trim().toLowerCase();
    return (overview?.conversations ?? []).filter((item) => !normalized || item.title.toLowerCase().includes(normalized));
  }, [overview?.conversations, searchQuery]);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6" aria-busy="true">
        <div className="h-5 w-32 animate-pulse rounded bg-[var(--color-surface-muted)]" />
        <div className="mt-12 h-32 animate-pulse rounded-3xl bg-[var(--color-surface-muted)]" />
        <div className="mt-8 h-5 w-56 animate-pulse rounded bg-[var(--color-surface-muted)]" />
        <div className="mt-4 h-72 animate-pulse rounded-3xl bg-[var(--color-surface-muted)]" />
      </div>
    );
  }

  if (!overview) {
    return (
      <main className="mx-auto flex min-h-[70dvh] w-full max-w-xl items-center justify-center px-6 text-center">
        <section role="alert" className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-[0_20px_60px_var(--color-shadow)]">
          <p className="font-heading text-xl font-semibold text-[var(--color-text-primary)]">{vi ? 'Không mở được dự án' : 'This project could not be opened'}</p>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{loadError ?? (vi ? 'Thử tải lại để tiếp tục.' : 'Try loading it again to continue.')}</p>
          <button type="button" onClick={() => void load()} className="mt-5 rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--color-on-primary)] transition hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]">{vi ? 'Tải lại' : 'Try again'}</button>
        </section>
      </main>
    );
  }

  const { project, conversations, meetings = [], summary, summaryUpdatedAt } = overview;
  const filteredMeetings = meetings.filter((item) => !searchQuery.trim() || item.title.toLowerCase().includes(searchQuery.trim().toLowerCase()));
  const empty = (activeTab === 'chats' && conversations.length === 0) || (activeTab === 'notes' && meetings.length === 0);

  return (
    <div className="min-h-[calc(100dvh-1rem)] bg-[var(--color-app-bg)] pb-12">
      <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between gap-4">
          <button type="button" onClick={() => navigate('/projects')} className="group flex min-w-0 items-center gap-3 rounded-xl px-2 py-1.5 text-left transition hover:bg-[var(--color-surface-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]">
            <Folder className="h-5 w-5 shrink-0 text-[var(--color-text-muted)] transition group-hover:text-[var(--color-text-primary)]" />
            <span className="truncate font-heading text-xl text-[var(--color-text-primary)]">{project.name}</span>
          </button>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => navigate(`/meeting-notes?projectId=${projectId}`)}
              aria-label={vi ? 'Cuộc họp mới' : 'New meeting'}
              className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-xl bg-[var(--color-primary)] px-3 py-2 text-sm font-semibold text-[var(--color-on-primary)] shadow-[0_8px_24px_var(--color-shadow)] transition hover:-translate-y-0.5 hover:brightness-110 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] sm:px-4 sm:py-2.5"
            >
              <Mic className="h-4 w-4 shrink-0" />
              <span className="hidden sm:inline">{vi ? 'Cuộc họp mới' : 'New meeting'}</span>
            </button>
          </div>
        </header>

        <section className="mt-9">
          <form onSubmit={handleAsk} className="app-composer-hero relative overflow-hidden rounded-[1.75rem] border p-5 sm:p-7">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_70%_0%,var(--color-accent-soft),transparent_68%)] opacity-60" />
            <label htmlFor="project-question" className="relative block text-sm text-[var(--color-text-muted)]">{vi ? 'Hỏi về dự án này' : 'Ask about this project'}</label>
            <input id="project-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={vi ? 'Bạn muốn biết điều gì?' : 'What would you like to know?'} className="relative mt-7 w-full bg-transparent text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]" />
            <div className="relative mt-7 flex items-center justify-between gap-3">
              <button type="button" onClick={() => navigate('/briefing')} className="rounded-xl border border-[var(--color-border)] p-2 text-[var(--color-text-secondary)] transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]" aria-label={vi ? 'Mở chat mới' : 'Open a new chat'} title={vi ? 'Mở chat mới' : 'Open a new chat'}><span className="block text-xl leading-none">+</span></button>
              <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"><button type="submit" disabled={!question.trim()} aria-label={vi ? 'Gửi câu hỏi' : 'Send question'} className="ml-1 rounded-full bg-[var(--color-primary)] p-2.5 text-[var(--color-on-primary)] transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"><ArrowUp className="h-4 w-4" /></button></div>
            </div>
          </form>
        </section>

        <nav className="mt-10 flex items-end gap-7 border-b border-[var(--color-border)]" aria-label={vi ? 'Nội dung dự án' : 'Project content'}>
          {([{ id: 'chats' as const, label: vi ? 'Chat' : 'Chats', count: conversations.length }, { id: 'notes' as const, label: vi ? 'Ghi chú' : 'Notes', count: meetings.length }]).map((tab) => (
            <button key={tab.id} type="button" onClick={() => setActiveTab(tab.id)} className={`border-b-2 pb-3 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${activeTab === tab.id ? 'border-[var(--color-text-primary)] font-semibold text-[var(--color-text-primary)]' : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]'}`}>{tab.label} <span className="ml-1 text-xs opacity-70">{tab.count}</span></button>
          ))}
          <button type="button" onClick={() => navigate('/projects')} className="mb-2 ml-auto rounded-lg p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]" aria-label={vi ? 'Tuỳ chỉnh dự án' : 'Customize project'} title={vi ? 'Tuỳ chỉnh dự án' : 'Customize project'}><MoreHorizontal className="h-5 w-5" /></button>
        </nav>

        {activeTab === 'chats' ? (
          <>
            <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center">
              <label className="flex min-w-0 flex-1 items-center gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 transition focus-within:border-[var(--color-accent)]"><Search className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" /><span className="sr-only">{vi ? 'Tìm kiếm' : 'Search'}</span><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={vi ? 'Tìm trong dự án…' : 'Search this project…'} className="min-w-0 flex-1 bg-transparent text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-muted)]" />{searchQuery && <button type="button" onClick={() => setSearchQuery('')} aria-label={vi ? 'Xoá tìm kiếm' : 'Clear search'}><X className="h-4 w-4 text-[var(--color-text-muted)]" /></button>}</label>
              <div className="flex items-center gap-1 text-sm text-[var(--color-text-secondary)]">{(['all', 'chats', 'notes'] as const).map((item) => <button key={item} type="button" onClick={() => setFilter(item)} className={`rounded-xl px-3 py-2 transition ${filter === item ? 'bg-[var(--color-surface-hover)] font-semibold text-[var(--color-text-primary)]' : 'hover:text-[var(--color-text-primary)]'}`}>{item === 'all' ? (vi ? 'Tất cả' : 'All') : item === 'chats' ? (vi ? 'Chat' : 'Chats') : (vi ? 'Ghi chú' : 'Notes')}</button>)}</div>
            </div>

            <section className="mt-7" aria-label={vi ? 'Hội thoại trong dự án' : 'Conversations in this project'}>
              {empty ? (
                <div className="flex min-h-[22rem] flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-[var(--color-border)] px-6 py-14 text-center"><div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--color-surface-muted)] text-[var(--color-text-muted)] shadow-inner"><MessagesSquare className="h-7 w-7" /></div><h2 className="font-heading text-2xl font-semibold text-[var(--color-text-primary)]">{vi ? 'Dự án này đang trống' : 'This project is empty'}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--color-text-secondary)]">{vi ? 'Bắt đầu một chat mới, tạo ghi chú hoặc thêm hội thoại từ menu của một chat bất kỳ.' : 'Start a chat or note, or add one from the menu of any conversation.'}</p></div>
              ) : filteredConversations.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-[var(--color-border)] px-6 py-12 text-center"><Search className="mx-auto h-6 w-6 text-[var(--color-text-muted)]" /><p className="mt-3 text-sm text-[var(--color-text-secondary)]">{vi ? 'Không tìm thấy kết quả.' : 'No matching conversations.'}</p></div>
              ) : (
                <ul className="grid gap-3 md:grid-cols-2">{filteredConversations.map((item) => <li key={item.id} className="group flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-[0_12px_36px_var(--color-shadow)]"><button type="button" onClick={() => navigate(`/briefing/conversation/${item.id}`)} className="min-w-0 flex-1 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"><span className="block truncate text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</span><span className="mt-1 block text-xs text-[var(--color-text-muted)]">{vi ? `${item.messageCount} lượt` : `${item.messageCount} turns`}</span></button><button type="button" onClick={() => void handleRemove(item.id)} aria-label={vi ? 'Gỡ khỏi dự án' : 'Remove from project'} title={vi ? 'Gỡ khỏi dự án' : 'Remove from project'} className="shrink-0 rounded-lg p-2 text-[var(--color-text-muted)] opacity-60 transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] sm:opacity-0 sm:group-hover:opacity-100"><LogOut className="h-4 w-4" /></button></li>)}</ul>
              )}
            </section>
          </>
        ) : (
          <section className="mt-7">
            {filteredMeetings.length === 0 ? <div className="flex min-h-[22rem] flex-col items-center justify-center rounded-[1.75rem] border border-dashed border-[var(--color-border)] px-6 py-14 text-center"><FileText className="mb-6 h-7 w-7 text-[var(--color-text-muted)]" /><h2 className="font-heading text-2xl font-semibold text-[var(--color-text-primary)]">{meetings.length ? (vi ? 'Không tìm thấy ghi chú' : 'No matching notes') : (vi ? 'Chưa có ghi chú' : 'No notes yet')}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--color-text-secondary)]">{vi ? 'Ghi chú từ các cuộc họp và phiên làm việc sẽ xuất hiện ở đây.' : 'Notes from meetings and work sessions will appear here.'}</p></div> : <ul className="grid gap-3 md:grid-cols-2">{filteredMeetings.map((item) => <li key={item.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"><button type="button" onClick={() => navigate(`/meeting-notes/${item.id}`)} className="w-full text-left"><span className="block truncate text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</span><span className="mt-1 block text-xs text-[var(--color-text-muted)]">{item.status === 'summarized' ? (vi ? 'Đã tóm tắt' : 'Summarized') : (vi ? 'Đang mở' : 'Open')}</span></button></li>)}</ul>}
          </section>
        )}

        {summary && <aside className="mt-7 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-5"><div className="flex items-center justify-between gap-3"><h2 className="flex items-center gap-2 font-heading text-base font-semibold text-[var(--color-text-primary)]"><Sparkles className="h-4 w-4 text-[var(--color-accent)]" />{vi ? 'Tóm tắt dự án' : 'Project summary'}</h2><button type="button" onClick={() => void load(true)} disabled={refreshing} aria-label={vi ? 'Tóm tắt lại' : 'Regenerate summary'} title={vi ? 'Tóm tắt lại' : 'Regenerate summary'} className="rounded-lg p-1.5 text-[var(--color-text-muted)] transition hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"><RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} /></button></div><p className="mt-3 max-w-3xl whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">{summary}</p>{summaryUpdatedAt && <p className="mt-3 text-[11px] text-[var(--color-text-muted)]">{vi ? 'Cập nhật ' : 'Updated '}{new Date(summaryUpdatedAt).toLocaleString()}</p>}</aside>}
        <div className="mt-6 flex items-center gap-2 text-xs text-[var(--color-text-muted)]"><ArrowLeft className="h-3.5 w-3.5" /><button type="button" onClick={() => navigate('/projects')} className="hover:text-[var(--color-text-primary)]">{vi ? 'Tất cả dự án' : 'All projects'}</button></div>
      </div>
    </div>
  );
};
