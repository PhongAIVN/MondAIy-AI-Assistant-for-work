// @vitest-environment jsdom

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppErrorBoundary } from '../src/components/ui/AppErrorBoundary';
import { AppLoadingScreen } from '../src/components/ui/AppLoadingScreen';

const Crash = () => {
  throw new Error('stale mobile bundle');
};

describe('mobile app recovery', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders a visible status while auth bootstrap is pending', () => {
    render(<AppLoadingScreen />);
    expect(screen.getByRole('status').textContent).toContain('Đang mở mondaiy');
  });

  it('shows recovery UI instead of a blank screen after a render crash', async () => {
    const unregister = vi.fn().mockResolvedValue(true);
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: { getRegistrations: vi.fn().mockResolvedValue([{ unregister }]) },
    });
    Object.defineProperty(globalThis, 'caches', {
      configurable: true,
      value: { keys: vi.fn().mockResolvedValue(['old-shell']), delete: vi.fn().mockResolvedValue(true) },
    });
    const reload = vi.fn();

    render(<AppErrorBoundary onReload={reload}><Crash /></AppErrorBoundary>);
    expect(screen.getByRole('alert').textContent).toContain('Mondaiy cần tải lại');
    fireEvent.click(screen.getByRole('button', { name: 'Tải lại ứng dụng' }));

    await waitFor(() => expect(unregister).toHaveBeenCalled());
    expect(globalThis.caches.delete).toHaveBeenCalledWith('old-shell');
    expect(reload).toHaveBeenCalled();
  });
});
