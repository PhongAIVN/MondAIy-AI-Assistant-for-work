import { useLayoutEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useMotionEnabled } from '../hooks/useMotionEnabled';

gsap.registerPlugin(ScrollTrigger);

const REVEAL_FROM = { opacity: 0, y: 24 };

/**
 * Fade + trượt lên khi cuộn tới, chỉ chạy 1 lần — dùng cho khối đứng một
 * mình (heading, panel...). Tắt hẳn khi useMotionEnabled() false, phần tử
 * hiện đủ ngay theo CSS mặc định (không set style gì).
 */
export function useRevealOnScroll<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const motionEnabled = useMotionEnabled();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !motionEnabled) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(el, REVEAL_FROM, {
        opacity: 1,
        y: 0,
        duration: 0.5,
        ease: 'power3.out',
        scrollTrigger: { trigger: el, start: 'top 85%', once: true },
      });
    });

    return () => ctx.revert();
  }, [motionEnabled]);

  return ref;
}

type RevealGroupOptions = {
  /** Phần tử con cần reveal — mặc định mọi con trực tiếp của container. */
  itemSelector?: string;
  /** Thêm hover lift + scale nhẹ cho từng item — dùng cho card thật (có ảnh/link). */
  hoverLift?: boolean;
  /** Thêm nghiêng 3D rất nhẹ theo vị trí con trỏ trong item — chỉ dùng cho feature card thật sự. */
  tilt?: boolean;
};

const TILT_MAX_DEG = 5;

/**
 * Container fade + trượt-lên-so-le cho các con trực tiếp khi cuộn tới, chỉ
 * chạy 1 lần. `hoverLift`/`tilt` gắn thêm tween hover cho từng item,
 * cleanup listener đầy đủ lúc unmount.
 */
export function useRevealGroup<T extends HTMLElement>(options: RevealGroupOptions = {}) {
  const { itemSelector = ':scope > *', hoverLift = false, tilt = false } = options;
  const ref = useRef<T>(null);
  const motionEnabled = useMotionEnabled();

  useLayoutEffect(() => {
    const container = ref.current;
    if (!container || !motionEnabled) return;

    const items = Array.from(container.querySelectorAll<HTMLElement>(itemSelector));
    if (items.length === 0) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(items, REVEAL_FROM, {
        opacity: 1,
        y: 0,
        duration: 0.5,
        ease: 'power3.out',
        stagger: 0.1,
        scrollTrigger: { trigger: container, start: 'top 85%', once: true },
      });
    });

    const cleanups: Array<() => void> = [];
    if (hoverLift || tilt) {
      for (const item of items) {
        if (tilt) gsap.set(item, { transformPerspective: 800 });

        const enter = () => {
          if (hoverLift) gsap.to(item, { y: -6, scale: 1.015, duration: 0.3, ease: 'power2.out' });
        };
        const leave = () => {
          gsap.to(item, { y: 0, scale: 1, rotateX: 0, rotateY: 0, duration: 0.3, ease: 'power2.out' });
        };
        const move = (e: MouseEvent) => {
          if (!tilt) return;
          const rect = item.getBoundingClientRect();
          const px = (e.clientX - rect.left) / rect.width - 0.5;
          const py = (e.clientY - rect.top) / rect.height - 0.5;
          gsap.to(item, {
            rotateX: -py * TILT_MAX_DEG * 2,
            rotateY: px * TILT_MAX_DEG * 2,
            duration: 0.4,
            ease: 'power2.out',
          });
        };

        item.addEventListener('mouseenter', enter);
        item.addEventListener('mouseleave', leave);
        item.addEventListener('mousemove', move);
        cleanups.push(() => {
          item.removeEventListener('mouseenter', enter);
          item.removeEventListener('mouseleave', leave);
          item.removeEventListener('mousemove', move);
        });
      }
    }

    return () => {
      ctx.revert();
      cleanups.forEach((fn) => fn());
    };
  }, [motionEnabled, itemSelector, hoverLift, tilt]);

  return ref;
}
