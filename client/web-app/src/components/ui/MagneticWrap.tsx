import { motion, useMotionValue, useSpring } from 'motion/react';
import type { MouseEvent, PropsWithChildren } from 'react';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';

export interface MagneticWrapProps {
  /** Biên độ hút theo chuột (px), giá trị càng lớn càng "hút" mạnh. */
  strength?: number;
  className?: string;
}

/**
 * Bọc một phần tử (nút, icon, thẻ) để nó trôi nhẹ theo con trỏ chuột khi hover,
 * dùng spring cho cảm giác đàn hồi thay vì tuyến tính. Tắt khi user bật giảm
 * chuyển động (usePreferencesStore) hoặc OS yêu cầu prefers-reduced-motion.
 */
export function MagneticWrap({
  children,
  strength = 0.3,
  className = '',
}: PropsWithChildren<MagneticWrapProps>) {
  const motionEnabled = useMotionEnabled();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 300, damping: 20, mass: 0.5 });
  const springY = useSpring(y, { stiffness: 300, damping: 20, mass: 0.5 });

  function handleMouseMove(event: MouseEvent<HTMLDivElement>) {
    if (!motionEnabled) return;
    const rect = event.currentTarget.getBoundingClientRect();
    x.set((event.clientX - rect.left - rect.width / 2) * strength);
    y.set((event.clientY - rect.top - rect.height / 2) * strength);
  }

  function handleMouseLeave() {
    x.set(0);
    y.set(0);
  }

  if (!motionEnabled) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      style={{ x: springX, y: springY, display: 'inline-flex' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </motion.div>
  );
}
