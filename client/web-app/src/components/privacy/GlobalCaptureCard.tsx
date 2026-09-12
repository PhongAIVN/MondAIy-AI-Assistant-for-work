import React, { useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { useAppStore } from '../../stores/useAppStore';
import { GlobalPauseModal } from './GlobalPauseModal';
import { PauseCircle, PlayCircle } from 'lucide-react';

export const GlobalCaptureCard: React.FC = () => {
  const { t } = useTranslation();
  const { globalCaptureStatus, setGlobalCaptureStatus } = useDataPrivacyStore();
  const { addToast } = useAppStore();
  const [isPauseModalOpen, setIsPauseModalOpen] = useState(false);

  const handleToggle = () => {
    if (globalCaptureStatus === 'active') {
      setIsPauseModalOpen(true);
    } else {
      setGlobalCaptureStatus('active');
      addToast({
        type: 'success',
        title: 'Capture Resumed',
        message: t.dataPrivacy.globalCapture.toastResumed,
      });
    }
  };

  const handleConfirmPause = () => {
    setGlobalCaptureStatus('paused');
    addToast({
      type: 'info',
      title: 'Capture Paused',
      message: t.dataPrivacy.globalCapture.toastPaused,
    });
  };

  const isActive = globalCaptureStatus === 'active';

  return (
    <>
      <div className="bg-[var(--color-surface)] p-5 rounded-2xl border border-dashed border-[var(--color-border)] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-bold text-[var(--color-text-primary)] font-heading">
                {t.dataPrivacy.globalCapture.title}
              </h2>
              <span
                className={`text-[10px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                  isActive
                    ? 'bg-[#DFF0E6] dark:bg-[#0F1F38] text-[#2A6B4F] dark:text-[#8CC3A2] border-[#C4DDCB] dark:border-[#1E2E4A]'
                    : 'bg-[#F6EEDA] dark:bg-[#0F1F38] text-[#8A5712] dark:text-[#D7B270] border-[#D7B270] dark:border-[#1E2E4A]'
                }`}
              >
                {isActive
                  ? t.dataPrivacy.globalCapture.statusActive
                  : t.dataPrivacy.globalCapture.statusPaused}
              </span>
            </div>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1">
              {isActive
                ? t.dataPrivacy.globalCapture.activeDesc
                : t.dataPrivacy.globalCapture.pausedDesc}
            </p>
            {isActive && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                {t.dataPrivacy.globalCapture.pauseAllHint}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={handleToggle}
            className={`px-3.5 py-2 rounded-xl font-bold text-xs transition-all shrink-0 flex items-center gap-2 border ${
              isActive
                ? 'bg-transparent border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-muted)] hover:text-[#8A5712]'
                : 'bg-[var(--color-surface-muted)] border-[var(--color-border)] text-[var(--color-text-primary)] hover:border-[var(--color-border-strong)]'
            }`}
          >
            {isActive ? <PauseCircle className="w-4 h-4" /> : <PlayCircle className="w-4 h-4" />}
            {isActive
              ? t.dataPrivacy.globalCapture.pauseAll
              : t.dataPrivacy.globalCapture.resumeAll}
          </button>
        </div>
      </div>

      <GlobalPauseModal
        isOpen={isPauseModalOpen}
        onClose={() => setIsPauseModalOpen(false)}
        onConfirm={handleConfirmPause}
      />
    </>
  );
};
