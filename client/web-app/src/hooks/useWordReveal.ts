import { useLayoutEffect, useMemo, useRef } from 'react';
import { gsap } from 'gsap';
import { useMotionEnabled } from './useMotionEnabled';

/**
 * Tách text thành từng từ, morph vào (blur+fade+trượt) so le lúc mount —
 * dùng cho tiêu đề quan trọng lúc trang load, không phải scroll-trigger.
 * motionEnabled false thì chữ hiện đủ ngay, không animate.
 */
export function useWordReveal<T extends HTMLElement>(text: string) {
  const containerRef = useRef<T>(null);
  const words = useMemo(() => text.split(' '), [text]);
  const motionEnabled = useMotionEnabled();

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container || !motionEnabled) return;

    const spans = container.querySelectorAll<HTMLElement>('[data-word]');
    const ctx = gsap.context(() => {
      gsap.fromTo(
        spans,
        { opacity: 0, y: 16, filter: 'blur(6px)' },
        {
          opacity: 1,
          y: 0,
          filter: 'blur(0px)',
          duration: 0.5,
          stagger: 0.05,
          ease: 'power2.out',
          delay: 0.08,
        },
      );
    }, container);

    return () => ctx.revert();
  }, [motionEnabled, words]);

  return { containerRef, words };
}
