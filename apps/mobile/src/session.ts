import * as SecureStore from 'expo-secure-store';
import type { Tokens } from './api/client';

const SESSION_KEY = 'mondaiy.mobile.session.v1';
const ONBOARDING_KEY = 'mondaiy.mobile.onboarding.v1';
const AI_DATA_SHARING_KEY_PREFIX = 'mondaiy.mobile.ai-data-sharing.v1.';

export const readSession = async (): Promise<Tokens | null> => {
  const raw = await SecureStore.getItemAsync(SESSION_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as Tokens; } catch { return null; }
};

export const saveSession = (tokens: Tokens): Promise<void> =>
  SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(tokens));

export const clearSession = (): Promise<void> => SecureStore.deleteItemAsync(SESSION_KEY);

export const readOnboardingCompleted = async (): Promise<boolean> =>
  (await SecureStore.getItemAsync(ONBOARDING_KEY)) === 'done';

export const markOnboardingCompleted = (): Promise<void> =>
  SecureStore.setItemAsync(ONBOARDING_KEY, 'done');

const aiDataSharingKey = (userId: string) => `${AI_DATA_SHARING_KEY_PREFIX}${userId}`;

export const readAiDataSharingConsent = async (userId: string): Promise<boolean | null> => {
  const value = await SecureStore.getItemAsync(aiDataSharingKey(userId));
  if (value === null) return null;
  return value === 'allowed';
};

export const saveAiDataSharingConsent = (userId: string, allowed: boolean): Promise<void> =>
  SecureStore.setItemAsync(aiDataSharingKey(userId), allowed ? 'allowed' : 'denied');

export const clearAiDataSharingConsent = (userId: string): Promise<void> =>
  SecureStore.deleteItemAsync(aiDataSharingKey(userId));
