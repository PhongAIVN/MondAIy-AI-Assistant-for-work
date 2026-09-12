import { useReducedMotion } from 'motion/react';
import { usePreferencesStore } from '../stores/usePreferencesStore';

/** Bật motion khi user chưa tắt và OS không yêu cầu giảm chuyển động. */
export function useMotionEnabled(): boolean {
  const reduceMotionPref = usePreferencesStore((s) => s.accessibility.reduceMotion);
  const systemReduce = useReducedMotion();
  return !reduceMotionPref && systemReduce !== true;
}
