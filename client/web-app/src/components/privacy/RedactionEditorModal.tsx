import React, { useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { type CapturedRecord } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { Scissors, AlertTriangle, X, Check, FileText } from 'lucide-react';

interface RedactionEditorModalProps {
  record: CapturedRecord | null;
  isOpen: boolean;
  onClose: () => void;
}

export const RedactionEditorModal: React.FC<RedactionEditorModalProps> = ({
  record,
  isOpen,
  onClose,
}) => {
  const { t, language } = useTranslation();
  const { redactCapturedRecord } = useDataPrivacyStore();

  const [selectedExcerpt, setSelectedExcerpt] = useState('');
  const [editedText, setEditedText] = useState(record?.originalContent || '');

  React.useEffect(() => {
    if (record) {
      setEditedText(record.originalContent);
      setSelectedExcerpt('');
    }
  }, [record]);

  if (!isOpen || !record) return null;

  const handleTextSelection = () => {
    const selection = window.getSelection()?.toString().trim();
    if (selection && selection.length > 2) {
      setSelectedExcerpt(selection);
    }
  };

  const handleRedactExcerpt = () => {
    if (!selectedExcerpt) return;
    const updated = editedText.replace(selectedExcerpt, '[REDACTED BY USER]');
    setEditedText(updated);
  };

  const handleSave = () => {
    if (!selectedExcerpt && editedText === record.originalContent) {
      onClose();
      return;
    }
    redactCapturedRecord(
      record.id,
      editedText,
      selectedExcerpt || 'User modified content segment'
    );
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-2xl bg-white dark:bg-[#122038] rounded-2xl shadow-2xl border border-[#E4EAF6] dark:border-[#1E2E4A] overflow-hidden flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-6 border-b border-[#E4EAF6] dark:border-[#1E2E4A] flex items-center justify-between bg-[#EDF2FB] dark:bg-[#0F1F38]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#E1EBFA] dark:bg-[#1A2A42] flex items-center justify-center text-[#0F1F38] dark:text-[#7EB0E8]">
              <Scissors className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
                {t.dataPrivacy.redaction.modalTitle}
              </h2>
              <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] mt-0.5">
                {record.sourceName} · {record.sourceLocation}
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
        <div className="p-6 overflow-y-auto space-y-5">
          <div className="p-3.5 bg-[#E1EBFA] dark:bg-[#0F1F38] border border-[#D5DDEB] dark:border-[#1E2E4A] rounded-xl flex items-start gap-3 text-xs text-[#0F1F38] dark:text-[#E1EBFA]">
            <FileText className="w-4 h-4 text-[#2563A6] dark:text-[#7EB0E8] shrink-0 mt-0.5" />
            <span>{t.dataPrivacy.redaction.selectNotice}</span>
          </div>

          {/* Interactive selection area */}
          <div>
            <label className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] block mb-2">
              {language === 'vi' ? 'Nội dung nguồn hiện tại (Bôi đen để chọn):' : 'Current Source Content (Select text to highlight excerpt):'}
            </label>
            <div
              onMouseUp={handleTextSelection}
              className="p-4 bg-[#EDF2FB] dark:bg-[#0F1F38] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-sm text-[#0F1F38] dark:text-[#E2E8F0] leading-relaxed select-text cursor-text min-h-[100px]"
            >
              {editedText}
            </div>
          </div>

          {/* Selected excerpt action */}
          {selectedExcerpt && (
            <div className="p-4 bg-[#F6EEDA] dark:bg-[#2E2717] border border-[#D7B270] dark:border-[#6A4711] rounded-xl flex items-center justify-between gap-3 animate-in fade-in">
              <div>
                <span className="text-[10px] font-medium text-[#8A5712] dark:text-[#D7B270] block mb-0.5">
                  {language === 'vi' ? 'Đoạn văn bản đã chọn:' : 'Selected Excerpt:'}
                </span>
                <p className="text-xs font-semibold text-[#0F1F38] dark:text-[#E2E8F0]">
                  "{selectedExcerpt}"
                </p>
              </div>
              <button
                type="button"
                onClick={handleRedactExcerpt}
                className="px-3 py-1.5 bg-[#8A5712] text-white rounded-lg text-xs font-bold shrink-0 hover:bg-[#6A4711] transition-colors flex items-center gap-1.5"
              >
                <Scissors className="w-3.5 h-3.5" />
                {language === 'vi' ? 'Xóa đoạn này' : 'Redact Excerpt'}
              </button>
            </div>
          )}

          {/* Direct editor text area fallback */}
          <div>
            <label className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] block mb-2">
              {t.dataPrivacy.redaction.updatedPreview}
            </label>
            <textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={4}
              className="w-full p-3 bg-white dark:bg-[#122038] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs text-[#0F1F38] dark:text-[#E2E8F0] leading-relaxed focus:outline-none focus:ring-2 focus:ring-[#0F1F38]"
            />
          </div>

          {/* Impact Notice */}
          <div className="p-3.5 bg-[#F9DEDE] dark:bg-[#0F1F38] border border-[#F0D8D3] dark:border-[#1E2E4A] rounded-xl flex items-center gap-2.5 text-xs text-[#A03D3D] dark:text-[#DC9A91] font-medium">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{t.dataPrivacy.redaction.saveNotice}</span>
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
            {language === 'vi' ? 'Lưu thay đổi' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};
