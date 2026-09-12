import React from 'react';

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
  accentBorder?: 'none' | 'urgent' | 'warning' | 'info' | 'success';
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick,
  hoverable = false,
  accentBorder = 'none',
}) => {
  const accentStyles = {
    none: 'border-[var(--color-border)]',
    urgent: 'border-l-4 border-l-[var(--color-danger)] border-y-[var(--color-border)] border-r-[var(--color-border)]',
    warning: 'border-l-4 border-l-[var(--color-warning)] border-y-[var(--color-border)] border-r-[var(--color-border)]',
    info: 'border-l-4 border-l-[var(--color-accent)] border-y-[var(--color-border)] border-r-[var(--color-border)]',
    success: 'border-l-4 border-l-[var(--color-success)] border-y-[var(--color-border)] border-r-[var(--color-border)]',
  };

  return (
    <div
      onClick={onClick}
      className={`bg-[var(--color-surface-muted)] rounded-xl border ${accentStyles[accentBorder]} p-5 shadow-[var(--shadow-sm)] transition-[transform,border-color,box-shadow] duration-150 ${
        hoverable ? 'hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)] hover:border-[var(--color-accent)] cursor-pointer' : ''
      } ${className}`}
    >
      {children}
    </div>
  );
};
