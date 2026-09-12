import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'warning';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  icon,
  children,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium transition-[transform,background-color,border-color,color,box-shadow] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] focus:ring-offset-2 focus:ring-offset-[var(--color-app-bg)] disabled:opacity-50 disabled:pointer-events-none hover:-translate-y-px active:translate-y-0 active:scale-[0.98]';

  const variantStyles = {
    primary: 'bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-[var(--color-on-primary)] shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)]',
    secondary: 'bg-[var(--color-surface)] border border-[var(--color-border-strong)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]',
    outline: 'border border-[var(--color-border-strong)] bg-transparent hover:bg-[var(--color-surface-hover)] text-[var(--color-text-primary)]',
    ghost: 'bg-transparent hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]',
    danger: 'bg-[var(--color-danger)] hover:brightness-90 text-[#FFFFF2] shadow-[var(--shadow-sm)]',
    warning: 'bg-[var(--color-warning)] hover:brightness-90 text-[#FFFFF2] shadow-[var(--shadow-sm)]',
  };

  const sizeStyles = {
    xs: 'px-2.5 py-1 text-[11px] rounded-md gap-1 min-h-[26px]',
    sm: 'px-3 py-1.5 text-xs rounded-lg gap-1.5 min-h-[32px]',
    md: 'px-4 py-2 text-sm rounded-lg gap-2 min-h-[40px]',
    lg: 'px-5 py-2.5 text-base rounded-xl gap-2.5 min-h-[48px]',
  };

  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {/* Không bọc children vào một span chung. Bọc chung thì chữ và icon nằm
          trong cùng một inline box, gap của flex không ăn, và nhãn dài sẽ đẩy
          icon xuống dòng thứ hai. */}
      {children}
    </button>
  );
};
