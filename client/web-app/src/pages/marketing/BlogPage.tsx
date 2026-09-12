import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowUpRight } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { LandingTeamMeet } from '../../components/marketing/LandingSections';
import { listManagedBlogPosts, type ManagedBlogPost } from '../../lib/managedBlogCatalog';
import { resolveBlogCoverUrl } from '../../lib/blogCovers';
import { MarkdownText } from '../../components/marketing/MarkdownBody';

export const BlogPage: React.FC = () => {
  const { t } = useTranslation();
  const language = usePreferencesStore((s) => s.language);
  const [tick, setTick] = useState(0);
  const posts = useMemo(() => listManagedBlogPosts(), [tick]);

  useEffect(() => {
    const sync = () => setTick((n) => n + 1);
    window.addEventListener('focus', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('focus', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blogBackHome}
      </Link>

      <header className="mt-8 max-w-2xl space-y-4">
        <h1 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
          {t.marketing.blogTitle}
        </h1>
        <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
          {t.marketing.blogSubtitle}
        </p>
      </header>

      <div className="mt-12 grid gap-4 md:grid-cols-2">
        {posts.map((post: ManagedBlogPost, index) => {
          const fallbackCover = resolveBlogCoverUrl({ ...post, coverImageUrl: null }, index);
          const cover = resolveBlogCoverUrl(post, index);
          const tag = post.tags[0] || 'Blog';
          const title = language === 'vi' ? post.titleVi : post.title;
          const excerpt = language === 'vi' ? post.excerptVi : post.excerpt;
          const hasCover = true;

          return (
            <Link
              key={post.id}
              to={`/blog/${post.slug}`}
              className="group relative flex min-h-[300px] overflow-hidden rounded-[22px] shadow-e1 ring-1 ring-hairline transition-[transform,box-shadow] duration-[var(--d-base)] ease-[var(--ease-out-quint)] hover:-translate-y-0.5 hover:shadow-e2"
            >
              {hasCover ? (
                <img
                  src={cover}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
                  onError={(event) => {
                    if (event.currentTarget.dataset.fallbackApplied) return;
                    event.currentTarget.dataset.fallbackApplied = 'true';
                    event.currentTarget.src = fallbackCover;
                  }}
                />
              ) : (
                <div
                  className="absolute inset-0 bg-gradient-to-br from-[#1b3a44] via-[#2f5d68] to-[#0f1f38]"
                  aria-hidden
                />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-ink-950/85 via-ink-950/45 to-ink-950/15" />
              <div className="relative z-10 flex h-full min-h-[300px] w-full flex-col justify-end gap-3 p-6 sm:p-7">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/75">
                  {tag}
                </p>
                <h2 className="font-heading max-w-[18ch] text-[clamp(1.55rem,2.4vw,2rem)] font-semibold leading-[1.15] tracking-[-0.02em] text-white">
                  {title}
                </h2>
                <p className="max-w-[42ch] text-sm leading-relaxed text-white/85">
                  <MarkdownText text={excerpt} />
                </p>
                <div className="mt-1 flex items-center justify-between gap-3 border-t border-white/15 pt-3">
                  <p className="truncate text-xs font-semibold text-white/80">
                    {post.author} · {post.publishedAt}
                  </p>
                  <span className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-white">
                    {t.marketing.blogReadMore}
                    <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <LandingTeamMeet className="mt-16 border-t border-hairline pt-12" />
    </div>
  );
};
