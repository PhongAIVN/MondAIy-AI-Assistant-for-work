import React, { useLayoutEffect, useRef } from 'react';
import { useLocation, useOutlet } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { getPageTransitionKey } from '../../lib/pageTransitionKey';
import { PAGE_MOTION, playStaggerEnter } from '../../lib/pageMotion';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';

/**
 * Bọc nội dung route: đổi trang chậm hơn + các khối hiện lần lượt.
 * Dùng useOutlet để AnimatePresence giữ được exit animation.
 */
export const PageTransition: React.FC = () => {
  const location = useLocation();
  const outlet = useOutlet();
  const motionEnabled = useMotionEnabled();
  const key = getPageTransitionKey(location.pathname);
  const rootRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!motionEnabled) return;
    const root = rootRef.current;
    if (!root) return;
    return playStaggerEnter(root);
  }, [key, motionEnabled]);

  if (!motionEnabled) {
    return <div className="page-transition-root min-h-0 w-full">{outlet}</div>;
  }

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={key}
        ref={rootRef}
        className="page-transition-root min-h-0 w-full"
        // Content must be visible before Motion starts. iOS can suspend the PWA
        // between the auth redirect and the first animation frame; an opacity-0
        // initial state then leaves the whole post-login route permanently blank.
        initial={false}
        animate={{
          opacity: 1,
          y: 0,
          transition: { duration: PAGE_MOTION.enterMs / 1000, ease: PAGE_MOTION.ease },
        }}
        exit={{
          opacity: 0,
          y: -12,
          transition: { duration: PAGE_MOTION.exitMs / 1000, ease: PAGE_MOTION.ease },
        }}
      >
        {outlet}
      </motion.div>
    </AnimatePresence>
  );
};
