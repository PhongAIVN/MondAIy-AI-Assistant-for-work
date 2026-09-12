import React, { useState } from 'react';
import { Check, Pencil, Save, Trash2 } from 'lucide-react';

import type { TaskDraftAction } from '../../lib/agentStream';
import { cancelTask, updateTask, type TaskStatus } from '../../lib/tasksApi';
import { formatTaskDueAt, toLocalDateTimeInputValue } from '../../lib/taskDateTime';
import { Button } from '../ui/Button';

type Props = {
  task: TaskDraftAction;
  accessToken: string | null;
  language: string;
  /** Giữ tương thích với các caller cũ; card không còn hiển thị navigation actions. */
  onOpenTasks?: () => void;
  onReconnectGoogle?: () => void;
};

export const ChatTaskDraftCard: React.FC<Props> = ({
  task,
  accessToken,
  language,
}) => {
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [title, setTitle] = useState(task.title);
  const [detail, setDetail] = useState(task.detail || '');
  // Keep the input local, but convert from the full ISO instant first. Slicing
  // the ISO string would drop `Z`/the offset and display UTC as local time.
  const [dueAt, setDueAt] = useState(task.dueAt ? toLocalDateTimeInputValue(task.dueAt) : '');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pending, setPending] = useState<'delete' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const vi = language === 'vi';

  const handleDelete = async () => {
    if (!accessToken) return;
    setPending('delete');
    setError(null);
    try {
      const updated = await cancelTask(task.id, accessToken);
      setStatus(updated.status);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : vi ? 'Không thể xóa task.' : 'Could not delete task.');
    } finally {
      setPending(null);
    }
  };

  const handleSave = async () => {
    if (!accessToken || !title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateTask(task.id, {
        title: title.trim(),
        detail: detail.trim(),
        dueAt: dueAt ? new Date(dueAt).toISOString() : null,
      }, accessToken);
      setTitle(updated.title);
      setDetail(updated.detail);
      setDueAt(updated.dueAt ? toLocalDateTimeInputValue(updated.dueAt) : '');
      setEditing(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : vi ? 'Không thể lưu thay đổi.' : 'Could not save changes.');
    } finally {
      setSaving(false);
    }
  };

  if (status === 'dismissed' || status === 'completed' || status === 'cancelled') return null;

  return (
    <section
      aria-label={vi ? `Bản nháp task ${task.title}` : `Task draft ${task.title}`}
      className="max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 shadow-2xs"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
              {vi ? 'Task đã tạo' : 'Task created'}
            </p>
            {/* Nhãn nguồn: nhìn thẻ là biết việc này lấy từ Gmail hay Jira.
                Không có nhãn thì không vẽ gì — task người dùng tự tạo (hoặc
                nguồn đã gỡ kết nối) không nên bị gán bừa một nền tảng. */}
            {task.sourceLabel ? (
              <span
                className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-0.5 text-[10px] font-semibold text-[var(--color-text-secondary)]"
                title={vi ? `Nguồn: ${task.sourceLabel}` : `Source: ${task.sourceLabel}`}
              >
                {task.sourceLabel}
              </span>
            ) : null}
          </div>
          {editing ? (
            <div className="mt-2 space-y-2">
              <input aria-label={vi ? 'Tiêu đề task' : 'Task title'} value={title} onChange={(event) => setTitle(event.target.value)} className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm" />
              <textarea aria-label={vi ? 'Chi tiết task' : 'Task details'} value={detail} onChange={(event) => setDetail(event.target.value)} className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm" rows={2} />
              <input aria-label={vi ? 'Hạn task' : 'Task deadline'} type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm" />
            </div>
          ) : (
            <>
              <h3 className="mt-1 font-semibold text-[var(--color-text-primary)]">{title}</h3>
              {detail && <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{detail}</p>}
              <p className="mt-1 text-xs text-[var(--color-text-muted)]">{dueAt ? formatTaskDueAt(dueAt, vi ? 'vi-VN' : 'en-GB') : (vi ? 'Chưa có hạn chót' : 'No due date')}</p>
            </>
          )}
        </div>
        {status === 'confirmed' && <Check className="h-5 w-5 shrink-0 text-[var(--color-success)]" />}
      </div>

      {error && <p role="alert" className="mt-3 text-sm text-[var(--color-danger)]">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => editing ? void handleSave() : setEditing(true)} disabled={saving || !accessToken}>
          {editing ? <Save className="mr-1.5 h-4 w-4" /> : <Pencil className="mr-1.5 h-4 w-4" />}
          {editing ? (saving ? (vi ? 'Đang lưu…' : 'Saving…') : (vi ? 'Lưu thay đổi' : 'Save changes')) : (vi ? 'Chỉnh sửa' : 'Edit details')}
        </Button>
        <Button size="sm" variant="outline" onClick={() => void handleDelete()} disabled={!accessToken || pending !== null}>
          <Trash2 className="mr-1.5 h-4 w-4" />
          {pending === 'delete' ? (vi ? 'Đang xóa…' : 'Deleting…') : (vi ? 'Xóa task' : 'Delete task')}
        </Button>
      </div>
    </section>
  );
};
