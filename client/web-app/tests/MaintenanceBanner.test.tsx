// @vitest-environment jsdom

import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MaintenanceBanner } from '../src/components/system/MaintenanceBanner';
import { apiRequest, probeBackendReadiness } from '../src/lib/apiClient';
import { getBackendStatus, resetBackendStatus } from '../src/lib/backendStatus';

beforeEach(() => {
  resetBackendStatus();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const jsonResponse = (status: number) =>
  new Response(JSON.stringify({ status: status === 200 ? 'ok' : 'degraded' }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('tín hiệu bảo trì', () => {
  it('im lặng khi backend khoẻ — không được doạ người dùng vô cớ', () => {
    render(<MaintenanceBanner />);
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('hiện banner khi API trả 503', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(503)));

    await expect(apiRequest('/api/v1/anything')).rejects.toThrow();
    expect(getBackendStatus()).toBe('maintenance');

    render(<MaintenanceBanner />);
    expect(screen.getByRole('status')).toBeTruthy();
  });

  it('hiện banner khi không tới được backend (mất mạng, DNS hỏng)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );

    await expect(apiRequest('/api/v1/anything')).rejects.toThrow();
    expect(getBackendStatus()).toBe('unreachable');
  });

  it('gặp 500 thì đi hỏi readiness, không tự kết luận', async () => {
    // DB chết KHÔNG làm endpoint thường trả 503 — nó trả 500. Nếu chỉ nghe 503 thì
    // banner không bao giờ hiện đúng lúc cần. Đây là ca hồi quy cho lỗi đó.
    const fetchMock = vi.fn(async (url: string) =>
      String(url).endsWith('/health/ready') ? jsonResponse(503) : jsonResponse(500),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(apiRequest('/api/v1/anything')).rejects.toThrow();

    await waitFor(() => expect(getBackendStatus()).toBe('maintenance'));
    expect(fetchMock.mock.calls.some(([u]) => String(u).endsWith('/health/ready'))).toBe(true);
  });

  it('bug 500 thường mà hạ tầng vẫn khoẻ thì KHÔNG dán nhãn bảo trì', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        String(url).endsWith('/health/ready') ? jsonResponse(200) : jsonResponse(500),
      ),
    );

    await expect(apiRequest('/api/v1/anything')).rejects.toThrow();

    await waitFor(() => expect(getBackendStatus()).toBe('ok'));
  });

  it('KHÔNG báo bảo trì khi caller tự huỷ request', async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new DOMException('Aborted', 'AbortError');
      }),
    );

    await expect(apiRequest('/api/v1/anything', { signal: controller.signal })).rejects.toThrow();
    expect(getBackendStatus()).toBe('ok');
  });

  it('tự gỡ banner khi backend hồi phục', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(503)));
    await probeBackendReadiness();
    expect(getBackendStatus()).toBe('maintenance');

    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200)));
    await probeBackendReadiness();

    await waitFor(() => expect(getBackendStatus()).toBe('ok'));
  });

  it('KHÔNG tin 200 text/html — fallback SPA của host không phải backend khoẻ', async () => {
    // Lỗi thật trên production: vercel.json chỉ rewrite /api/* và /health, quên
    // /health/ready → fallback SPA trả index.html kèm 200, probe tưởng hệ thống khoẻ.
    const html = new Response('<!doctype html><html><body>app</body></html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    });
    vi.stubGlobal('fetch', vi.fn(async () => html.clone()));

    // Đang ở trạng thái hỏng thì một phản hồi HTML không được phép "chữa lành".
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(503)));
    await probeBackendReadiness();
    expect(getBackendStatus()).toBe('maintenance');

    vi.stubGlobal('fetch', vi.fn(async () => html.clone()));
    await probeBackendReadiness();
    expect(getBackendStatus()).toBe('maintenance');
  });

  it('probe hỏi /health/ready chứ không hỏi /health — /health luôn 200 kể cả khi DB ngủ', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200));
    vi.stubGlobal('fetch', fetchMock);

    await probeBackendReadiness();

    const calledUrl = String(fetchMock.mock.calls[0][0]);
    expect(calledUrl.endsWith('/health/ready')).toBe(true);
  });
});
