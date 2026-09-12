import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { type CapturedRecord } from '../../types/dataPrivacy';
import {
  X,
  FileText,
  Clock,
  Scissors,
  Trash2,
  Sparkles,
  ShieldCheck,
  Tag
} from 'lucide-react';

interface CapturedRecordDrawerProps {
  record: CapturedRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenRedactModal: (record: CapturedRecord) => void;
  onDeleteRecord: (recordId: string) => void;
}

export const CapturedRecordDrawer: React.FC<CapturedRecordDrawerProps> = ({
  record,
  isOpen,
  onClose,
  onOpenRedactModal,
  onDeleteRecord,
}) => {
  const { t, language } = useTranslation();

  if (!isOpen || !record) return null;

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
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
                {t.dataPrivacy.activity.recordDetailTitle}
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

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 p-4 bg-[#EDF2FB] dark:bg-[#0F1F38] rounded-2xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs">
            <div>
              <span className="text-[#5A6A85] dark:text-[#AEB9CC] block font-medium">
                {language === 'vi' ? 'Thời gian gốc:' : 'Original Timestamp:'}
              </span>
              <span className="font-bold text-[#0F1F38] dark:text-[#E2E8F0] mt-0.5 block flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-[#2563A6]" />
                {record.originalTimestamp}
              </span>
            </div>
            <div>
              <span className="text-[#5A6A85] dark:text-[#AEB9CC] block font-medium">
                {language === 'vi' ? 'Thời gian thu thập:' : 'Capture Timestamp:'}
              </span>
              <span className="font-bold text-[#0F1F38] dark:text-[#E2E8F0] mt-0.5 block flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#2A6B4F]" />
                {record.capturedAt}
              </span>
            </div>
            <div>
              <span className="text-[#5A6A85] dark:text-[#AEB9CC] block font-medium">
                {language === 'vi' ? 'Mức tin cậy:' : 'Confidence Level:'}
              </span>
              <span className="font-bold text-[#0F1F38] dark:text-[#E2E8F0] mt-0.5 block">
                {record.confidence}
              </span>
            </div>
            <div>
              <span className="text-[#5A6A85] dark:text-[#AEB9CC] block font-medium">
                {language === 'vi' ? 'Trạng thái lưu trữ:' : 'Retention Status:'}
              </span>
              <span className="font-bold text-[#0F1F38] dark:text-[#E2E8F0] mt-0.5 block capitalize">
                {record.retentionStatus}
              </span>
            </div>
          </div>

          {/* Original Source Content */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-[#2563A6]" />
              {t.dataPrivacy.activity.originalContent}
            </h3>
            <div className="p-4 bg-white dark:bg-[#122038] rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] text-xs text-[#0F1F38] dark:text-[#E2E8F0] leading-relaxed">
              {record.originalContent}
            </div>
          </div>

          {/* AI Interpretation */}
          <div className="space-y-2">
            <h3 className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-[#2563A6]" />
              {t.dataPrivacy.activity.aiInterpretation}
            </h3>
            <div className="p-4 bg-[#E1EBFA] dark:bg-[#0F1F38] rounded-xl border border-[#D5DDEB] dark:border-[#1E2E4A] text-xs text-[#0F1F38] dark:text-[#E1EBFA] font-medium leading-relaxed">
              {record.extractedInformation}
            </div>
          </div>

          {/* Where used */}
          {record.usedInBriefingTitle && (
            <div className="space-y-2">
              <h3 className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] flex items-center gap-1.5">
                <Tag className="w-4 h-4 text-[#2A6B4F]" />
                {t.dataPrivacy.activity.usedInLocation}
              </h3>
              <div className="p-3 bg-[#DFF0E6] dark:bg-[#0F1F38] rounded-xl border border-[#C4DDCB] dark:border-[#1E2E4A] text-xs font-bold text-[#2A6B4F] dark:text-[#8CC3A2]">
                {record.usedInBriefingTitle}
              </div>
            </div>
          )}

          {/* User Removed Excerpts (if any) */}
          {record.userRemovedExcerpts && record.userRemovedExcerpts.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-medium text-[#A03D3D] dark:text-[#DC9A91] flex items-center gap-1.5">
                <Scissors className="w-4 h-4 text-[#A03D3D]" />
                {language === 'vi' ? 'Đoạn đã trích xóa bởi người dùng:' : 'User Removed Excerpts:'}
              </h3>
              <ul className="space-y-1">
                {record.userRemovedExcerpts.map((excerpt, idx) => (
                  <li
                    key={idx}
                    className="p-2.5 bg-[#F9DEDE] dark:bg-[#0F1F38] border border-[#F0D8D3] dark:border-[#1E2E4A] rounded-lg text-xs text-[#A03D3D] dark:text-[#DC9A91] italic"
                  >
                    "{excerpt}"
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-[#E4EAF6] dark:border-[#1E2E4A] bg-[#EDF2FB] dark:bg-[#0F1F38] flex items-center justify-between gap-3">
          <button
            onClick={() => {
              onClose();
              onOpenRedactModal(record);
            }}
            className="px-3.5 py-2 bg-white dark:bg-[#122038] border border-[#E4EAF6] dark:border-[#1E2E4A] text-[#0F1F38] dark:text-[#E2E8F0] rounded-xl font-bold text-xs hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] transition-colors flex items-center gap-2"
          >
            <Scissors className="w-4 h-4 text-[#2563A6]" />
            {t.dataPrivacy.activity.editRetainedContent}
          </button>

          <button
            onClick={() => {
              onDeleteRecord(record.id);
              onClose();
            }}
            className="px-3.5 py-2 bg-[#F9DEDE] dark:bg-[#0F1F38] text-[#A03D3D] dark:text-[#DC9A91] border border-[#F0D8D3] dark:border-[#1E2E4A] rounded-xl font-bold text-xs hover:bg-[#F0D8D3] transition-colors flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            {t.dataPrivacy.activity.deleteRecord}
          </button>
        </div>
      </div>
    </div>
  );
};
