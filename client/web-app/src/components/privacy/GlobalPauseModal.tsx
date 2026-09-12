import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { X, PauseCircle } from 'lucide-react';

interface GlobalPauseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export const GlobalPauseModal: React.FC<GlobalPauseModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
}) => {
  const { t, language } = useTranslation();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-md bg-white dark:bg-[#122038] rounded-2xl shadow-2xl border border-[#E4EAF6] dark:border-[#1E2E4A] overflow-hidden flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-6 border-b border-[#E4EAF6] dark:border-[#1E2E4A] flex items-center justify-between bg-[#F6EEDA] dark:bg-[#0F1F38]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white dark:bg-[#122038] flex items-center justify-center text-[#8A5712] dark:text-[#D7B270]">
              <PauseCircle className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
              {t.dataPrivacy.globalCapture.pauseModalTitle}
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
        <div className="p-6">
          <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] leading-relaxed">
            {t.dataPrivacy.globalCapture.pauseModalDesc}
          </p>
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
            onClick={() => {
              onConfirm();
              onClose();
            }}
            className="px-5 py-2 bg-[#8A5712] text-white rounded-xl font-bold text-xs shadow-2xs hover:bg-[#6A4711] transition-colors flex items-center gap-2"
          >
            <PauseCircle className="w-4 h-4" />
            {t.dataPrivacy.globalCapture.confirmPause}
          </button>
        </div>
      </div>
    </div>
  );
};
