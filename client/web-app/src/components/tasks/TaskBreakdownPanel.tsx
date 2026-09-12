import React, { useState } from 'react';
import { Check, Copy, ListChecks, X } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { useTranslation } from '../../i18n/useTranslation';
import type { TaskBreakdown, TaskBreakdownItem as BreakdownItem } from '../../lib/tasksApi';

type SegmentProps = { item: BreakdownItem; rank: number };

const TaskSegment: React.FC<SegmentProps> = ({ item, rank }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(item.aiPrompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <article
      className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
      data-testid={`breakdown-segment-${item.taskId}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)] text-[11px] font-bold text-white">
          {rank}
        </span>
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</h3>
        <Badge variant={item.shouldBreak ? 'warning' : 'neutral'}>
          {item.shouldBreak ? t.tasksPage.breakdownShouldSplit : t.tasksPage.breakdownNoSplit}
        </Badge>
      </div>

      {item.reason && (
        <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">{item.reason}</p>
      )}

      {item.steps.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            {t.tasksPage.breakdownSteps}
          </p>
          <ol className="mt-1 space-y-1.5">
            {item.steps.map((step, index) => (
              <li key={index} className="flex gap-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                <span className="font-semibold tabular-nums text-[var(--color-primary)]">{index + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {item.contextNeeded.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            {t.tasksPage.breakdownContext}
          </p>
          <ul className="mt-1 space-y-1">
            {item.contextNeeded.map((entry, index) => (
              <li key={index} className="flex gap-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                <Check className="mt-0.5 h-3 w-3 shrink-0 text-[var(--color-success)]" />
                <span>{entry}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {item.aiPrompt && (
        <div className="mt-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
              {t.tasksPage.breakdownPromptLabel}
            </p>
            <button
              type="button"
              onClick={copyPrompt}
              aria-label={t.tasksPage.breakdownCopyA11y}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--color-border)] px-2 py-1 text-[10px] font-semibold text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
            >
              {copied ? <Check className="h-3 w-3 text-[var(--color-success)]" /> : <Copy className="h-3 w-3" />}
              {copied ? t.tasksPage.breakdownCopied : t.tasksPage.breakdownCopy}
            </button>
          </div>
          <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl bg-[var(--color-surface-muted)] px-3 py-2.5 font-sans text-xs leading-relaxed text-[var(--color-text-secondary)]">
            {item.aiPrompt}
          </pre>
        </div>
      )}
    </article>
  );
};

type PanelProps = {
  breakdown: TaskBreakdown;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onRetry: () => void;
};

export const TaskBreakdownPanel: React.FC<PanelProps> = ({ breakdown, loading, error, onClose, onRetry }) => {
  const { t } = useTranslation();

  return (
    <section
      aria-label={t.tasksPage.breakdownTitle}
      className="mt-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-[var(--shadow-sm)]"
      data-tour-id="tasks-breakdown-panel"
    >
      <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] pb-2">
        <h3 className="flex min-w-0 items-center gap-1.5 truncate font-heading text-sm font-semibold tracking-[-0.02em] text-[var(--color-text-primary)]">
          <ListChecks className="h-4 w-4 shrink-0 text-[var(--color-primary)]" /> {t.tasksPage.breakdownTitle}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label={t.tasksPage.breakdownCloseA11y}
          className="rounded-lg p-1 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {loading && (
        <div className="space-y-2 pt-4" aria-label={t.tasksPage.loading}>
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-24 animate-pulse rounded-xl bg-[var(--color-surface-muted)]" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="pt-4">
          <p className="rounded-lg bg-[var(--color-danger-soft)] p-3 text-sm text-[var(--color-danger)]">{error}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            {t.tasksPage.refresh}
          </Button>
        </div>
      )}

      {!loading && !error && (
        <>
          {breakdown.summary && (
            <p className="pt-3 text-xs leading-relaxed text-[var(--color-text-secondary)]">{breakdown.summary}</p>
          )}
          {breakdown.items.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--color-text-muted)]">{t.tasksPage.breakdownEmpty}</p>
          ) : (
            <div className="mt-3 space-y-3">
              {breakdown.items.map((item, index) => (
                <TaskSegment key={item.taskId} item={item} rank={index + 1} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
};
