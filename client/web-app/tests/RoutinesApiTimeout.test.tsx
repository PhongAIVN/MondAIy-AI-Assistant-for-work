// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_TIMEOUT_MS } from '../src/lib/apiClient';
import { runRoutineNow } from '../src/lib/routinesApi';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

/**
 * run-now chạy nguyên vòng agent thật (nhiều lượt LLM) trong request, chậm
 * hơn hẳn CRUD thường — regression test cho bug đã gặp: timeout mặc định
 * 15s của apiRequest hủy request giữa chừng, hiện lỗi "không lưu được" dù
 * backend vẫn đang chạy tiếp (xem client/web-app/src/lib/routinesApi.ts).
 */
describe('runRoutineNow timeout', () => {
  it('does not abort before the default 15s timeout would have fired', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );

    const request = runRoutineNow('token', 1);
    const settled = vi.fn();
    request.catch(settled);

    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS + 1_000);
    expect(settled).not.toHaveBeenCalled();
  });

  it('eventually aborts a run that truly never settles', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
        }),
      ),
    );

    const request = runRoutineNow('token', 1);
    const assertion = expect(request).rejects.toMatchObject({ name: 'TimeoutError' });

    await vi.advanceTimersByTimeAsync(120_000 + 1);
    await assertion;
  });
});
