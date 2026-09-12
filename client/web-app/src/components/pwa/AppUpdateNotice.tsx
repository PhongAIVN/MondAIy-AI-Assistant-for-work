import type { FC } from 'react';
import { useEffect } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { watchForAppUpdate } from '../../lib/appUpdateNotice';
import { useAppStore } from '../../stores/useAppStore';

/** Hiện toast ngắn khi team đã phát hành vỏ app mới. */
export const AppUpdateNotice: FC = () => {
  const addToast = useAppStore((state) => state.addToast);
  const { t } = useTranslation();

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return undefined;

    return watchForAppUpdate(navigator.serviceWorker, () => {
      addToast({
        type: 'info',
        title: t.appUpdate.title,
        message: t.appUpdate.message,
      });
    });
  }, [addToast, t.appUpdate]);

  return null;
};
