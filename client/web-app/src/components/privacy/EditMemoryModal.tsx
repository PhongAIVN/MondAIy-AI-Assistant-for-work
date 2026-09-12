import React, { useState, useEffect } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { type CanonicalMemory } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { X, Check, Brain, Info } from 'lucide-react';

interface EditMemoryModalProps {
  memory: CanonicalMemory | null;
  isOpen: boolean;
  onClose: () => void;
}

export const EditMemoryModal: React.FC<EditMemoryModalProps> = ({
  memory,
  isOpen,
  onClose,
}) => {
  const { t, language } = useTranslation();
  const { editMemory } = useDataPrivacyStore();
  const [statement, setStatement] = useState(memory?.statement || '');

  useEffect(() => {
    if (memory) {
      setStatement(memory.statement);
    }
  }, [memory]);

  if (!isOpen || !memory) return null;

  const handleSave = () => {
    if (statement.trim() && statement.trim() !== memory.statement) {
      editMemory(memory.id, statement.trim());
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white dark:bg-[#122038] rounded-2xl shadow-2xl border border-[#E4EAF6] dark:border-[#1E2E4A] overflow-hidden flex flex-col"
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
                {t.dataPrivacy.memory.editMemory}
              </h2>
              <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] mt-0.5">
                {memory.category} · {memory.sourceReference}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <div className="p-3.5 bg-[#E1EBFA] dark:bg-[#0F1F38] border border-[#D5DDEB] dark:border-[#1E2E4A] rounded-xl flex items-start gap-2.5 text-xs text-[#0F1F38] dark:text-[#E1EBFA]">
            <Info className="w-4 h-4 text-[#2563A6] shrink-0 mt-0.5" />
            <span>
              {language === 'vi'
                ? 'Thay đổi này sẽ tạo một phiên bản mới trong bộ nhớ được sử dụng để cá nhân hóa các câu trả lời AI.'
                : 'This change will create a new version in retained memory used to personalize future AI responses.'}
            </span>
          </div>

          <div>
            <label className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] block mb-2">
              {language === 'vi' ? 'Nội dung ghi nhớ:' : 'Memory Statement:'}
            </label>
            <textarea
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
              rows={4}
              className="w-full p-3 bg-white dark:bg-[#122038] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs font-semibold text-[#0F1F38] dark:text-[#E2E8F0] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#0F1F38]"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[#E4EAF6] dark:border-[#1E2E4A] bg-[#EDF2FB] dark:bg-[#0F1F38] flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white dark:bg-[#122038] border border-[#E4EAF6] dark:border-[#1E2E4A] text-[#5A6A85] dark:text-[#AEB9CC] rounded-xl font-bold text-xs hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] transition-colors"
          >
            {language === 'vi' ? 'Hủy' : 'Cancel'}
          </button>
          <button
            onClick={handleSave}
            className="px-5 py-2 bg-[#0F1F38] dark:bg-[#2563A6] text-white rounded-xl font-bold text-xs shadow-2xs hover:bg-[#1E4E85] transition-colors flex items-center gap-2"
          >
            <Check className="w-4 h-4" />
            {language === 'vi' ? 'Lưu ghi nhớ' : 'Save Memory'}
          </button>
        </div>
      </div>
    </div>
  );
};
