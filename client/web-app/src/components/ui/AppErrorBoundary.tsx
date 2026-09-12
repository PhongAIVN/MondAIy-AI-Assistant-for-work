import React from 'react';
import { AlertTriangle } from 'lucide-react';

type State = { failed: boolean; errorMessage: string | null };
type Props = React.PropsWithChildren<{ onReload?: () => void }>;

export class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { failed: false, errorMessage: null };

  static getDerivedStateFromError(error: unknown): State {
    return {
      failed: true,
      errorMessage: error instanceof Error ? error.message : String(error),
    };
  }

  componentDidCatch(error: unknown): void {
    console.error('Mondaiy UI crashed', error);
  }

  private recover = async (): Promise<void> => {
    // Một PWA có thể giữ HTML/bundle cũ sau deploy. Chỉ dọn cache tĩnh và SW;
    // session đăng nhập trong localStorage/sessionStorage vẫn được giữ nguyên.
    try {
      const registrations = await navigator.serviceWorker?.getRegistrations?.();
      await Promise.all((registrations ?? []).map((registration) => registration.unregister()));
      const keys = await globalThis.caches?.keys?.();
      await Promise.all((keys ?? []).map((key) => globalThis.caches.delete(key)));
    } finally {
      (this.props.onReload ?? (() => window.location.reload()))();
    }
  };

  render(): React.ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[var(--color-app-bg)] px-5">
        <section role="alert" className="w-full max-w-sm rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 text-center shadow-lg">
          <AlertTriangle className="mx-auto h-7 w-7 text-[var(--color-danger)]" />
          <h1 className="mt-3 font-heading text-xl font-bold text-[var(--color-text-primary)]">
            Mondaiy cần tải lại
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-secondary)]">
            Mondaiy gặp lỗi khi mở workspace. Tài khoản và dữ liệu trên máy chủ vẫn an toàn.
          </p>
          {this.state.errorMessage && (
            <details className="mt-4 text-left text-xs text-[var(--color-text-muted)]">
              <summary className="cursor-pointer select-none">Chi tiết kỹ thuật</summary>
              <code className="mt-2 block break-words rounded-lg bg-[var(--color-surface-muted)] p-2 font-mono">
                {this.state.errorMessage}
              </code>
            </details>
          )}
          <button
            type="button"
            onClick={() => void this.recover()}
            className="mt-5 w-full rounded-xl bg-[var(--color-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--color-on-primary)]"
          >
            Tải lại ứng dụng
          </button>
        </section>
      </main>
    );
  }
}
