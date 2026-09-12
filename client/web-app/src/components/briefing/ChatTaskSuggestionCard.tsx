import React, { useState } from 'react';
import { Check, Plus } from 'lucide-react';

import type { TaskSuggestionAction } from '../../lib/agentStream';
import { createTaskFromSuggestion } from '../../lib/tasksApi';
import { Button } from '../ui/Button';

type Props = {
  suggestion: TaskSuggestionAction;
  accessToken: string | null;
  language: string;
  onOpenTasks: () => void;
};

export const ChatTaskSuggestionCard: React.FC<Props> = ({
  suggestion,
  accessToken,
  language,
  onOpenTasks,
}) => {
  const [created, setCreated] = useState(false);
  const [merged, setMerged] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const vi = language === 'vi';
  const dueLabel = suggestion.dueAt
    ? new Date(suggestion.dueAt).toLocaleString(vi ? 'vi-VN' : 'en-GB')
    : (vi ? 'Chưa có hạn chót rõ ràng' : 'No confirmed due date');

  const handleCreate = async () => {
    if (!accessToken) return;
    setPending(true);
    setError(null);
    try {
      const task = await createTaskFromSuggestion(suggestion, accessToken);
      setMerged(Boolean(task.deduplicated));
      setCreated(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : (vi ? 'Không thể thêm task.' : 'Could not add task.'));
    } finally {
      setPending(false);
    }
  };

  return (
    <section
      aria-label={vi ? `Gợi ý task ${suggestion.title}` : `Task suggestion ${suggestion.title}`}
      className="max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 shadow-2xs"
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
        {vi ? 'Việc được nhận ra từ nguồn' : 'Task found in a source'}
      </p>
      <h3 className="mt-1 font-semibold text-[var(--color-text-primary)]">{suggestion.title}</h3>
      {suggestion.detail && <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{suggestion.detail}</p>}
      <p className="mt-2 text-xs text-[var(--color-text-muted)]">
        {[suggestion.source, dueLabel].filter(Boolean).join(' · ')}
      </p>
      {error && <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">{error}</p>}
      <div className="mt-4 flex gap-2">
        {created ? (
          <Button size="sm" variant="outline" onClick={onOpenTasks}>
            <Check className="mr-1.5 h-4 w-4" />
            {merged
              ? (vi ? 'Đã gộp vào task có sẵn · Mở Tasks' : 'Merged with existing task · Open Tasks')
              : (vi ? 'Đã thêm · Mở Tasks' : 'Added · Open Tasks')}
          </Button>
        ) : (
          <Button size="sm" onClick={() => void handleCreate()} disabled={!accessToken || pending}>
            <Plus className="mr-1.5 h-4 w-4" />
            {pending ? (vi ? 'Đang thêm…' : 'Adding…') : (vi ? 'Thêm task' : 'Add task')}
          </Button>
        )}
      </div>
      {created && merged && (
        <p className="mt-2 text-xs text-[var(--color-text-muted)]">
          {vi ? 'Nguồn mới đã được gắn vào task trùng để tránh tạo bản sao.' : 'The new source was attached to the matching task to avoid a duplicate.'}
        </p>
      )}
    </section>
  );
};
