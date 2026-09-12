import React from 'react';
import { FlaskConical } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import type { PipelineTransport } from '../../lib/pipelineApi';

export interface TransportBannerProps {
  transport: PipelineTransport | null;
  reason?: string | null;
}

/**
 * Băng cảnh báo khi màn hình đang chạy bằng fixture. Điều kiện dừng
 * Checkpoint 3 là "không mock", nên trạng thái mock phải hiện rõ trên UI chứ
 * không được lặng lẽ trông như dữ liệu thật.
 */
export const TransportBanner: React.FC<TransportBannerProps> = ({ transport, reason }) => {
  const { t } = useTranslation();
  if (transport !== 'mock') return null;

  return (
    <div
      role="status"
      className="flex items-start gap-3 p-3 rounded-xl border border-[var(--color-warning)]/35 bg-[var(--color-warning-soft)] text-[var(--color-warning)]"
    >
      <FlaskConical className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="text-xs space-y-0.5">
        <p className="font-bold font-heading">{t.pipeline.mockTitle}</p>
        <p className="font-normal text-[var(--color-text-secondary)]">{t.pipeline.mockBody}</p>
        {reason && <p className="text-[11px] text-[#5E6B7D] dark:text-[#AEB9CC]">{reason}</p>}
      </div>
    </div>
  );
};
