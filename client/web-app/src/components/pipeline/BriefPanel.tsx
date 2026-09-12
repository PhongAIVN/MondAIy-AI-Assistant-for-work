import React from 'react';
import { AlertTriangle, FileText, Flag } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Card } from '../ui/Card';
import type { Brief } from '../../types/pipeline';

export interface BriefPanelProps {
  brief: Brief | null;
  onFocusTask?: (taskId: number) => void;
}

export const BriefPanel: React.FC<BriefPanelProps> = ({ brief, onFocusTask }) => {
  const { t, language } = useTranslation();
  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';

  const formatDate = (iso: string | null): string | null => {
    if (!iso) return null;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString(locale, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Card accentBorder="info" className="space-y-4">
      <h2 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading flex items-center gap-2">
        <FileText className="w-4 h-4 text-[var(--color-primary)]" aria-hidden="true" />
        {t.pipeline.briefTitle}
      </h2>

      {!brief ? (
        <p className="text-xs text-[var(--color-text-secondary)]">{t.pipeline.briefWaiting}</p>
      ) : (
        <div className="space-y-4">
          <p className="text-xs leading-relaxed text-[#172033] dark:text-[#F4F7FC]">{brief.summary}</p>

          {brief.topPriority.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-secondary)] flex items-center gap-1.5">
                <Flag className="w-3.5 h-3.5 text-[var(--color-primary)]" aria-hidden="true" />
                {t.pipeline.topPriority}
              </h3>

              <ol className="space-y-2 list-none p-0 m-0">
                {brief.topPriority.map((priority, index) => (
                  <li
                    key={priority.taskId}
                    className="p-2.5 rounded-lg bg-[var(--color-accent-soft)] border border-[var(--color-border)]"
                  >
                    <button
                      type="button"
                      onClick={() => onFocusTask?.(priority.taskId)}
                      className="text-left w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] rounded"
                    >
                      <span className="text-xs font-bold text-[var(--color-text-primary)]">
                        {index + 1}. {priority.title}
                      </span>
                      {formatDate(priority.dueAt) && (
                        <span className="block text-[11px] font-semibold text-[var(--color-primary)] dark:text-[#90CDF4] mt-0.5">
                          {formatDate(priority.dueAt)}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="space-y-2">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-[var(--color-text-secondary)] flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-[var(--color-warning)]" aria-hidden="true" />
              {t.pipeline.conflicts}
            </h3>

            {/* schedule_conflicts luôn rỗng ở P0 (xem src/api/runs.py) — nói
                thẳng là chưa bật, đừng để trống như thể đã kiểm tra xong. */}
            <p className="text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC]">
              {brief.scheduleConflicts.length === 0
                ? t.pipeline.conflictsUnavailable
                : `${brief.scheduleConflicts.length}`}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
};
