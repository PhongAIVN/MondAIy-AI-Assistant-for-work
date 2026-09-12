import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckCircle2,
  FileUp,
  Image,
  ImagePlus,
  Loader2,
  Newspaper,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
} from 'lucide-react';
import { AdminMockBanner } from '../../components/admin/AdminStates';
import { Button } from '../../components/ui/Button';
import {
  getBlogStorageStatus,
  blogAssetPublicUrl,
  publishBlogPost,
  uploadBlogAsset,
  type BlogStorageStatus,
} from '../../lib/adminBlogApi';
import {
  buildMarkdownImage,
  insertMarkdownSnippet,
  parseMarkdownDraft,
  slugify,
} from '../../lib/blogCompose';
import { MarkdownBody } from '../../components/marketing/MarkdownBody';
import { coverUrlFromObjectKey } from '../../lib/blogCovers';
import {
  createBlogPostId,
  deleteManagedBlogPost,
  getManagedBlogPostById,
  listManagedBlogPosts,
  type ManagedBlogPost,
  upsertManagedBlogPost,
} from '../../lib/managedBlogCatalog';
import { useAuthStore } from '../../stores/useAuthStore';
import { useAppStore } from '../../stores/useAppStore';
import { useTranslation } from '../../i18n/useTranslation';
import type { BlogPost } from '../../data/blogPosts';

type DraftForm = {
  title: string;
  titleVi: string;
  slug: string;
  author: string;
  excerpt: string;
  excerptVi: string;
  tags: string;
  body: string;
  bodyVi: string;
  markdownSourceName: string | null;
};

type AssetRow = {
  objectKey: string;
  filename: string;
  storageMode: string;
  previewUrl?: string;
};

type TabKey = 'manage' | 'compose';

const EMPTY_DRAFT: DraftForm = {
  title: '',
  titleVi: '',
  slug: '',
  author: '',
  excerpt: '',
  excerptVi: '',
  tags: '',
  body: '',
  bodyVi: '',
  markdownSourceName: null,
};

function fill(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce(
    (out, [key, value]) => out.replaceAll(`{${key}}`, String(value)),
    template,
  );
}

function postToDraft(post: BlogPost): DraftForm {
  return {
    title: post.title,
    titleVi: post.titleVi,
    slug: post.slug,
    author: post.author,
    excerpt: post.excerpt,
    excerptVi: post.excerptVi,
    tags: post.tags.join(', '),
    body: post.body,
    bodyVi: post.bodyVi,
    markdownSourceName: null,
  };
}

function MarkdownPreview({ source, emptyLabel }: { source: string; emptyLabel: string }) {
  if (!source.trim()) {
    return <p className="text-xs text-[#5A6A85]">{emptyLabel}</p>;
  }
  return (
    <MarkdownBody
      source={source}
      className="space-y-3 text-sm leading-relaxed text-[#0F1F38] dark:text-slate-200"
    />
  );
}

export const AdminBlogPage: React.FC = () => {
  const { t, language } = useTranslation();
  const bp = t.admin.blogPage;
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const addToast = useAppStore((s) => s.addToast);

  const mdInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const bodyImageInputRef = useRef<HTMLInputElement>(null);
  const bodyEnRef = useRef<HTMLTextAreaElement>(null);
  const bodyViRef = useRef<HTMLTextAreaElement>(null);
  const [bodyTarget, setBodyTarget] = useState<'en' | 'vi'>('en');

  const [tab, setTab] = useState<TabKey>('manage');
  const [catalogTick, setCatalogTick] = useState(0);
  const managedPosts = listManagedBlogPosts();
  void catalogTick;

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftForm>(() => ({
    ...EMPTY_DRAFT,
    author: user?.name || '',
  }));
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [coverKey, setCoverKey] = useState<string | null>(null);
  const [coverPreviewUrl, setCoverPreviewUrl] = useState<string | null>(null);
  const [previewLang, setPreviewLang] = useState<'en' | 'vi'>('en');
  const [storage, setStorage] = useState<BlogStorageStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastPublished, setLastPublished] = useState<{
    title: string;
    slug: string;
    publicPath: string;
  } | null>(null);

  const refreshCatalog = () => setCatalogTick((n) => n + 1);

  const displayTitle = (post: Pick<BlogPost, 'title' | 'titleVi'>) =>
    language === 'vi' ? post.titleVi || post.title : post.title;

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void getBlogStorageStatus(accessToken)
      .then((status) => {
        if (!cancelled) setStorage(status);
      })
      .catch(() => {
        if (!cancelled) {
          setStorage({
            available: false,
            mode: 'local',
            endpoint: 'n/a',
            bucket: 'browser-catalog',
            detail: bp.storageFallbackDetail,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, bp.storageFallbackDetail]);

  const updateField = <K extends keyof DraftForm>(key: K, value: DraftForm[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const resetComposer = (keepAuthor = true) => {
    setEditingId(null);
    setDraft({ ...EMPTY_DRAFT, author: keepAuthor ? user?.name || '' : '' });
    setAssets([]);
    setCoverKey(null);
    setCoverPreviewUrl(null);
    setLastPublished(null);
    setMessage(null);
    setError(null);
  };

  const startCreate = () => {
    resetComposer(true);
    setTab('compose');
  };

  const startEdit = (post: ManagedBlogPost) => {
    setEditingId(post.id);
    setDraft(postToDraft(post));
    setAssets([]);
    setCoverKey(null);
    setCoverPreviewUrl(post.coverImageUrl || null);
    setLastPublished(null);
    setMessage(fill(bp.editingMessage, { title: displayTitle(post) }));
    setError(null);
    setTab('compose');
  };

  const handleDelete = (post: ManagedBlogPost) => {
    const title = displayTitle(post);
    const ok = window.confirm(
      post.origin === 'seed'
        ? fill(bp.confirmDeleteSeed, { title })
        : fill(bp.confirmDeleteCustom, { title }),
    );
    if (!ok) return;
    deleteManagedBlogPost(post.id);
    if (editingId === post.id) resetComposer(true);
    refreshCatalog();
    addToast({ type: 'success', title: bp.toastDeleted, message: title });
  };

  const handleMarkdownFile = async (file: File) => {
    setError(null);
    setBusy('md');
    try {
      const text = await file.text();
      const parsed = parseMarkdownDraft(text);
      setDraft({
        title: parsed.title,
        titleVi: parsed.titleVi,
        slug: parsed.slug,
        author: parsed.author || user?.name || '',
        excerpt: parsed.excerpt,
        excerptVi: parsed.excerptVi,
        tags: parsed.tags.join(', '),
        body: parsed.body,
        bodyVi: parsed.bodyVi,
        markdownSourceName: file.name,
      });
      setMessage(fill(bp.loadedMd, { name: file.name }));
    } catch (err) {
      setError(err instanceof Error ? err.message : bp.mdReadError);
    } finally {
      setBusy(null);
    }
  };

  const handleImageUpload = async (file: File) => {
    setError(null);
    setBusy('image');
    try {
      let previewUrl = URL.createObjectURL(file);
      let objectKey = `blog/local/pending-${Date.now()}-${file.name}`;
      let storageMode = 'local';

      if (accessToken) {
        try {
          const uploaded = await uploadBlogAsset(accessToken, file);
          objectKey = uploaded.objectKey;
          storageMode = uploaded.storageMode;
          previewUrl =
            uploaded.publicUrl ||
            (uploaded.objectKey.startsWith('blog/local/')
              ? blogAssetPublicUrl(uploaded.objectKey)
              : previewUrl);
        } catch {
          // Giữ blob preview nếu API upload lỗi
          storageMode = 'browser';
        }
      }

      setAssets((prev) => [
        { objectKey, filename: file.name, storageMode, previewUrl },
        ...prev,
      ]);
      setCoverKey(objectKey);
      setCoverPreviewUrl(previewUrl);
      setMessage(fill(bp.coverAttached, { name: file.name }));
    } catch (err) {
      setError(err instanceof Error ? err.message : bp.imageUploadError);
    } finally {
      setBusy(null);
    }
  };

  /** Upload ảnh rồi chèn cú pháp ![alt](url) vào body EN/VI đang focus. */
  const handleBodyImageUpload = async (file: File) => {
    setError(null);
    setBusy('body-image');
    try {
      let src = URL.createObjectURL(file);
      let objectKey = `blog/local/pending-${Date.now()}-${file.name}`;
      let storageMode = 'browser';

      if (accessToken) {
        try {
          const uploaded = await uploadBlogAsset(accessToken, file);
          objectKey = uploaded.objectKey;
          storageMode = uploaded.storageMode;
          src =
            uploaded.publicUrl ||
            (uploaded.objectKey.startsWith('blog/local/')
              ? blogAssetPublicUrl(uploaded.objectKey)
              : src);
        } catch {
          storageMode = 'browser';
        }
      }

      setAssets((prev) => [
        { objectKey, filename: file.name, storageMode, previewUrl: src },
        ...prev,
      ]);

      const field = bodyTarget === 'vi' ? 'bodyVi' : 'body';
      const textarea = bodyTarget === 'vi' ? bodyViRef.current : bodyEnRef.current;
      const current = bodyTarget === 'vi' ? draft.bodyVi : draft.body;
      const start = textarea?.selectionStart ?? current.length;
      const end = textarea?.selectionEnd ?? current.length;
      const alt = file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ');
      const snippet = buildMarkdownImage(alt, src);
      const { next, cursor } = insertMarkdownSnippet(current, snippet, start, end);

      setDraft((prev) => ({ ...prev, [field]: next }));
      setMessage(
        fill(bp.imageInserted, {
          name: file.name,
          target: bodyTarget === 'vi' ? bp.bodyTargetVi : bp.bodyTargetEn,
        }),
      );

      requestAnimationFrame(() => {
        const el = bodyTarget === 'vi' ? bodyViRef.current : bodyEnRef.current;
        if (!el) return;
        el.focus();
        el.setSelectionRange(cursor, cursor);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : bp.imageUploadError);
    } finally {
      setBusy(null);
    }
  };

  const handleSave = async () => {
    setError(null);
    setMessage(null);
    setLastPublished(null);

    const slug = (draft.slug || slugify(draft.title)).trim();
    if (!draft.title.trim() || !draft.body.trim() || !draft.author.trim() || !slug) {
      setError(bp.validationError);
      return;
    }

    const tags = draft.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);

    const coverImageUrl =
      coverPreviewUrl ||
      assets.find((a) => a.objectKey === coverKey)?.previewUrl ||
      coverUrlFromObjectKey(coverKey);

    const existing = editingId ? getManagedBlogPostById(editingId) : null;
    const post: BlogPost = {
      id: existing?.id || createBlogPostId(),
      slug,
      title: draft.title.trim(),
      titleVi: draft.titleVi.trim() || draft.title.trim(),
      excerpt: draft.excerpt.trim(),
      excerptVi: draft.excerptVi.trim() || draft.excerpt.trim(),
      body: draft.body,
      bodyVi: draft.bodyVi || draft.body,
      author: draft.author.trim(),
      tags,
      publishedAt: existing?.publishedAt || new Date().toISOString().slice(0, 10),
      coverImageUrl: coverImageUrl || null,
    };

    setBusy('publish');
    try {
      // Catalog luôn là nguồn chuẩn cho /blog
      upsertManagedBlogPost(post);
      refreshCatalog();

      // Best-effort gửi API (không chặn UX nếu backend cũ)
      if (accessToken) {
        try {
          await publishBlogPost(accessToken, {
            slug: post.slug,
            title: post.title,
            titleVi: post.titleVi,
            excerpt: post.excerpt,
            excerptVi: post.excerptVi,
            body: post.body,
            bodyVi: post.bodyVi,
            author: post.author,
            tags: post.tags,
            coverObjectKey: coverKey,
            assetObjectKeys: assets.map((a) => a.objectKey),
            markdownSourceName: draft.markdownSourceName,
          });
        } catch {
          // bỏ qua — catalog local đã lưu
        }
      }

      setEditingId(post.id);
      setLastPublished({
        title: displayTitle(post),
        slug: post.slug,
        publicPath: `/blog/${post.slug}`,
      });
      setMessage(existing ? bp.updatedMessage : bp.publishedMessage);
      addToast({
        type: 'success',
        title: existing ? bp.toastUpdated : bp.toastPublished,
        message: `“${displayTitle(post)}” → /blog/${post.slug}`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : bp.saveFailedFallback);
      addToast({
        type: 'error',
        title: bp.toastSaveFailed,
        message: err instanceof Error ? err.message : bp.saveFailedFallback,
      });
    } finally {
      setBusy(null);
    }
  };

  const previewSource = previewLang === 'vi' ? draft.bodyVi || draft.body : draft.body;

  return (
    <div className="space-y-6">
      <AdminMockBanner lyDo={bp.mockBannerReason} />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#0F1F38] dark:text-white sm:text-2xl">
            {t.admin.blog}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{bp.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => refreshCatalog()} disabled={!!busy}>
            <RefreshCw className="h-3.5 w-3.5" /> {bp.refreshList}
          </Button>
          <Button size="sm" onClick={startCreate} icon={<Plus className="h-3.5 w-3.5" />}>
            {bp.newPost}
          </Button>
        </div>
      </div>

      <div className="flex gap-1 rounded-xl bg-[#EDF2FB] p-1 dark:bg-[#0A1628]">
        {(
          [
            {
              key: 'manage' as const,
              label: fill(bp.tabManage, { count: managedPosts.length }),
            },
            {
              key: 'compose' as const,
              label: editingId ? bp.tabEdit : bp.tabCompose,
            },
          ]
        ).map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setTab(item.key)}
            className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
              tab === item.key
                ? 'bg-white text-[#0F1F38] shadow-sm dark:bg-[#122038] dark:text-white'
                : 'text-[#5A6A85] hover:text-[#0F1F38] dark:hover:text-white'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === 'manage' && (
        <section className="overflow-hidden rounded-2xl border border-[#D5DDEB] bg-white shadow-xs dark:border-[#1A2A42] dark:bg-[#122038]">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#D5DDEB] bg-[#EDF2FB] text-[10px] font-medium text-[#5A6A85] dark:border-[#1A2A42] dark:bg-[#0A1628] dark:text-[#8B98AB]">
                <tr>
                  <th className="p-4">{bp.colPost}</th>
                  <th className="p-4">{bp.colSlug}</th>
                  <th className="p-4">{bp.colOrigin}</th>
                  <th className="p-4">{bp.colDate}</th>
                  <th className="p-4 text-right">{bp.colActions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42]">
                {managedPosts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-[#5A6A85]">
                      {bp.emptyList}
                    </td>
                  </tr>
                ) : (
                  managedPosts.map((post) => (
                    <tr key={post.id} className="hover:bg-[#EDF2FB]/50 dark:hover:bg-[#0A1628]/40">
                      <td className="p-4">
                        <p className="font-bold text-[#0F1F38] dark:text-white">
                          {displayTitle(post)}
                        </p>
                        <p className="mt-0.5 text-[11px] text-[#5A6A85]">{post.author}</p>
                      </td>
                      <td className="p-4 text-[11px] text-[#2563A6]">{post.slug}</td>
                      <td className="p-4">
                        <span
                          className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                            post.origin === 'seed'
                              ? 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
                              : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                          }`}
                        >
                          {post.origin === 'seed' ? bp.originSeed : bp.originCustom}
                        </span>
                      </td>
                      <td className="p-4 text-[#5A6A85]">{post.publishedAt}</td>
                      <td className="p-4">
                        <div className="flex flex-wrap justify-end gap-1.5">
                          <Link to={`/blog/${post.slug}`}>
                            <Button size="xs" variant="outline">
                              {bp.view}
                            </Button>
                          </Link>
                          <Button size="xs" variant="secondary" onClick={() => startEdit(post)}>
                            <Pencil className="h-3 w-3" /> {bp.edit}
                          </Button>
                          <Button size="xs" variant="danger" onClick={() => handleDelete(post)}>
                            <Trash2 className="h-3 w-3" /> {bp.delete}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === 'compose' && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-[#D5DDEB] bg-white p-4 dark:border-[#1A2A42] dark:bg-[#122038]">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[#5A6A85]">
                {bp.step1Label}
              </p>
              <p className="mt-1 text-sm font-bold text-[#0F1F38] dark:text-white">{bp.step1Title}</p>
            </div>
            <div className="rounded-2xl border border-[#D5DDEB] bg-white p-4 dark:border-[#1A2A42] dark:bg-[#122038]">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[#5A6A85]">
                {bp.step2Label}
              </p>
              <p className="mt-1 text-sm font-bold text-[#0F1F38] dark:text-white">{bp.step2Title}</p>
            </div>
            <div className="rounded-2xl border border-[#D5DDEB] bg-white p-4 dark:border-[#1A2A42] dark:bg-[#122038]">
              <p className="text-[10px] font-semibold uppercase tracking-wide text-[#5A6A85]">
                {bp.step3Label}
              </p>
              <p className="mt-1 text-sm font-bold text-[#0F1F38] dark:text-white">
                {fill(bp.step3Title, { mode: storage ? storage.mode : '…' })}
              </p>
            </div>
          </div>

          {(message || error || lastPublished) && (
            <div className="space-y-2">
              {error && (
                <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                  {error}
                </p>
              )}
              {lastPublished && (
                <div className="rounded-2xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950/40">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                    <div className="min-w-0 space-y-2">
                      <p className="text-sm font-bold text-emerald-950 dark:text-emerald-100">
                        {fill(bp.savedTitle, { title: lastPublished.title })}
                      </p>
                      <p className="text-xs text-emerald-900/80 dark:text-emerald-200/90">
                        {message}
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        <Link
                          to="/blog"
                          className="inline-flex items-center rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800"
                        >
                          {bp.openBlog}
                        </Link>
                        <Link
                          to={lastPublished.publicPath}
                          className="inline-flex items-center rounded-lg border border-emerald-700 px-3 py-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-100"
                        >
                          {bp.viewPost}
                        </Link>
                        <Button size="xs" variant="outline" onClick={() => setTab('manage')}>
                          {bp.backToList}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {!lastPublished && message && (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
                  {message}
                </p>
              )}
            </div>
          )}

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <section className="space-y-4 rounded-2xl border border-[#D5DDEB] bg-white p-4 shadow-xs dark:border-[#1A2A42] dark:bg-[#122038] sm:p-5">
              <div className="flex flex-wrap gap-2">
                <input
                  ref={mdInputRef}
                  type="file"
                  accept=".md,text/markdown,text/plain"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleMarkdownFile(file);
                    e.target.value = '';
                  }}
                />
                <Button size="sm" variant="secondary" onClick={() => mdInputRef.current?.click()} disabled={!!busy}>
                  {busy === 'md' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileUp className="h-3.5 w-3.5" />}
                  {bp.pickMarkdown}
                </Button>
                <input
                  ref={imageInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleImageUpload(file);
                    e.target.value = '';
                  }}
                />
                <Button size="sm" variant="outline" onClick={() => imageInputRef.current?.click()} disabled={!!busy}>
                  {busy === 'image' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" />}
                  {bp.pickCover}
                </Button>
                <input
                  ref={bodyImageInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void handleBodyImageUpload(file);
                    e.target.value = '';
                  }}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => bodyImageInputRef.current?.click()}
                  disabled={!!busy}
                  title={bp.insertTargetHint}
                >
                  {busy === 'body-image' ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Image className="h-3.5 w-3.5" />
                  )}
                  {bp.insertBodyImage}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => resetComposer(true)}>
                  <Trash2 className="h-3.5 w-3.5" /> {bp.resetForm}
                </Button>
                <Button
                  size="sm"
                  onClick={() => void handleSave()}
                  disabled={!!busy}
                  icon={busy === 'publish' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                >
                  {editingId ? bp.saveChanges : bp.publish}
                </Button>
              </div>

              {coverPreviewUrl && (
                <div className="overflow-hidden rounded-xl border border-[#E1EBFA] dark:border-[#1A2A42]">
                  <img src={coverPreviewUrl} alt="Cover preview" className="h-36 w-full object-cover" />
                  <button
                    type="button"
                    className="w-full px-3 py-1.5 text-left text-[11px] font-semibold text-[#2563A6]"
                    onClick={() => {
                      setCoverPreviewUrl(null);
                      setCoverKey(null);
                    }}
                  >
                    {bp.removeCover}
                  </button>
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.titleEn}</span>
                  <input
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.title}
                    onChange={(e) => {
                      const nextTitle = e.target.value;
                      setDraft((prev) => ({
                        ...prev,
                        title: nextTitle,
                        slug:
                          !prev.slug || prev.slug === slugify(prev.title)
                            ? slugify(nextTitle)
                            : prev.slug,
                      }));
                    }}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.titleVi}</span>
                  <input
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.titleVi}
                    onChange={(e) => updateField('titleVi', e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.slug}</span>
                  <input
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.slug}
                    onChange={(e) => updateField('slug', slugify(e.target.value))}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.author}</span>
                  <input
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.author}
                    onChange={(e) => updateField('author', e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold sm:col-span-2">
                  <span>{bp.tags}</span>
                  <input
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.tags}
                    onChange={(e) => updateField('tags', e.target.value)}
                    placeholder="product, design"
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.excerptEn}</span>
                  <textarea
                    rows={2}
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.excerpt}
                    onChange={(e) => updateField('excerpt', e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold">
                  <span>{bp.excerptVi}</span>
                  <textarea
                    rows={2}
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 text-sm dark:border-[#1A2A42]"
                    value={draft.excerptVi}
                    onChange={(e) => updateField('excerptVi', e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold sm:col-span-2">
                  <span>
                    {bp.bodyEn}
                    {bodyTarget === 'en' ? (
                      <span className="ml-2 text-[10px] font-medium text-[#2563A6]">●</span>
                    ) : null}
                  </span>
                  <textarea
                    ref={bodyEnRef}
                    rows={10}
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 font-mono text-xs dark:border-[#1A2A42]"
                    value={draft.body}
                    onFocus={() => setBodyTarget('en')}
                    onChange={(e) => updateField('body', e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-xs font-semibold sm:col-span-2">
                  <span>
                    {bp.bodyVi}
                    {bodyTarget === 'vi' ? (
                      <span className="ml-2 text-[10px] font-medium text-[#2563A6]">●</span>
                    ) : null}
                  </span>
                  <textarea
                    ref={bodyViRef}
                    rows={8}
                    className="w-full rounded-xl border border-[#D5DDEB] bg-transparent px-3 py-2 font-mono text-xs dark:border-[#1A2A42]"
                    value={draft.bodyVi}
                    onFocus={() => setBodyTarget('vi')}
                    onChange={(e) => updateField('bodyVi', e.target.value)}
                  />
                </label>
              </div>
            </section>

            <aside className="space-y-4">
              <div className="rounded-2xl border border-[#D5DDEB] bg-white p-4 dark:border-[#1A2A42] dark:bg-[#122038] sm:p-5">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="text-sm font-bold text-[#0F1F38] dark:text-white">{bp.preview}</p>
                  <div className="flex gap-1">
                    {(['en', 'vi'] as const).map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => setPreviewLang(lang)}
                        className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold ${
                          previewLang === lang
                            ? 'bg-[#2563A6] text-white'
                            : 'bg-[#EDF2FB] text-[#5A6A85] dark:bg-[#0A1628]'
                        }`}
                      >
                        {lang.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                <p className="mb-2 text-[10px] text-[#5A6A85]">
                  /blog/{draft.slug || '…'} · {draft.author || 'author'}
                </p>
                <h2 className="mb-4 text-lg font-bold tracking-tight text-[#0F1F38] dark:text-white">
                  {previewLang === 'vi'
                    ? draft.titleVi || draft.title
                    : draft.title || bp.untitled}
                </h2>
                <MarkdownPreview source={previewSource} emptyLabel={bp.previewEmpty} />
              </div>

              <div className="rounded-2xl border border-[#D5DDEB] bg-white p-4 dark:border-[#1A2A42] dark:bg-[#122038] sm:p-5">
                <div className="mb-3 flex items-center gap-2">
                  <Newspaper className="h-4 w-4 text-[#2563A6]" />
                  <p className="text-sm font-bold text-[#0F1F38] dark:text-white">
                    {fill(bp.managingCount, { count: managedPosts.length })}
                  </p>
                </div>
                <Button size="sm" variant="outline" className="w-full" onClick={() => setTab('manage')}>
                  {bp.openManageList}
                </Button>
              </div>
            </aside>
          </div>
        </>
      )}
    </div>
  );
};
