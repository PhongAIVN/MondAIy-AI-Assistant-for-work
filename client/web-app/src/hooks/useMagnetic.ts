import { useLayoutEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { useMotionEnabled } from './useMotionEnabled';

/**
 * Nút/CTA trôi nhẹ theo con trỏ khi hover (magnetic), dùng quickTo cho mượt
 * mà không tốn tính toán spring vật lý. Tắt hẳn khi useMotionEnabled() false.
 */
export function useMagnetic<T extends HTMLElement>(strength = 0.35) {
  const ref = useRef<T>(null);
  const motionEnabled = useMotionEnabled();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !motionEnabled) return;

    const xTo = gsap.quickTo(el, 'x', { duration: 0.35, ease: 'power3.out' });
    const yTo = gsap.quickTo(el, 'y', { duration: 0.35, ease: 'power3.out' });

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      xTo((e.clientX - rect.left - rect.width / 2) * strength);
      yTo((e.clientY - rect.top - rect.height / 2) * strength);
    };
    const onLeave = () => {
      xTo(0);
      yTo(0);
    };

    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);

    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [motionEnabled, strength]);

  return ref;
}
