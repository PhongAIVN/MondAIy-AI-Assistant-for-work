import React from 'react';
import { LoaderCircle } from 'lucide-react';

export const AppLoadingScreen: React.FC = () => (
  <main
    role="status"
    aria-live="polite"
    className="flex min-h-[100dvh] items-center justify-center bg-[var(--color-app-bg)] px-6 text-center"
  >
    <div className="flex flex-col items-center gap-3 text-[var(--color-text-secondary)]">
      <LoaderCircle className="h-6 w-6 animate-spin text-[var(--color-primary)]" />
      <p className="text-sm font-semibold">Đang mở mondaiy…</p>
    </div>
  </main>
);
