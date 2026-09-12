import { useCallback, useEffect, useState } from 'react';
import { submitAppRating, type RatingTrigger } from '../lib/ratingApi';
import { useAuthStore } from '../stores/useAuthStore';
import { useAppStore } from '../stores/useAppStore';
import { useTranslation } from '../i18n/useTranslation';

export type MeaningfulAction =
  | 'gmail_summary_completed'
  | 'calendar_summary_completed'
  | 'task_confirmed'
  | 'task_dismissed'
  | 'grounded_answer_completed'
  | 'approved_external_action';

type RatingPrompt = {
  trigger: RatingTrigger;
  actionCount: number;
  durationSeconds: number;
};

type SessionState = {
  id: string;
  startedAt: number;
  actionCount: number;
  prompted: boolean;
};

const STORAGE_KEY = 'mondaiy_product_rating_session';
const ACTION_THRESHOLD = 3;
const ACTION_EVENT = 'mondaiy:meaningful-action';
const RATING_REQUEST_EVENT = 'mondaiy:request-product-rating';

const getSession = (): SessionState => {
  const existing = sessionStorage.getItem(STORAGE_KEY);
  if (existing) {
    try { return JSON.parse(existing) as SessionState; } catch { /* recreate */ }
  }
  const fresh: SessionState = {
    id: `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    startedAt: Date.now(),
    actionCount: 0,
    prompted: false,
  };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(fresh));
  return fresh;
};

const saveSession = (session: SessionState) => sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));

const evaluatePrompt = (trigger: RatingTrigger, increment: boolean): RatingPrompt | null => {
  const session = getSession();
  if (increment) session.actionCount += 1;
  const durationSeconds = Math.floor((Date.now() - session.startedAt) / 1000);
  const eligible = session.actionCount >= ACTION_THRESHOLD;
  if (eligible && !session.prompted) {
    session.prompted = true;
    saveSession(session);
    return { trigger, actionCount: session.actionCount, durationSeconds };
  }
  saveSession(session);
  return null;
};

export const recordMeaningfulAction = (action: MeaningfulAction) => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(ACTION_EVENT, { detail: action }));
};

export const requestProductRating = () => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(RATING_REQUEST_EVENT));
};

export const useProductRating = () => {
  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);
  const addToast = useAppStore((state) => state.addToast);
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState<RatingPrompt | null>(null);

  useEffect(() => {
    if (!accessToken || !user || user.role === 'admin' || typeof window === 'undefined') {
      setPrompt(null);
      return undefined;
    }
    const onAction = () => {
      const nextPrompt = evaluatePrompt('action_count', true);
      if (nextPrompt) setPrompt(nextPrompt);
    };
    window.addEventListener(ACTION_EVENT, onAction);
    return () => window.removeEventListener(ACTION_EVENT, onAction);
  }, [accessToken, user]);

  useEffect(() => {
    if (!accessToken || !user || typeof window === 'undefined') {
      return undefined;
    }
    const onRequest = () => {
      const session = getSession();
      session.prompted = true;
      saveSession(session);
      setPrompt({
        trigger: 'manual',
        actionCount: session.actionCount,
        durationSeconds: Math.floor((Date.now() - session.startedAt) / 1000),
      });
    };
    window.addEventListener(RATING_REQUEST_EVENT, onRequest);
    return () => window.removeEventListener(RATING_REQUEST_EVENT, onRequest);
  }, [accessToken, user]);

  const closePrompt = useCallback(() => {
    const session = getSession();
    saveSession({
      ...session,
      startedAt: Date.now(),
      actionCount: 0,
      prompted: false,
    });
    setPrompt(null);
  }, []);

  const submit = useCallback(async (rating: number, feedback: string) => {
    if (!accessToken || !prompt) return;
    if (!feedback.trim()) {
      throw new Error(t.productRating.minLengthError);
    }
    const session = getSession();
    const reward = await submitAppRating(accessToken, {
      rating,
      feedback: feedback.trim(),
      trigger: prompt.trigger,
      sessionId: session.id,
      meaningfulActionCount: prompt.actionCount,
      sessionDurationSeconds: prompt.durationSeconds,
    });
    addToast({
      type: 'success',
      title: t.productRating.rewardToastTitle.replace('{count}', String(reward.bonusQuestionsAwarded)),
      message: t.productRating.rewardToastMessage.replace('{count}', String(reward.questionsRemaining)),
    });
    // A submitted rating starts a fresh prompt cycle.
    saveSession({
      ...session,
      startedAt: Date.now(),
      actionCount: 0,
      prompted: false,
    });
    setPrompt(null);
  }, [accessToken, addToast, prompt, t.productRating]);

  return { prompt, submit, closePrompt };
};
