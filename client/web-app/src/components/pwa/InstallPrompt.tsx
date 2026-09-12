// Lời nhắc cài mondaiy lên màn hình chính.
//
// Ba đường đi khác nhau, vì trình duyệt không thống nhất:
//   Android/desktop — bắt `beforeinstallprompt`, bấm nút là gọi prompt() thật
//   iOS Safari      — Apple không phát sự kiện đó, chỉ còn cách chỉ đường thủ công
//   đã standalone   — cài rồi, không hiện gì
//
// Người dùng đã đóng thì im luôn: nhắc lại một thứ vừa bị từ chối là phiền,
// nên lựa chọn được ghi vào localStorage giống cách usePreferencesStore lưu.

import React, { useCallback, useEffect, useState } from 'react';
import { Download, Share, X } from 'lucide-react';

import { useTranslation } from '../../i18n/useTranslation';

/** Khoá localStorage nhớ việc người dùng đã đóng lời nhắc cài đặt. */
export const PWA_INSTALL_DISMISSED_KEY = 'mondaiy.pwaInstallDismissed';

/**
 * Sự kiện `beforeinstallprompt` chưa có trong lib DOM chuẩn nên phải tự khai.
 * `prompt()` mở hộp thoại cài của trình duyệt, `userChoice` cho biết kết quả.
 */
type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
};

/**
 * Đang chạy dạng app rời trình duyệt hay chưa.
 * Chrome/Android báo qua media query display-mode, iOS báo qua navigator.standalone.
 */
const dangChayStandalone = (): boolean => {
  if (typeof window === 'undefined') return false;
  const theoDisplayMode = window.matchMedia?.('(display-mode: standalone)').matches ?? false;
  const theoIOS = (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
  return theoDisplayMode || theoIOS;
};

/**
 * Nhận diện iOS. iPadOS 13+ khai user agent giống macOS nên phải kiểm thêm
 * màn cảm ứng — nếu không, iPad sẽ không bao giờ thấy hướng dẫn thủ công.
 */
const laIOS = (): boolean => {
  if (typeof window === 'undefined') return false;
  const ua = window.navigator.userAgent;
  if (/iPad|iPhone|iPod/.test(ua)) return true;
  return ua.includes('Macintosh') && window.navigator.maxTouchPoints > 1;
};

/**
 * Chỉ Safari trên iOS mới thêm được vào màn hình chính. Chrome/Firefox/Edge
 * trên iOS đều là WebKit nhưng chèn token riêng (CriOS/FxiOS/EdgiOS) và không
 * có mục "Add to Home Screen", nên hướng dẫn ở đó là chỉ sai đường.
 */
const laSafariTrenIOS = (): boolean => {
  if (!laIOS()) return false;
  const ua = window.navigator.userAgent;
  return !/CriOS|FxiOS|EdgiOS|OPiOS|Mercury/.test(ua);
};

/** Đọc cờ đã đóng; localStorage hỏng hoặc bị chặn thì coi như chưa đóng. */
const daDong = (): boolean => {
  try {
    return localStorage.getItem(PWA_INSTALL_DISMISSED_KEY) === 'true';
  } catch {
    return false;
  }
};

/** Ghi cờ đã đóng; nuốt lỗi quota / chế độ riêng tư như phần còn lại của app. */
const ghiNhoDaDong = (): void => {
  try {
    localStorage.setItem(PWA_INSTALL_DISMISSED_KEY, 'true');
  } catch {
    /* ignore quota / private mode */
  }
};

export const InstallPrompt: React.FC = () => {
  const { t } = useTranslation();

  // Giữ chính sự kiện lại: prompt() chỉ gọi được trên đúng đối tượng đã bắt.
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState<boolean>(daDong);
  const [standalone, setStandalone] = useState<boolean>(dangChayStandalone);
  const [iosHint] = useState<boolean>(() => laSafariTrenIOS() && !dangChayStandalone());

  useEffect(() => {
    const batSuKien = (event: Event) => {
      // Chặn banner mặc định của trình duyệt để tự quyết thời điểm hiện.
      event.preventDefault();
      setInstallEvent(event as BeforeInstallPromptEvent);
    };
    // Cài xong thì gỡ lời nhắc ngay, không đợi tải lại trang.
    const daCaiXong = () => {
      setInstallEvent(null);
      setStandalone(true);
    };

    window.addEventListener('beforeinstallprompt', batSuKien);
    window.addEventListener('appinstalled', daCaiXong);
    return () => {
      window.removeEventListener('beforeinstallprompt', batSuKien);
      window.removeEventListener('appinstalled', daCaiXong);
    };
  }, []);

  /** Mở hộp thoại cài của trình duyệt rồi bỏ sự kiện đi — mỗi sự kiện dùng một lần. */
  const cai = useCallback(async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    await installEvent.userChoice;
    setInstallEvent(null);
  }, [installEvent]);

  /** Đóng và nhớ luôn, để lần mở app sau không hỏi lại. */
  const dong = useCallback(() => {
    ghiNhoDaDong();
    setDismissed(true);
  }, []);

  if (standalone || dismissed) return null;
  if (!installEvent && !iosHint) return null;

  return (
    <div
      role="dialog"
      aria-label={t.pwaInstall.title}
      className="fixed inset-x-3 bottom-3 z-[100] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 shadow-lg sm:left-auto sm:right-4 sm:bottom-4 sm:w-80"
      style={{ marginBottom: 'env(safe-area-inset-bottom)' }}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--color-accent-soft)]">
          {iosHint && !installEvent ? (
            <Share className="h-4 w-4 text-[var(--color-primary)]" />
          ) : (
            <Download className="h-4 w-4 text-[var(--color-primary)]" />
          )}
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-heading text-xs font-extrabold text-[var(--color-text-primary)]">
            {installEvent ? t.pwaInstall.title : t.pwaInstall.iosTitle}
          </p>

          {installEvent ? (
            <p className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              {t.pwaInstall.body}
            </p>
          ) : (
            // iOS không cho gọi cài bằng script — chỉ còn cách nói rõ ba bước.
            <ol className="list-decimal space-y-0.5 pl-4 text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
              <li>{t.pwaInstall.iosStepShare}</li>
              <li>{t.pwaInstall.iosStepAdd}</li>
              <li>{t.pwaInstall.iosStepConfirm}</li>
            </ol>
          )}

          {installEvent && (
            <div className="flex items-center gap-2 pt-1.5">
              <button
                type="button"
                onClick={() => void cai()}
                className="cursor-pointer rounded-xl bg-[var(--color-primary)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-on-primary)] transition-colors hover:bg-[var(--color-primary-hover)]"
              >
                {t.pwaInstall.installAction}
              </button>
              <button
                type="button"
                onClick={dong}
                className="app-control cursor-pointer rounded-xl px-3 py-1.5 text-[11px] font-semibold"
              >
                {t.pwaInstall.dismissAction}
              </button>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={dong}
          aria-label={t.pwaInstall.dismissLabel}
          className="app-icon-button shrink-0 rounded-lg p-1"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
