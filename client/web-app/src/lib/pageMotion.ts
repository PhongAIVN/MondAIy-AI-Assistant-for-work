import { animate, stagger } from 'motion';

/**
 * Chọn các phần tử sẽ hiện lần lượt khi vào trang.
 * Đi xuyên qua wrapper đơn (page root) để lấy các section thật.
 * Dùng shape tối giản để test chạy được cả trong môi trường Node (không DOM).
 */
export interface StaggerElement {
  hidden?: boolean | string;
  tagName: string;
  children: ArrayLike<StaggerElement>;
}

export function collectStaggerTargets(root: StaggerElement, max = 8): StaggerElement[] {
  const pick = (parent: StaggerElement): StaggerElement[] =>
    Array.from(parent.children).filter(
      (el) =>
        !el.hidden &&
        el.tagName !== 'SCRIPT' &&
        el.tagName !== 'STYLE' &&
        el.tagName !== 'LINK',
    );

  let items = pick(root);
  let depth = 0;
  while (items.length === 1 && items[0].children.length >= 2 && depth < 3) {
    items = pick(items[0]);
    depth += 1;
  }

  return items.slice(0, max);
}

/** Thời gian motion trang — chậm hơn để dễ cảm nhận. */
export const PAGE_MOTION = {
  enterMs: 480,
  exitMs: 320,
  staggerDelayMs: 140,
  staggerStepMs: 100,
  staggerItemMs: 560,
  easeCss: 'cubic-bezier(0.16, 1, 0.3, 1)',
  ease: [0.16, 1, 0.3, 1] as const,
} as const;

/**
 * Từng section fade + trượt lên theo thứ tự, dùng chung engine motion với
 * page transition (thay cho WAAPI tay viết trước đây).
 * Trả về cleanup dừng animation đang chạy.
 */
export function playStaggerEnter(root: Element): () => void {
  const targets = collectStaggerTargets(root as unknown as StaggerElement) as unknown as Element[];
  if (targets.length === 0) return () => {};

  const controls = animate(
    targets,
    // Never make application content depend on an animation completing. Safari
    // may pause the first frames while returning from an OAuth/auth redirect.
    // A translate-only entrance still gives hierarchy without a blank screen.
    { y: [18, 0] },
    {
      duration: PAGE_MOTION.staggerItemMs / 1000,
      delay: stagger(PAGE_MOTION.staggerStepMs / 1000, {
        startDelay: PAGE_MOTION.staggerDelayMs / 1000,
      }),
      ease: PAGE_MOTION.ease,
    },
  );

  return () => controls.stop();
}
