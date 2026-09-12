import React from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { CheckCircle2, Info, AlertTriangle, AlertCircle, X } from 'lucide-react';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useAppStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        const icons = {
          success: <CheckCircle2 className="w-5 h-5 text-[var(--color-success)] shrink-0" />,
          info: <Info className="w-5 h-5 text-[var(--color-info)] shrink-0" />,
          warning: <AlertTriangle className="w-5 h-5 text-[var(--color-warning)] shrink-0" />,
          error: <AlertCircle className="w-5 h-5 text-[var(--color-danger)] shrink-0" />,
        };

        const bgColors = {
          success: 'bg-[var(--color-success-soft)] border-[var(--color-success)]',
          info: 'bg-[var(--color-info-soft)] border-[var(--color-info)]',
          warning: 'bg-[var(--color-warning-soft)] border-[var(--color-warning)]',
          error: 'bg-[var(--color-danger-soft)] border-[var(--color-danger)]',
        };

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-lg transition-all duration-200 animate-in slide-in-from-bottom-2 ${bgColors[toast.type]}`}
          >
            {toast.mascotGif ? (
              <img src={toast.mascotGif} alt="" aria-hidden="true" className="h-9 w-9 shrink-0" />
            ) : (
              icons[toast.type]
            )}
            <div className="flex-1">
              <h4 className="text-xs font-bold text-[var(--color-text-primary)]">{toast.title}</h4>
              <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">{toast.message}</p>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="app-icon-button p-1 rounded-md border-transparent shadow-none"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
