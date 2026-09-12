import React from 'react';

export type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
  'aria-label'?: string;
  className?: string;
};

/** Công tắc bật/tắt thay cho checkbox trong form cài đặt. */
export const Toggle: React.FC<ToggleProps> = ({
  checked,
  onChange,
  disabled = false,
  id,
  'aria-label': ariaLabel,
  className = '',
}) => {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-[background-color,border-color,box-shadow] duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-app-bg)] disabled:opacity-50 disabled:pointer-events-none cursor-pointer ${
        checked
          ? 'border-[var(--color-primary)] bg-[var(--color-primary)]'
          : 'border-[var(--color-border-strong)] bg-[var(--color-surface)]'
      } ${className}`}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full shadow-sm transition-transform duration-150 ${
          checked
            ? 'translate-x-[18px] bg-[var(--color-on-primary)]'
            : 'translate-x-[3px] bg-[var(--color-text-muted)]'
        }`}
      />
    </button>
  );
};
