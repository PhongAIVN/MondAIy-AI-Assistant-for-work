import { useEffect } from 'react';
import { useAppStore } from '../stores/useAppStore';
import { useTranslation } from '../i18n/useTranslation';

export type TaskDecision = 'dismissed' | 'confirmed';

const STORAGE_KEY = 'mondaiy_task_dismissal_streak';
const DISMISS_THRESHOLD = 3;
const DECISION_EVENT = 'mondaiy:task-decision';

const readStreak = (): number => {
  try {
    return Number(sessionStorage.getItem(STORAGE_KEY)) || 0;
  } catch {
    return 0;
  }
};

const writeStreak = (value: number) => {
  try {
    sessionStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    // sessionStorage có thể bị chặn ở private mode — nhắc nhở chỉ sống trong phiên này.
  }
};

/** Ghi nhận một quyết định trên task ('dismiss'/'confirm') để nuôi chuỗi nhắc nhở. */
export const recordTaskDecision = (decision: TaskDecision) => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(DECISION_EVENT, { detail: decision }));
};

/**
 * Người dùng bỏ qua nhiều task liên tiếp (không xác nhận task nào xen giữa)
 * thì mondaiy nhắc nhở buồn kèm mascot — reset chuỗi mỗi khi nhắc hoặc mỗi
 * khi có một lần xác nhận (tín hiệu tích cực phá chuỗi).
 */
export const useTaskDismissalNudge = () => {
  const addToast = useAppStore((state) => state.addToast);
  const { t } = useTranslation();

  useEffect(() => {
    const onDecision = (event: Event) => {
      const decision = (event as CustomEvent<TaskDecision>).detail;
      if (decision === 'confirmed') {
        writeStreak(0);
        return;
      }
      const streak = readStreak() + 1;
      if (streak >= DISMISS_THRESHOLD) {
        writeStreak(0);
        addToast({
          type: 'info',
          title: t.tasksPage.dismissalNudgeTitle,
          message: t.tasksPage.dismissalNudgeMsg,
          mascotGif: '/loadinggif1.gif',
        });
        return;
      }
      writeStreak(streak);
    };
    window.addEventListener(DECISION_EVENT, onDecision);
    return () => window.removeEventListener(DECISION_EVENT, onDecision);
  }, [addToast, t.tasksPage.dismissalNudgeTitle, t.tasksPage.dismissalNudgeMsg]);
};
