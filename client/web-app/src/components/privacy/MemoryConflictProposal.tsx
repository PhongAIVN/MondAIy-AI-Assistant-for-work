import React from 'react';
import { AlertTriangle, Check, Trash2 } from 'lucide-react';
import type { MemoryItem } from '../../lib/memoryApi';

type Props = {
  memories: MemoryItem[];
  language: string;
  busyKey: string | null;
  onChoose: (key: string, version: number) => void;
  onDelete: (key: string) => void;
};

export const MemoryConflictProposal: React.FC<Props> = ({ memories, language, busyKey, onChoose, onDelete }) => {
  if (memories.length < 2) return null;
  const vi = language === 'vi';
  return (
    <section className="rounded-2xl border border-[#D7B270] bg-[#F6EEDA] p-5 dark:border-[#5A4430] dark:bg-[#211B13]" aria-label={vi ? 'Đề xuất xử lý xung đột memory' : 'Memory conflict proposal'}>
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-[#A05B19]" />
        <div>
          <h3 className="text-sm font-extrabold text-[var(--color-text-primary)]">{vi ? 'Có thông tin mâu thuẫn' : 'Conflicting information found'}</h3>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{vi ? 'Mình giữ cả hai phiên bản. Bạn chọn bản đúng hoặc xoá toàn bộ memory này.' : 'Both versions are kept. Choose the correct one or delete this memory.'}</p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {memories.map((memory) => {
          const value = typeof memory.value === 'string' ? memory.value : JSON.stringify(memory.value);
          const busy = busyKey === memory.key;
          return (
            <article key={`${memory.key}:${memory.version}`} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 text-[10px] font-bold text-[var(--color-primary)]">v{memory.version}</span>
                <span className="text-[10px] text-[var(--color-text-secondary)]">{memory.source}</span>
              </div>
              <p className="mt-3 text-sm font-bold text-[var(--color-text-primary)]">{memory.predicate.replace(/_/g, ' ')}: {value}</p>
              <p className="mt-1 text-[11px] text-[var(--color-text-secondary)]">{new Date(memory.lastReinforcedAt).toLocaleDateString(vi ? 'vi-VN' : 'en-GB')}</p>
              <div className="mt-3 flex gap-2">
                <button type="button" aria-label={vi ? `Giữ phiên bản v${memory.version}` : `Keep version v${memory.version}`} disabled={Boolean(busyKey)} onClick={() => onChoose(memory.key, memory.version)} className="inline-flex items-center gap-1 rounded-lg bg-[#2A6B4F] px-2.5 py-1.5 text-xs font-bold text-white disabled:opacity-50">
                  <Check className="h-3.5 w-3.5" />{vi ? 'Giữ bản này' : 'Keep this'}
                </button>
                <button type="button" aria-label={vi ? `Xoá toàn bộ memory (đang xem v${memory.version})` : `Delete entire memory (viewing v${memory.version})`} disabled={Boolean(busyKey)} onClick={() => onDelete(memory.key)} className="inline-flex items-center gap-1 rounded-lg bg-[#F9DEDE] px-2.5 py-1.5 text-xs font-bold text-[#A03D3D] disabled:opacity-50">
                  <Trash2 className="h-3.5 w-3.5" />{vi ? 'Xoá memory' : 'Delete memory'}
                </button>
              </div>
              {busy && <span className="mt-2 block text-[10px] text-[var(--color-text-secondary)]">{vi ? 'Đang cập nhật...' : 'Updating...'}</span>}
            </article>
          );
        })}
      </div>
    </section>
  );
};
