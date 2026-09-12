import React, { useEffect, useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { type MemoryItem } from '../../lib/memoryApi';
import { X, Brain, CheckCircle2, XCircle, Trash2, Tag, Pencil, Save, Link2 } from 'lucide-react';

interface MemoryDetailDrawerProps {
  memory: MemoryItem | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (key: string) => void;
  onReject: (key: string) => void;
  onDelete: (key: string) => void;
  onEdit: (key: string, value: string) => void;
  busy?: boolean;
}

export const MemoryDetailDrawer: React.FC<MemoryDetailDrawerProps> = ({
  memory,
  isOpen,
  onClose,
  onConfirm,
  onReject,
  onDelete,
  onEdit,
  busy = false,
}) => {
  const { t, language } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draftValue, setDraftValue] = useState('');

  useEffect(() => {
    const nextValue = typeof memory?.value === 'string' ? memory.value : JSON.stringify(memory?.value ?? '');
    setDraftValue(nextValue);
    setEditing(false);
  }, [memory?.key, memory?.version, memory?.value]);

  if (!isOpen || !memory) return null;

  const readablePredicate = memory.predicate.replace(/_/g, ' ');
  const value = typeof memory.value === 'string' ? memory.value : JSON.stringify(memory.value);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white dark:bg-[#122038] h-full shadow-2xl flex flex-col border-l border-[#E4EAF6] dark:border-[#1E2E4A] animate-in slide-in-from-right duration-300"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-6 border-b border-[#E4EAF6] dark:border-[#1E2E4A] flex items-center justify-between bg-[#EDF2FB] dark:bg-[#0F1F38]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#E1EBFA] dark:bg-[#1A2A42] flex items-center justify-center text-[#0F1F38] dark:text-[#7EB0E8]">
              <Brain className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
                {language === 'vi' ? 'Chi tiết ghi nhớ' : 'Memory Record Details'}
              </h2>
              <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] mt-0.5">
                {memory.kind} · {memory.source}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label={language === 'vi' ? 'Đóng' : 'Close'}
            className="p-2 text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Statement Box */}
          <div className="p-4 bg-[#E1EBFA] dark:bg-[#0F1F38] rounded-2xl border border-[#D5DDEB] dark:border-[#1E2E4A]">
            <span className="text-[10px] font-medium text-[#2563A6] dark:text-[#7EB0E8] block mb-1">
              {language === 'vi' ? 'Nội dung ghi nhớ' : 'Memory Statement'}
            </span>
            {editing ? (
              <div className="space-y-3">
                <label className="sr-only" htmlFor="memory-value-editor">
                  {language === 'vi' ? 'Giá trị ghi nhớ' : 'Memory value'}
                </label>
                <textarea
                  id="memory-value-editor"
                  value={draftValue}
                  onChange={(event) => setDraftValue(event.target.value)}
                  maxLength={500}
                  rows={4}
                  className="w-full rounded-xl border border-[#B8C7DE] bg-white p-3 text-sm text-[#0F1F38] outline-none focus:ring-2 focus:ring-[#2563A6] dark:border-[#355070] dark:bg-[#122038] dark:text-[#E2E8F0]"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setDraftValue(value);
                      setEditing(false);
                    }}
                    className="px-3 py-1.5 text-xs font-bold text-[#5A6A85]"
                  >
                    {language === 'vi' ? 'Hủy' : 'Cancel'}
                  </button>
                  <button
                    type="button"
                    onClick={() => onEdit(memory.key, draftValue.trim())}
                    disabled={busy || !draftValue.trim() || draftValue.trim() === value}
                    className="flex items-center gap-1.5 rounded-lg bg-[#2563A6] px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {language === 'vi' ? 'Lưu phiên bản mới' : 'Save new version'}
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm font-bold text-[#0F1F38] dark:text-[#E2E8F0] leading-relaxed">
                {readablePredicate}: {value}
              </p>
            )}
          </div>

          {/* Pending Actions Bar */}
          {memory.status === 'candidate' && (
            <div className="p-4 bg-[#F6EEDA] dark:bg-[#2E2717] border border-[#D7B270] dark:border-[#6A4711] rounded-xl space-y-3">
              <span className="text-xs font-bold text-[#8A5712] dark:text-[#D7B270] block">
                {t.dataPrivacy.memory.candidateNotice}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => onConfirm(memory.key)}
                  disabled={busy}
                  className="px-3.5 py-1.5 bg-[#2A6B4F] text-white rounded-lg text-xs font-bold hover:bg-[#27573F] transition-colors flex items-center gap-1.5"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  {t.dataPrivacy.memory.confirm}
                </button>
                <button
                  onClick={() => onReject(memory.key)}
                  disabled={busy}
                  className="px-3.5 py-1.5 bg-[#A03D3D] text-white rounded-lg text-xs font-bold hover:bg-[#8A3434] transition-colors flex items-center gap-1.5"
                >
                  <XCircle className="w-4 h-4" />
                  {t.dataPrivacy.memory.reject}
                </button>
              </div>
            </div>
          )}

          {/* Field details — chỉ hiện field thật backend trả về, không bịa lịch sử phiên bản */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] flex items-center gap-1.5">
              <Tag className="w-4 h-4 text-[#2563A6]" />
              {language === 'vi' ? 'Chi tiết' : 'Details'}
            </h3>
            <div className="p-4 bg-white dark:bg-[#122038] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs text-[#0F1F38] dark:text-[#E2E8F0] space-y-1.5">
              <div className="flex justify-between">
                <span className="text-[#5A6A85] dark:text-[#AEB9CC]">{language === 'vi' ? 'Phiên bản' : 'Version'}</span>
                <span>v{memory.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#5A6A85] dark:text-[#AEB9CC]">{language === 'vi' ? 'Độ tin cậy' : 'Confidence'}</span>
                <span>{Math.round(memory.confidence * 100)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#5A6A85] dark:text-[#AEB9CC]">{language === 'vi' ? 'Số lần củng cố' : 'Reinforced'}</span>
                <span>{memory.reinforcementCount}×</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#5A6A85] dark:text-[#AEB9CC]">{language === 'vi' ? 'Quan sát lần đầu' : 'First observed'}</span>
                <span>
                  {new Date(memory.firstObservedAt).toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-GB')}
                </span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="flex items-center gap-1.5 text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0]">
              <Link2 className="h-4 w-4 text-[#2563A6]" />
              {language === 'vi' ? 'Bằng chứng đã dùng' : 'Supporting evidence'}
            </h3>
            {memory.evidence?.length ? (
              <ul className="space-y-2">
                {memory.evidence.map((item) => (
                  <li
                    key={`${item.evidenceType}:${item.evidenceRef}`}
                    className="rounded-xl border border-[#E4EAF6] bg-white p-3 text-xs text-[#0F1F38] dark:border-[#1E2E4A] dark:bg-[#122038] dark:text-[#E2E8F0]"
                  >
                    <span className="font-bold">{item.evidenceType.replace(/_/g, ' ')}</span>
                    <span className="ml-2 break-all text-[#5A6A85] dark:text-[#AEB9CC]">#{item.evidenceRef}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="rounded-xl border border-[#D7B270] bg-[#F6EEDA] p-3 text-xs text-[#8A5712] dark:bg-[#2E2717] dark:text-[#D7B270]">
                {language === 'vi' ? 'Không tìm thấy bằng chứng cho phiên bản này.' : 'No evidence was found for this version.'}
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E4EAF6] dark:border-[#1E2E4A] bg-[#EDF2FB] dark:bg-[#0F1F38] flex items-center justify-end gap-3">
          <button
            onClick={() => setEditing(true)}
            disabled={busy || editing}
            className="flex items-center gap-2 rounded-xl border border-[#B8C7DE] bg-white px-3.5 py-2 text-xs font-bold text-[#2563A6] disabled:opacity-50 dark:border-[#355070] dark:bg-[#122038] dark:text-[#7EB0E8]"
          >
            <Pencil className="h-4 w-4" />
            {language === 'vi' ? 'Sửa ghi nhớ' : 'Edit memory'}
          </button>
          <button
            onClick={() => onDelete(memory.key)}
            disabled={busy}
            className="px-3.5 py-2 bg-[#F9DEDE] dark:bg-[#0F1F38] text-[#A03D3D] dark:text-[#DC9A91] border border-[#F0D8D3] dark:border-[#1E2E4A] rounded-xl font-bold text-xs hover:bg-[#F0D8D3] transition-colors flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            {t.dataPrivacy.memory.deleteMemory}
          </button>
        </div>
      </div>
    </div>
  );
};
