import React, { useMemo } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { getManagedBlogPostBySlug } from '../../lib/managedBlogCatalog';
import { MarkdownBody } from '../../components/marketing/MarkdownBody';

export const BlogPostPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { t } = useTranslation();
  const language = usePreferencesStore((s) => s.language);
  const post = useMemo(
    () => (slug ? getManagedBlogPostBySlug(slug) : null),
    [slug],
  );

  if (!post) {
    return <Navigate to="/blog" replace />;
  }

  const title = language === 'vi' ? post.titleVi : post.title;
  const body = language === 'vi' ? post.bodyVi : post.body;

  return (
    <article className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/blog"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blog}
      </Link>

      <header className="mt-8 space-y-4">
        <p className="text-xs tabular-nums text-ink-400">
          {post.publishedAt} · {post.author}
          {post.tags[0] ? ` · ${post.tags[0]}` : ''}
        </p>
        <h1 className="text-balance text-[clamp(2rem,4vw,2.85rem)] font-semibold leading-[1.15] tracking-[-0.025em] text-ink-900">
          {title}
        </h1>
      </header>

      <MarkdownBody source={body} className="mt-10 space-y-5 text-base leading-relaxed text-ink-700" />
    </article>
  );
};
