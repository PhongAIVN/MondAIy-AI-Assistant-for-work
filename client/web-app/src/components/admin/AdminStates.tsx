// Trạng thái rỗng/đang tải/lỗi cho các trang admin.
//
// Tách riêng khỏi ui/LoadingState và ui/ErrorState vì hai cái đó viết cứng chữ
// về "briefing" và bảng màu sáng của workspace người dùng, không dùng lại được
// trong khung admin tối.

import React from 'react';
import { AlertOctagon, Inbox, RefreshCw } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

const KHUNG =
  'rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] p-8 flex flex-col items-center justify-center text-center gap-2';

export const AdminLoading: React.FC<{ label?: string }> = ({ label }) => {
  const { t } = useTranslation();
  return (
    <div className={KHUNG} role="status" aria-live="polite">
      <img src="/loadinggif2.gif" alt="" aria-hidden className="w-12 h-12" />
      <p className="text-xs font-semibold text-[#5A6A85] dark:text-[#8B98AB]">
        {label ?? t.auth.loadingText}
      </p>
    </div>
  );
};

export const AdminError: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => {
  const { t } = useTranslation();
  return (
    <div className={KHUNG} role="alert">
      <AlertOctagon className="w-6 h-6 text-rose-600 dark:text-rose-400" />
      <p className="text-sm font-bold text-[#0F1F38] dark:text-white">{t.admin.errorTitle}</p>
      <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB] max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] text-xs font-semibold text-[#2563A6] hover:bg-[#EDF2FB] dark:hover:bg-[#0A1628] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> {t.admin.retry}
        </button>
      )}
    </div>
  );
};

export const AdminEmpty: React.FC<{ title: string; hint?: string }> = ({ title, hint }) => (
  <div className={KHUNG}>
    <Inbox className="w-6 h-6 text-[#5A6A85]" />
    <p className="text-sm font-bold text-[#0F1F38] dark:text-white">{title}</p>
    {hint && <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB] max-w-md">{hint}</p>}
  </div>
);

export const AdminMockBanner: React.FC<{ lyDo: string }> = ({ lyDo }) => {
  const { t } = useTranslation();
  return (
    <div
      className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 flex items-start gap-3"
      role="note"
    >
      <AlertOctagon className="w-4 h-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
      <p className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
        <strong>{t.admin.mockBannerLead}</strong> {lyDo} {t.admin.mockBannerTail}
      </p>
    </div>
  );
};
