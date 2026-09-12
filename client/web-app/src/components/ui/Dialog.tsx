import React, { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

export interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

export const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
}) => {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current();
      if (e.key !== 'Tab' || !panelRef.current) return;
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    const firstFocusable = panelRef.current?.querySelector<HTMLElement>(
      '[data-autofocus], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled])',
    );
    firstFocusable?.focus();
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const maxWidthClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  };

  return (
    <div
      className="app-overlay fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 animate-in fade-in duration-150"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        className={`app-panel relative w-full min-w-0 ${maxWidthClasses[maxWidth]} rounded-2xl shadow-xl overflow-hidden flex flex-col max-h-[92dvh]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="app-panel-muted flex items-center justify-between p-5 border-b">
          <div>
            {title && <h3 id={titleId} className="text-lg font-bold text-[var(--color-text-primary)] font-heading">{title}</h3>}
            {description && <p id={descriptionId} className="text-xs text-[var(--color-text-secondary)] mt-0.5">{description}</p>}
          </div>
          <button
            onClick={onClose}
            className="app-icon-button p-1 rounded-lg border-transparent shadow-none"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-4 text-sm text-[var(--color-text-primary)]">
          {children}
        </div>

        {footer && (
          <div className="app-panel-muted flex items-center justify-end gap-3 p-4 border-t">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
