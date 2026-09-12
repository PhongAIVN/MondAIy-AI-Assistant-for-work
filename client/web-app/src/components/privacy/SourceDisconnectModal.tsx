import React, { useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { localizeSourceName } from '../../i18n/privacyCatalog';
import { type ConnectedSourceAccess } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { X, Unplug, Trash2 } from 'lucide-react';

interface SourceDisconnectModalProps {
  source: ConnectedSourceAccess | null;
  isOpen: boolean;
  onClose: () => void;
}

export const SourceDisconnectModal: React.FC<SourceDisconnectModalProps> = ({
  source,
  isOpen,
  onClose,
}) => {
  const { t, language } = useTranslation();
  const { disconnectSource } = useDataPrivacyStore();
  const [deleteData, setDeleteData] = useState(false);

  if (!isOpen || !source) return null;

  const sourceName = localizeSourceName(source.id, source.name, language);

  const handleDisconnect = () => {
    disconnectSource(source.id, deleteData);
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
            <div className="w-10 h-10 rounded-xl bg-[#F9DEDE] dark:bg-[#1A2A42] flex items-center justify-center text-[#A03D3D] dark:text-[#DC9A91]">
              <Unplug className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
              {t.dataPrivacy.disconnectModal.title.replace('{source}', sourceName)}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC]">
            {language === 'vi'
              ? 'Vui lòng chọn cách xử lý dữ liệu đã được thu thập trước đó từ nguồn này:'
              : 'Please choose how to handle previously captured data from this source:'}
          </p>

          <div className="space-y-3">
            {/* Option A: Keep Data */}
            <label
              onClick={() => setDeleteData(false)}
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                !deleteData
                  ? 'border-[#0F1F38] dark:border-[#2563A6] bg-[#E1EBFA] dark:bg-[#0F1F38] ring-1 ring-[#0F1F38]'
                  : 'border-[#E4EAF6] dark:border-[#1E2E4A] bg-white dark:bg-[#122038] hover:border-[#0F1F38]'
              }`}
            >
              <input
                type="radio"
                name="disconnectChoice"
                checked={!deleteData}
                onChange={() => setDeleteData(false)}
                className="mt-1 sr-only"
              />
              <div className="space-y-1">
                <span className="text-sm font-bold text-[#0F1F38] dark:text-[#E2E8F0] block">
                  {t.dataPrivacy.disconnectModal.optionA}
                </span>
                <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC]">
                  {t.dataPrivacy.disconnectModal.optionADesc}
                </p>
              </div>
            </label>

            {/* Option B: Delete Data */}
            <label
              onClick={() => setDeleteData(true)}
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                deleteData
                  ? 'border-[#A03D3D] dark:border-[#DC9A91] bg-[#F9DEDE] dark:bg-[#0F1F38] ring-1 ring-[#A03D3D]'
                  : 'border-[#E4EAF6] dark:border-[#1E2E4A] bg-white dark:bg-[#122038] hover:border-[#A03D3D]'
              }`}
            >
              <input
                type="radio"
                name="disconnectChoice"
                checked={deleteData}
                onChange={() => setDeleteData(true)}
                className="mt-1 sr-only"
              />
              <div className="space-y-1">
                <span className="text-sm font-bold text-[#A03D3D] dark:text-[#DC9A91] block">
                  {t.dataPrivacy.disconnectModal.optionB}
                </span>
                <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC]">
                  {t.dataPrivacy.disconnectModal.optionBDesc.replace('{source}', sourceName)}
                </p>
              </div>
            </label>
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
            onClick={handleDisconnect}
            className={`px-5 py-2 rounded-xl font-bold text-xs shadow-2xs transition-colors flex items-center gap-2 text-white ${
              deleteData
                ? 'bg-[#A03D3D] hover:bg-[#8A3434]'
                : 'bg-[#0F1F38] dark:bg-[#2563A6] hover:bg-[#1E4E85]'
            }`}
          >
            {deleteData ? <Trash2 className="w-4 h-4" /> : <Unplug className="w-4 h-4" />}
            {language === 'vi' ? 'Ngắt kết nối' : 'Disconnect Source'}
          </button>
        </div>
      </div>
    </div>
  );
};
