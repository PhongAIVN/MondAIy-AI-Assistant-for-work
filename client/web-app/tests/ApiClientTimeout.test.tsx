// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiRequest, DEFAULT_TIMEOUT_MS } from '../src/lib/apiClient';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('apiRequest timeout', () => {
  it('aborts a request that never settles instead of blocking auth bootstrap forever', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );

    const request = apiRequest('/api/v1/auth/me');
    const assertion = expect(request).rejects.toMatchObject({ name: 'TimeoutError' });

    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS + 1);
    await assertion;
  });

  it('still honors a caller abort before the timeout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );

    const controller = new AbortController();
    const request = apiRequest('/api/v1/auth/me', { signal: controller.signal });
    controller.abort(new DOMException('Route changed', 'AbortError'));

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
  });
});
