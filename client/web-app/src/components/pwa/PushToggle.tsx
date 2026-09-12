// Bật/tắt thông báo đẩy của trình duyệt trên đúng thiết bị này.
//
// "Trên đúng thiết bị này" là điều quan trọng nhất phải nói với người dùng:
// đăng ký push gắn với một trình duyệt trên một máy, không theo tài khoản. Bật
// ở máy tính không có nghĩa là điện thoại cũng nhận, và ngược lại.
//
// Bốn lý do khiến không bật được là bốn tình huống khác nhau, cần bốn câu khác
// nhau. Gộp hết thành "không bật được" là bỏ mặc người dùng tự đoán.

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Smartphone } from 'lucide-react';

import { Toggle } from '../ui/Toggle';
import { disablePush, enablePush, readPushStatus, type PushStatus } from '../../lib/pushApi';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

/** iOS chỉ cho phép push khi web app đã được thêm vào màn hình chính. */
const isIos = (): boolean => /iPad|iPhone|iPod/.test(navigator.userAgent);

/** Đang chạy dạng app đã cài (không còn thanh địa chỉ trình duyệt). */
const isStandalone = (): boolean =>
  window.matchMedia?.('(display-mode: standalone)').matches ||
  (navigator as { standalone?: boolean }).standalone === true;

export const PushToggle: React.FC = () => {
  const accessToken = useAuthStore((state) => state.accessToken);
  const { t } = useTranslation();

  const [status, setStatus] = useState<PushStatus | null>(null);
  const [dangDoi, setDangDoi] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const napTrangThai = useCallback(async () => {
    setStatus(await readPushStatus());
  }, []);

  useEffect(() => {
    void napTrangThai();
  }, [napTrangThai]);

  const doiTrangThai = async (bat: boolean) => {
    if (!accessToken) return;
    setDangDoi(true);
    setLoi(null);
    try {
      if (bat) {
        const xong = await enablePush(accessToken);
        // enablePush trả false ở hai nhánh hợp lệ: người dùng từ chối quyền,
        // hoặc máy chủ chưa cấu hình VAPID. Phân biệt bằng quyền hiện tại.
        if (!xong) {
          setLoi(
            Notification.permission === 'denied'
              ? t.pushNotifications.blocked
              : t.pushNotifications.serverOff,
          );
        }
      } else {
        await disablePush(accessToken);
      }
    } catch {
      setLoi(t.pushNotifications.failed);
    } finally {
      await napTrangThai();
      setDangDoi(false);
    }
  };

  if (status === null) return null;

  // iOS chưa cài lên màn hình chính thì đăng ký chắc chắn thất bại. Hiện hướng
  // dẫn thay vì một cái toggle bấm vào không có tác dụng.
  const canCaiTruoc = isIos() && !isStandalone();

  return (
    <div className="p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-bold text-[var(--color-text-primary)]">{t.pushNotifications.title}</p>
          <p className="text-[11px] text-[var(--color-text-secondary)]">
            {t.pushNotifications.thisDeviceOnly}
          </p>
        </div>
        <Toggle
          checked={status.subscribed}
          disabled={!status.supported || canCaiTruoc || dangDoi}
          onChange={(checked) => void doiTrangThai(checked)}
          aria-label={t.pushNotifications.title}
        />
      </div>

      {!status.supported && (
        <p className="text-[11px] text-[var(--color-text-secondary)]">
          {t.pushNotifications.unsupported}
        </p>
      )}

      {canCaiTruoc && (
        <p className="text-[11px] text-[var(--color-text-secondary)] flex items-start gap-1.5">
          <Smartphone className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {t.pushNotifications.iosInstallFirst}
        </p>
      )}

      {loi && (
        <p role="alert" className="text-[11px] text-red-700 dark:text-red-300 flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {loi}
        </p>
      )}
    </div>
  );
};
