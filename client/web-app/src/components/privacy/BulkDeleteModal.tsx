import React, { useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { X, Trash2, ShieldAlert } from 'lucide-react';

interface BulkDeleteModalProps {
  sourceName?: string;
  sourceId?: string;
  selectedRecordIds?: string[];
  isOpen: boolean;
  onClose: () => void;
}

export const BulkDeleteModal: React.FC<BulkDeleteModalProps> = ({
  sourceName,
  sourceId,
  selectedRecordIds = [],
  isOpen,
  onClose,
}) => {
  const { t, language } = useTranslation();
  const { deleteAllSourceData, bulkDeleteRecords } = useDataPrivacyStore();

  const isFullSourcePurge = Boolean(sourceId && sourceName);
  const requiredCode = isFullSourcePurge
    ? `DELETE ${sourceName?.toUpperCase()} DATA`
    : '';

  const [inputCode, setInputCode] = useState('');

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (isFullSourcePurge && sourceId) {
      if (inputCode.trim() !== requiredCode) return;
      deleteAllSourceData(sourceId);
    } else if (selectedRecordIds.length > 0) {
      bulkDeleteRecords(selectedRecordIds);
    }
    onClose();
  };

  const isButtonDisabled = isFullSourcePurge && inputCode.trim() !== requiredCode;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white dark:bg-[#122038] rounded-2xl shadow-2xl border border-[#E4EAF6] dark:border-[#1E2E4A] overflow-hidden flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-6 border-b border-[#E4EAF6] dark:border-[#1E2E4A] flex items-center justify-between bg-[#F9DEDE] dark:bg-[#0F1F38]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white dark:bg-[#122038] flex items-center justify-center text-[#A03D3D] dark:text-[#DC9A91]">
              <Trash2 className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-extrabold text-[#A03D3D] dark:text-[#DC9A91] font-heading">
              {isFullSourcePurge
                ? language === 'vi'
                  ? `Xóa tất cả dữ liệu ${sourceName}`
                  : `Delete All ${sourceName} Data`
                : t.dataPrivacy.activity.deleteConfirmTitle}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-white dark:hover:bg-[#1A2A42] rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] leading-relaxed">
            {isFullSourcePurge
              ? language === 'vi'
                ? `Hành động này sẽ xóa vĩnh viễn tất cả các bản ghi thông tin đã được thu thập từ ${sourceName}. Thông tin này sẽ không còn xuất hiện trong các briefing hoặc phản hồi AI tương lai.`
                : `This action will permanently purge all captured records and memories associated with ${sourceName}. This content will no longer be available for future AI processing.`
              : t.dataPrivacy.activity.deleteConfirmDesc}
          </p>

          {isFullSourcePurge && (
            <div className="space-y-2 p-4 bg-[#EDF2FB] dark:bg-[#0F1F38] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A]">
              <label className="text-xs font-bold text-[#0F1F38] dark:text-[#E2E8F0] block">
                {t.dataPrivacy.activity.typeToConfirmNotice.replace('{code}', requiredCode)}
              </label>
              <input
                type="text"
                value={inputCode}
                onChange={(e) => setInputCode(e.target.value)}
                placeholder={requiredCode}
                className="w-full p-2.5 bg-white dark:bg-[#122038] rounded-lg border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs font-bold text-[#0F1F38] dark:text-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#A03D3D]"
              />
            </div>
          )}

          <div className="p-3.5 bg-[#F9DEDE] dark:bg-[#0F1F38] border border-[#F0D8D3] dark:border-[#1E2E4A] rounded-xl flex items-center gap-2.5 text-xs text-[#A03D3D] dark:text-[#DC9A91] font-medium">
            <ShieldAlert className="w-4 h-4 shrink-0" />
            <span>{t.dataPrivacy.activity.deleteImpactNote}</span>
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
            disabled={isButtonDisabled}
            onClick={handleConfirm}
            className="px-5 py-2 bg-[#A03D3D] text-white rounded-xl font-bold text-xs shadow-2xs hover:bg-[#8A3434] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            {language === 'vi' ? 'Xác nhận xóa' : 'Confirm Deletion'}
          </button>
        </div>
      </div>
    </div>
  );
};
