import { RefreshCw } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { checkAppVersion, reloadToLatest } from '../../lib/appVersion';

/**
 * Nhắc người dùng làm mới khi bản đang chạy đã cũ hơn bản trên server.
 *
 * Vì sao là banner chứ không phải màn hình chặn: khác `AppErrorBoundary`, ở đây
 * app VẪN CHẠY ĐƯỢC. Chặn cả màn hình sẽ cướp mất công việc đang dở của người
 * dùng vì một thứ chưa hỏng. Họ tự chọn thời điểm.
 *
 * Cố ý không tự reload: người dùng có thể đang gõ giữa chừng.
 */
export function AppUpdateBanner() {
  const [stale, setStale] = useState(false);
  const [reloading, setReloading] = useState(false);
  // Đã báo rồi thì thôi — kiểm lại mỗi lần focus mà cứ dựng lại banner đã bị
  // đóng là biến một lời nhắc thành một thứ phiền nhiễu.
  const dismissed = useRef(false);

  const kiemTra = useCallback(async () => {
    if (dismissed.current || stale) return;
    const result = await checkAppVersion();
    if (result.status === 'stale') setStale(true);
  }, [stale]);

  useEffect(() => {
    void kiemTra();

    // Kiểm lại khi người dùng quay lại tab. Đây đúng là lúc một tab để mở lâu
    // xuyên qua một lần deploy, và cũng là lúc họ sắp thao tác tiếp.
    const onVisible = () => {
      if (document.visibilityState === 'visible') void kiemTra();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  }, [kiemTra]);

  if (!stale) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-0 z-50 flex justify-center px-4 pb-4"
    >
      <div className="flex w-full max-w-md items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 shadow-lg">
        <RefreshCw className="h-5 w-5 shrink-0 text-[var(--color-primary)]" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">
            Đã có bản Mondaiy mới
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-text-secondary)]">
            Làm mới để tránh lỗi lạ. Bạn vẫn đăng nhập như cũ.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setReloading(true);
            void reloadToLatest();
          }}
          disabled={reloading}
          className="shrink-0 rounded-xl bg-[var(--color-primary)] px-3.5 py-2 text-sm font-semibold text-[var(--color-on-primary)] disabled:opacity-60"
        >
          {reloading ? 'Đang làm mới…' : 'Làm mới ứng dụng'}
        </button>
        <button
          type="button"
          onClick={() => {
            dismissed.current = true;
            setStale(false);
          }}
          aria-label="Để sau"
          className="shrink-0 rounded-lg px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
        >
          Để sau
        </button>
      </div>
    </div>
  );
}
