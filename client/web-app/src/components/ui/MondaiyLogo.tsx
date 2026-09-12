import React, { useState } from 'react';
import { MondaiyMark } from './MondaiyMark';

interface MondaiyLogoProps {
  className?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'light' | 'dark' | 'auto' | 'on-dark' | 'on-light';
  showIcon?: boolean;
  /** Gif thay thế lúc hover mark — xem MondaiyMark. */
  hoverSrc?: string;
}

const markSizes = {
  xs: 18,
  sm: 20,
  md: 26,
  lg: 32,
  xl: 40,
} as const;

const textSizes = {
  xs: 'text-sm',
  sm: 'text-base',
  md: 'text-lg',
  lg: 'text-2xl',
  xl: 'text-3xl',
} as const;

/**
 * Wordmark: "ai" đậm + màu nhấn, phần còn lại kế thừa màu chữ cha.
 */
export const MondaiyWordmark: React.FC<{
  className?: string;
  accentClassName?: string;
}> = ({ className = '', accentClassName = 'text-action-solid' }) => (
  <span className={className}>
    mond
    <span className={`font-bold ${accentClassName}`}>ai</span>
    y
  </span>
);

export const MondaiyLogo: React.FC<MondaiyLogoProps> = ({
  className = '',
  size = 'md',
  variant = 'auto',
  showIcon = true,
  hoverSrc,
}) => {
  const [hovered, setHovered] = useState(false);

  const baseClass =
    variant === 'on-dark' || variant === 'dark'
      ? 'text-white'
      : variant === 'light' || variant === 'on-light'
        ? 'text-ink-900'
        : 'text-ink-900 dark:text-[#F4F7FC]';

  const accentClass =
    variant === 'on-dark' || variant === 'dark'
      ? 'text-[#A8C8F0]'
      : 'text-action-solid dark:text-[#7EB0E8]';

  return (
    <div
      className={`inline-flex items-center gap-2.5 select-none ${className}`}
      onMouseEnter={hoverSrc ? () => setHovered(true) : undefined}
      onMouseLeave={hoverSrc ? () => setHovered(false) : undefined}
    >
      {showIcon && <MondaiyMark size={markSizes[size]} hoverSrc={hoverSrc} hovered={hovered} />}
      <MondaiyWordmark
        className={`font-semibold tracking-[-0.03em] leading-none ${textSizes[size]} ${baseClass}`}
        accentClassName={accentClass}
      />
    </div>
  );
};
