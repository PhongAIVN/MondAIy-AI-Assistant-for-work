import React, { useState } from 'react';

import { previewDiscordAnnouncement, publishDiscordAnnouncement, type AdminAnnouncementCandidate, type AdminAnnouncementCategory } from '../../lib/adminApi';
import { useAuthStore } from '../../stores/useAuthStore';

const localReferenceValue = (): string => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
};

const categories: AdminAnnouncementCategory[] = [
  'overview', 'schedule', 'policy', 'submission', 'support', 'other',
];

const toDateTimeLocal = (value: string | null): string => {
  if (!value) return '';
  const local = value.replace(/(?:Z|[+-]\d{2}:\d{2})$/, '');
  return /^\d{4}-\d{2}-\d{2}$/.test(local) ? `${local}T00:00` : local.slice(0, 16);
};
const fromDateTimeLocal = (value: string): string | null => value ? `${value}:00+07:00` : null;

export const AdminDiscordAnnouncementPage: React.FC = () => {
  const token = useAuthStore((state) => state.accessToken);
  const [rawText, setRawText] = useState('');
  const [referenceDate, setReferenceDate] = useState(localReferenceValue);
  const [item, setItem] = useState<AdminAnnouncementCandidate | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const preview = async () => {
    if (!token) return;
    setBusy(true); setError('');
    try {
      setItem(await previewDiscordAnnouncement(token, {
        rawText,
        referenceDate: referenceDate ? `${referenceDate}:00+07:00` : undefined,
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể xem trước.');
    } finally {
      setBusy(false);
    }
  };
  const publish = async () => {
    if (!token || !item) return;
    setBusy(true); setError('');
    try {
      setItem(await publishDiscordAnnouncement(token, item.id, {
        title: item.preview.title,
        category: item.preview.category,
        aliases: item.preview.aliases.map((value) => value.trim()).filter(Boolean),
        items: item.preview.items.map(({ title, kind, dueAt, allDay }) => ({ title, kind, dueAt, allDay })),
      }));
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể phát hành.'); }
    finally { setBusy(false); }
  };
  return (
    <main className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Nạp thông báo Discord</h1>
        <p className="text-sm text-slate-500">
          Nguồn Mức A cho học viên Type A; không tự ghi Google Calendar.
        </p>
      </div>
      <label className="block space-y-1">
        <span>Thời điểm thông báo</span>
        <input
          aria-label="Reference date"
          type="datetime-local"
          value={referenceDate}
          onChange={(event) => setReferenceDate(event.target.value)}
          className="rounded-xl border p-2"
        />
      </label>
      <textarea
        aria-label="Discord announcement"
        value={rawText}
        onChange={(event) => setRawText(event.target.value)}
        className="min-h-48 w-full rounded-xl border p-3"
        placeholder="Dán thông báo Discord…"
      />
      <button
        type="button"
        disabled={!rawText.trim() || busy}
        onClick={preview}
        className="rounded-xl bg-blue-700 px-4 py-2 font-semibold text-white"
      >
        {busy ? 'Đang xử lý…' : 'Xem trước'}
      </button>
      {error && <p role="alert">{error}</p>}
      {item && (
        <section className="space-y-2 rounded-xl border p-4">
          <p><b>Nguồn:</b> Mức {item.evidence.sourceLevel} · {item.evidence.channel}</p>
          <p>
            <b>Trích xuất:</b>{' '}
            {item.preview.extractionMethod === 'llm' ? 'LLM' : `Regex fallback (${item.preview.fallbackReason ?? 'không rõ lỗi'})`}
          </p>
          <pre className="whitespace-pre-wrap text-sm">{item.rawText}</pre>
          <div className="space-y-1 rounded-lg bg-slate-50 p-3">
            <label className="block space-y-1">
              <span>Tiêu đề sẽ publish</span>
              <input
                aria-label="Tiêu đề sẽ publish"
                value={item.preview.title}
                disabled={item.status === 'published'}
                onChange={(event) => setItem({ ...item, preview: { ...item.preview, title: event.target.value } })}
                className="w-full rounded-xl border p-2"
              />
            </label>
            <p><b>Nội dung sẽ publish:</b></p>
            <pre className="whitespace-pre-wrap text-sm">{item.preview.body}</pre>
          </div>
          <label className="block space-y-1">
            <span>Category đề xuất</span>
            <select
              aria-label="Category đề xuất"
              value={item.preview.category}
              disabled={item.status === 'published'}
              onChange={(event) => setItem({
                ...item,
                preview: { ...item.preview, category: event.target.value as AdminAnnouncementCategory },
              })}
              className="rounded-xl border p-2"
            >
              {categories.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </label>
          <label className="block space-y-1">
            <span>Aliases đề xuất (mỗi dòng một cách gọi)</span>
            <textarea
              aria-label="Aliases đề xuất"
              value={item.preview.aliases.join('\n')}
              disabled={item.status === 'published'}
              onChange={(event) => setItem({
                ...item,
                preview: {
                  ...item.preview,
                  aliases: event.target.value.split('\n'),
                },
              })}
              className="min-h-24 w-full rounded-xl border p-2"
            />
          </label>
          {item.preview.items.map((action, index) => (
            <div key={`${action.title}-${index}`} className="space-y-2 rounded-lg border p-3">
              <label className="block space-y-1">
                <span>Action {index + 1} title</span>
                <input
                  aria-label={`Action ${index + 1} title`}
                  value={action.title}
                  disabled={item.status === 'published'}
                  onChange={(event) => setItem({ ...item, preview: { ...item.preview, items: item.preview.items.map((current, currentIndex) => currentIndex === index ? { ...current, title: event.target.value } : current) } })}
                  className="w-full rounded-xl border p-2"
                />
              </label>
              <label className="block space-y-1">
                <span>Action kind</span>
                <select
                  aria-label={`Action ${index + 1} kind`}
                  value={action.kind}
                  disabled={item.status === 'published'}
                  onChange={(event) => setItem({ ...item, preview: { ...item.preview, items: item.preview.items.map((current, currentIndex) => currentIndex === index ? { ...current, kind: event.target.value as typeof action.kind } : current) } })}
                  className="rounded-xl border p-2"
                >
                  {['task', 'calendar', 'change', 'resource'].map((kind) => <option key={kind} value={kind}>{kind}</option>)}
                </select>
              </label>
              <label className="block space-y-1">
                <span>Due date/time</span>
                <input
                  aria-label={`Action ${index + 1} due date`}
                  type="datetime-local"
                  value={toDateTimeLocal(action.dueAt)}
                  disabled={item.status === 'published'}
                  onChange={(event) => setItem({ ...item, preview: { ...item.preview, items: item.preview.items.map((current, currentIndex) => currentIndex === index ? { ...current, dueAt: fromDateTimeLocal(event.target.value), ambiguous: !event.target.value } : current) } })}
                  className="rounded-xl border p-2"
                />
              </label>
              <label className="flex items-center gap-2">
                <input
                  aria-label={`Action ${index + 1} all day`}
                  type="checkbox"
                  checked={action.allDay}
                  disabled={item.status === 'published'}
                  onChange={(event) => setItem({ ...item, preview: { ...item.preview, items: item.preview.items.map((current, currentIndex) => currentIndex === index ? { ...current, allDay: event.target.checked } : current) } })}
                />
                All day
              </label>
              <p><b>{action.kind}:</b> {action.title} · {action.dueAt ?? 'Chưa có ngày/giờ'}
              {action.ambiguous && (
                <span className="text-amber-700"> — {action.ambiguityReason}</span>
              )}
              </p>
            </div>
          ))}
          {item.status === 'published' ? (
            <p>
              Đã publish thông tin #{item.informationItemId}; learner tự thêm và
              xác nhận task trước khi calendar handoff.
            </p>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={publish}
              className="rounded-xl bg-emerald-700 px-4 py-2 font-semibold text-white"
            >
              Xác nhận và phát hành
            </button>
          )}
        </section>
      )}
    </main>
  );
};
