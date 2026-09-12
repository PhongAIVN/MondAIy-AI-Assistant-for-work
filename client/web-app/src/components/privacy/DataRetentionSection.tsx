import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { HardDrive } from 'lucide-react';

export const DataRetentionSection: React.FC = () => {
  const { t, language } = useTranslation();

  return (
    <div className="bg-[var(--color-surface-muted)] p-6 rounded-2xl border border-[var(--color-border)] shadow-2xs space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--color-accent-soft)] flex items-center justify-center text-[var(--color-primary)]">
          <HardDrive className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-base font-extrabold text-[var(--color-text-primary)] font-heading">
            {t.dataPrivacy.retentionTransparency.title}
          </h2>
          <p className="text-xs text-[var(--color-text-secondary)]">
            {language === 'vi'
              ? 'Quy định minh bạch về thời gian lưu trữ và xóa dữ liệu trong hệ thống'
              : 'Transparent policy regarding storage lifecycle and deletion timelines'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        <div className="p-3.5 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] space-y-1">
          <span className="font-bold text-[var(--color-text-primary)] block">
            {t.dataPrivacy.retentionTransparency.capturedSourceInfo}
          </span>
          <p className="text-[var(--color-text-secondary)]">
            {t.dataPrivacy.retentionTransparency.capturedSourceRule}
          </p>
        </div>

        <div className="p-3.5 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] space-y-1">
          <span className="font-bold text-[var(--color-text-primary)] block">
            {t.dataPrivacy.retentionTransparency.confirmedMemories}
          </span>
          <p className="text-[var(--color-text-secondary)]">
            {t.dataPrivacy.retentionTransparency.confirmedMemoriesRule}
          </p>
        </div>

        <div className="p-3.5 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] space-y-1">
          <span className="font-bold text-[var(--color-text-primary)] block">
            {t.dataPrivacy.retentionTransparency.pendingCandidates}
          </span>
          <p className="text-[var(--color-text-secondary)]">
            {t.dataPrivacy.retentionTransparency.pendingCandidatesRule}
          </p>
        </div>

        <div className="p-3.5 bg-[#F9DEDE] dark:bg-[#0F1F38] rounded-xl border border-[#F0D8D3] dark:border-[#1E2E4A] space-y-1">
          <span className="font-bold text-[#A03D3D] dark:text-[#DC9A91] block">
            {t.dataPrivacy.retentionTransparency.deletedInfo}
          </span>
          <p className="text-[var(--color-text-secondary)]">
            {t.dataPrivacy.retentionTransparency.deletedInfoRule}
          </p>
        </div>
      </div>
    </div>
  );
};
