/**
 * Phát hiện bản cũ sau deploy, và làm mới không mất phiên đăng nhập.
 *
 * Bối cảnh: `registerType: 'autoUpdate'` thay service worker nền nhưng KHÔNG
 * tải lại trang. Một tab để mở xuyên qua một lần deploy vẫn chạy JS cũ và gọi
 * backend đã đổi hợp đồng — không có gì phát hiện, không có gì nhắc.
 */

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppUpdateBanner } from '../src/components/ui/AppUpdateBanner';
import { checkAppVersion, reloadToLatest } from '../src/lib/appVersion';

const RUNNING = 'abc123abc123';

function fetchTraVe(buildId: unknown, ok = true) {
  return vi.fn(async () =>
    ({
      ok,
      status: ok ? 200 : 503,
      json: async () => ({ buildId }),
    }) as unknown as Response,
  );
}

afterEach(() => {
  // Repo này KHÔNG bật auto-cleanup của Testing Library (xem vitest.config.ts —
  // không có globals:true). Thiếu dòng này thì DOM của test trước còn nguyên và
  // test sau đọc phải banner cũ, tức là xanh/đỏ vì lý do sai.
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('checkAppVersion', () => {
  it('bản trên server trùng bản đang chạy thì không báo gì', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    expect(await checkAppVersion(fetchTraVe(RUNNING))).toEqual({ status: 'current' });
  });

  it('bản trên server khác thì báo stale kèm cả hai giá trị', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    const result = await checkAppVersion(fetchTraVe('def456def456'));
    expect(result).toEqual({ status: 'stale', deployed: 'def456def456', running: RUNNING });
  });

  it('mất mạng thì trả unknown, KHÔNG ném lỗi và KHÔNG báo nhầm', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    const fetchHong = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });

    const result = await checkAppVersion(fetchHong as unknown as typeof fetch);

    expect(result.status).toBe('unknown');
  });

  it('server chưa có version.json thì im lặng, vì báo nhầm tệ hơn không báo', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    expect((await checkAppVersion(fetchTraVe(undefined))).status).toBe('unknown');
    expect((await checkAppVersion(fetchTraVe(RUNNING, false))).status).toBe('unknown');
  });

  it('fetch phải dùng no-store, kẻo chính lời kiểm cũng bị cache', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    const fetchGia = fetchTraVe(RUNNING);

    await checkAppVersion(fetchGia as unknown as typeof fetch);

    expect(fetchGia).toHaveBeenCalledWith(
      '/version.json',
      expect.objectContaining({ cache: 'no-store' }),
    );
  });
});

describe('AppUpdateBanner', () => {
  it('hiện nhắc kèm nút khi bản đang chạy đã cũ', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    vi.stubGlobal('fetch', fetchTraVe('moi-hon-nhieu'));

    render(<AppUpdateBanner />);

    expect(await screen.findByText('Đã có bản Mondaiy mới')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Làm mới ứng dụng' })).not.toBeNull();
  });

  it('không hiện gì khi đang chạy bản mới nhất', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    vi.stubGlobal('fetch', fetchTraVe(RUNNING));

    render(<AppUpdateBanner />);

    await waitFor(() => expect(screen.queryByText('Đã có bản Mondaiy mới')).toBeNull());
  });

  it('bấm "Để sau" thì đóng và không dựng lại', async () => {
    vi.stubGlobal('__BUILD_ID__', RUNNING);
    vi.stubGlobal('fetch', fetchTraVe('moi-hon-nhieu'));
    render(<AppUpdateBanner />);
    await screen.findByText('Đã có bản Mondaiy mới');

    await userEvent.click(screen.getByRole('button', { name: 'Để sau' }));

    await waitFor(() => expect(screen.queryByText('Đã có bản Mondaiy mới')).toBeNull());
  });
});

describe('reloadToLatest', () => {
  it('gỡ service worker, xoá cache tĩnh, rồi tải lại', async () => {
    const unregister = vi.fn(async () => true);
    const xoa = vi.fn(async () => true);
    vi.stubGlobal('navigator', {
      serviceWorker: { getRegistrations: async () => [{ unregister }] },
    });
    vi.stubGlobal('caches', { keys: async () => ['vo-app'], delete: xoa });
    const reload = vi.fn();

    await reloadToLatest(reload);

    expect(unregister).toHaveBeenCalled();
    expect(xoa).toHaveBeenCalledWith('vo-app');
    expect(reload).toHaveBeenCalled();
  });

  it('KHÔNG đụng localStorage — phiên đăng nhập phải sống sót qua một lần làm mới', async () => {
    const xoaHet = vi.fn();
    vi.stubGlobal('navigator', { serviceWorker: { getRegistrations: async () => [] } });
    vi.stubGlobal('caches', { keys: async () => [], delete: vi.fn() });
    vi.stubGlobal('localStorage', { clear: xoaHet, removeItem: xoaHet });

    await reloadToLatest(vi.fn());

    expect(xoaHet).not.toHaveBeenCalled();
  });

  it('service worker hỏng vẫn phải tải lại, không kẹt màn hình trắng', async () => {
    vi.stubGlobal('navigator', {
      serviceWorker: {
        getRegistrations: async () => {
          throw new Error('SecurityError');
        },
      },
    });
    vi.stubGlobal('caches', { keys: async () => [], delete: vi.fn() });
    const reload = vi.fn();

    await reloadToLatest(reload).catch(() => undefined);

    expect(reload).toHaveBeenCalled();
  });
});
