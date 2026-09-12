import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  position?: 'right' | 'left';
  width?: 'sm' | 'md' | 'lg';
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  position = 'right',
  width = 'md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const widthClasses = {
    sm: 'w-full sm:w-80',
    md: 'w-full sm:w-96 md:w-[440px]',
    lg: 'w-full sm:w-[500px] md:w-[600px]',
  };

  const positionClasses = {
    right: 'right-0 top-0 bottom-0 border-l',
    left: 'left-0 top-0 bottom-0 border-r',
  };

  return (
    <div className="app-overlay fixed inset-0 z-50 overflow-hidden transition-opacity">
      <div
        className="absolute inset-0"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`app-panel absolute ${positionClasses[position]} ${widthClasses[width]} shadow-2xl flex flex-col h-full transform transition-transform duration-200 ease-out`}
      >
        <div className="app-panel-muted flex items-center justify-between px-5 py-4 border-b">
          <div>
            {typeof title === 'string' ? (
              <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading">{title}</h3>
            ) : (
              title
            )}
            {subtitle && <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="app-icon-button p-1.5 rounded-lg border-transparent shadow-none"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {children}
        </div>

        {footer && (
          <div className="app-panel-muted p-4 border-t">
            {footer}
          </div>
        )}
      </aside>
    </div>
  );
};
