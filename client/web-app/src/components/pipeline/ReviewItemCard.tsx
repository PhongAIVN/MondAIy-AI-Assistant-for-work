import React, { useState } from 'react';
import {
  AlertTriangle,
  CalendarPlus,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  X,
} from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { calendarHandoffBlockReason } from '../../lib/calendarHandoffClient';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';
import { resolveBrandIcon } from '../ui/BrandIcons';
import {
  PROVIDER_LABEL,
  SOURCE_LEVEL,
  type CalendarHandoffResponse,
  type ConnectionProvider,
  type Task,
} from '../../types/pipeline';

const providerLabel = (provider: string): string =>
  provider in PROVIDER_LABEL ? PROVIDER_LABEL[provider as ConnectionProvider] : provider;

const providerLevel = (provider: string) => SOURCE_LEVEL[provider as ConnectionProvider];

const ProviderMark: React.FC<{ provider: string }> = ({ provider }) =>
  resolveBrandIcon(provider, 'w-3.5 h-3.5');

export interface ReviewItemCardProps {
  task: Task;
  actionPending: boolean;
  handoff?: CalendarHandoffResponse;
  handoffPending: boolean;
  onConfirm: () => void;
  onDismiss: () => void;
  onOpenCalendar: () => void;
  onCalendarHandoffOpened: () => void;
}

export const ReviewItemCard: React.FC<ReviewItemCardProps> = ({
  task,
  actionPending,
  handoff,
  handoffPending,
  onConfirm,
  onDismiss,
  onOpenCalendar,
  onCalendarHandoffOpened,
}) => {
  const { t, language } = useTranslation();
  const [showEvidence, setShowEvidence] = useState(false);

  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';

  const formatDateTime = (iso: string | null): string | null => {
    if (!iso) return null;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString(locale, {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      ...(task.allDay ? {} : { hour: '2-digit', minute: '2-digit' }),
    });
  };

  const dueText = formatDateTime(task.dueAt);
  const handoffBlockReason = calendarHandoffBlockReason(task.status, task.dueAt, handoffPending);
  const accentBorder = task.status === 'confirmed' ? 'success' : task.status === 'dismissed' ? 'none' : 'info';
  const evidenceId = `task-evidence-${task.id}`;

  return (
    <Card accentBorder={accentBorder} className={`space-y-3 ${task.status === 'dismissed' ? 'opacity-60' : ''}`}>
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <Badge variant={task.sourceCount > 1 ? 'success' : 'neutral'}>
            {`${task.sourceCount} ${
              task.sourceCount === 1 ? t.pipeline.sourceCountOne : t.pipeline.sourceCountMany
            }`}
          </Badge>
          {task.status === 'confirmed' && <Badge variant="success">{t.pipeline.statusConfirmed}</Badge>}
          {task.status === 'dismissed' && <Badge variant="danger">{t.pipeline.statusDismissed}</Badge>}
          {task.status === 'proposed' && <Badge variant="neutral">{t.pipeline.statusProposed}</Badge>}
        </div>

        <h3 className="text-sm font-bold text-[var(--color-text-primary)] font-heading">{task.title}</h3>

        {task.detail && <p className="text-xs text-[var(--color-text-secondary)]">{task.detail}</p>}

        <div className="flex items-center gap-3 flex-wrap text-[11px]">
          <span
            className={`inline-flex items-center gap-1 font-semibold ${
              dueText ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-warning)]'
            }`}
          >
            <CalendarPlus className="w-3.5 h-3.5" aria-hidden="true" />
            {dueText ?? t.pipeline.deadlineMissing}
          </span>

          <span className="text-[#5E6B7D] dark:text-[#AEB9CC]">
            {t.pipeline.signalStrength}: {Math.round(task.signalStrength * 100)}%
          </span>
        </div>

        {/* Node resolve tự đánh dấu khi không chắc mốc thời gian — đây là chỗ
            dễ sinh deadline sai nhất, phải cảnh báo trước khi user xác nhận. */}
        {task.ambiguous && (
          <p className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[var(--color-warning)] bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-lg px-2 py-1">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
            {t.pipeline.ambiguousWarn}
          </p>
        )}
      </div>

      {/* Bằng chứng: trích dẫn nguyên văn từng nguồn, không phải văn LLM viết lại */}
      <div>
        <button
          type="button"
          aria-expanded={showEvidence}
          aria-controls={evidenceId}
          onClick={() => setShowEvidence((prev) => !prev)}
          className="inline-flex items-center gap-1 text-[11px] font-bold text-[var(--color-primary)] dark:text-[#90CDF4] hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] rounded"
        >
          {showEvidence ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          {t.pipeline.evidence} ({task.evidence.length})
        </button>

        {showEvidence && (
          <ul id={evidenceId} className="mt-2 space-y-2 list-none p-0 m-0">
            {task.evidence.map((item) => (
              <li
                key={item.id}
                className="p-2.5 rounded-lg bg-[var(--color-accent-soft)] border border-[var(--color-border)] text-[11px] space-y-1"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="flex items-center gap-1.5 font-semibold text-[var(--color-text-primary)]">
                    <ProviderMark provider={item.provider} />
                    {providerLabel(item.provider)}
                    {/* Mức đáng tin theo Program Frame mục 5 — người dùng phải
                        nhìn ra bằng chứng này đến từ nguồn chính thức hay không. */}
                    {providerLevel(item.provider) === 'A' && (
                      <Badge variant="success">{t.pipeline.levelA}</Badge>
                    )}
                    {providerLevel(item.provider) === 'B' && (
                      <Badge variant="neutral">{t.pipeline.levelB}</Badge>
                    )}
                  </span>

                  {item.deepLink && (
                    <a
                      href={item.deepLink}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1 font-semibold text-[var(--color-primary)] dark:text-[#90CDF4] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] rounded"
                    >
                      <ExternalLink className="w-3 h-3" aria-hidden="true" />
                      {t.pipeline.evidence}
                    </a>
                  )}
                </div>

                <blockquote className="text-[#5E6B7D] dark:text-[#AEB9CC] italic border-l-2 border-[#C8D2DE] pl-2">
                  “{item.evidenceQuote}”
                </blockquote>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Duyệt việc: mọi thứ dừng ở đây cho tới khi user tự bấm. Backend chỉ
          cho chuyển trạng thái từ 'proposed', không có đường quay lại. */}
      <div className="pt-2 border-t border-[var(--color-border)] flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          {task.status === 'proposed' && (
            <>
              <Button
                variant="primary"
                size="xs"
                icon={<Check className="w-3.5 h-3.5" />}
                disabled={actionPending}
                onClick={onConfirm}
              >
                {t.pipeline.accept}
              </Button>
              <Button
                variant="ghost"
                size="xs"
                icon={<X className="w-3.5 h-3.5" />}
                disabled={actionPending}
                onClick={onDismiss}
              >
                {t.pipeline.reject}
              </Button>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          {handoff?.icsUrl && (
            <a
              href={handoff.icsUrl}
              download={handoff.filename}
              rel="noreferrer noopener"
              onClick={onCalendarHandoffOpened}
              className="text-[11px] font-semibold text-[var(--color-primary)] dark:text-[#90CDF4] hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] rounded"
            >
              {t.pipeline.openIcs}
            </a>
          )}

          <Button
            variant="secondary"
            size="xs"
            icon={<CalendarPlus className="w-3.5 h-3.5" />}
            disabled={handoffBlockReason !== null}
            title={
              handoffBlockReason === 'task_not_confirmed'
                ? t.pipeline.confirmTaskFirst
                : handoffBlockReason === 'missing_due_at'
                  ? t.pipeline.needDeadline
                  : undefined
            }
            onClick={onOpenCalendar}
          >
            {handoffPending ? t.pipeline.opening : t.pipeline.confirmCalendar}
          </Button>
        </div>
      </div>

      <p className="text-[10px] text-[#5E6B7D] dark:text-[#AEB9CC] flex items-center gap-1">
        <ShieldCheck className="w-3 h-3 text-[#2F7D5B] dark:text-[#6EE7B7]" aria-hidden="true" />
        {t.pipeline.noAutoWrite}
      </p>
    </Card>
  );
};
