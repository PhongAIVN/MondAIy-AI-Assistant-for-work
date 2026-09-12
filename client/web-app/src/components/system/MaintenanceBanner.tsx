import React, { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { getBackendStatus, subscribeBackendStatus } from '../../lib/backendStatus';
import { probeBackendReadiness } from '../../lib/apiClient';
import { useTranslation } from '../../i18n/useTranslation';

/** Nhịp tự dò lại khi đang hỏng. Đủ thưa để không quật thêm một backend đang yếu. */
const RETRY_INTERVAL_MS = 15_000;

/**
 * Báo cho người dùng biết hệ thống đang bảo trì thay vì để họ nhìn lỗi trơ.
 *
 * CHỈ gắn ở khu app và khu auth. Khu marketing (landing/blog/policy/try/help/extension)
 * không phụ thuộc backend nên phải dùng được bình thường ngay cả khi DB ngủ —
 * đó là yêu cầu rõ ràng, không phải hệ quả tình cờ.
 */
export function MaintenanceBanner(): React.ReactElement | null {
  const status = useSyncExternalStore(subscribeBackendStatus, getBackendStatus, getBackendStatus);
  const { t } = useTranslation();
  const [checking, setChecking] = useState(false);

  const recheck = useCallback(async () => {
    setChecking(true);
    try {
      await probeBackendReadiness();
    } finally {
      setChecking(false);
    }
  }, []);

  // Dò một lần lúc vào app: nếu hạ tầng đã hỏng từ trước, người dùng phải biết ngay
  // chứ không phải sau khi bấm vào thứ gì đó và nhận lỗi khó hiểu.
  useEffect(() => {
    void probeBackendReadiness();
  }, []);

  useEffect(() => {
    if (status === 'ok') return;
    const timer = globalThis.setInterval(() => {
      void probeBackendReadiness();
    }, RETRY_INTERVAL_MS);
    return () => globalThis.clearInterval(timer);
  }, [status]);

  if (status === 'ok') return null;

  const message = status === 'maintenance' ? t.maintenance.description : t.maintenance.unreachable;

  // Overlay cố định, KHÔNG chèn vào cây layout: root của AppShell khoá h-[100dvh]
  // overflow-hidden và là flex-row; thêm một hàng vào đó sẽ đẩy nội dung vượt viewport
  // và làm trôi composer ở đáy hội thoại.
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 top-0 z-[60] bg-amber-500/95 px-4 py-2 text-sm text-amber-950 shadow-md backdrop-blur"
    >
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
        <span>
          <strong className="font-semibold">{t.maintenance.title}</strong>{' '}
          <span className="opacity-90">{message}</span>
        </span>
        <button
          type="button"
          onClick={() => void recheck()}
          disabled={checking}
          className="shrink-0 rounded-md border border-amber-500/50 px-3 py-1 font-medium hover:bg-amber-500/20 disabled:opacity-60"
        >
          {checking ? t.maintenance.retrying : t.maintenance.retry}
        </button>
      </div>
    </div>
  );
}
