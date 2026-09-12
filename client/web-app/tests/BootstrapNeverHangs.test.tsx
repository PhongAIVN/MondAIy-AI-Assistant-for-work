// @vitest-environment jsdom

// Hồi quy cho lỗi màn hình trắng trên iOS (2026-08-13).
//
// Chuỗi gây lỗi: cả ProtectedRoute lẫn GuestRoute render RỖNG khi
// `isBootstrapping` còn true -> `bootstrap()` gọi API mà không có trần thời
// gian -> mạng di động treo -> cờ kẹt true vĩnh viễn -> toàn bộ ứng dụng là
// một màn hình trống đúng màu nền, không spinner, không lỗi, không lối thoát.
//
// Hai ràng buộc khoá ở đây, thiếu một trong hai là lỗi quay lại:
//   1. bootstrap() LUÔN kết thúc, kể cả khi mọi lời gọi mạng đều hỏng
//   2. apiRequest tự bỏ cuộc sau DEFAULT_TIMEOUT_MS thay vì chờ vô hạn

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DEFAULT_TIMEOUT_MS, apiRequest } from '../src/lib/apiClient';

const mocks = vi.hoisted(() => ({ me: vi.fn(), refresh: vi.fn() }));

vi.mock('../src/lib/authApi', () => ({
  me: mocks.me,
  refresh: mocks.refresh,
  signIn: vi.fn(),
  signUp: vi.fn(),
}));

const SESSION_KEY = 'mondaiy.session';

beforeEach(() => {
  mocks.me.mockReset();
  mocks.refresh.mockReset();
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

/** Nạp store mới mỗi lần để `isBootstrapping` bắt đầu lại từ true. */
const freshStore = async () => {
  vi.resetModules();
  const mod = await import('../src/stores/useAuthStore');
  return mod.useAuthStore;
};

/** Ghi sẵn một phiên đã lưu để bootstrap đi vào nhánh gọi mạng. */
const seedSession = () => {
  localStorage.setItem(
    SESSION_KEY,
    JSON.stringify({ accessToken: 'access', refreshToken: 'refresh' }),
  );
};

describe('bootstrap() không bao giờ treo', () => {
  it('kết thúc kể cả khi cả me() lẫn refresh() đều hỏng', async () => {
    seedSession();
    mocks.me.mockRejectedValue(new Error('mạng hỏng'));
    mocks.refresh.mockRejectedValue(new Error('mạng hỏng'));

    const useAuthStore = await freshStore();
    expect(useAuthStore.getState().isBootstrapping).toBe(true);

    await useAuthStore.getState().bootstrap();

    // Đây chính là điều kiện chặn màn hình trắng: cờ phải hạ xuống.
    expect(useAuthStore.getState().isBootstrapping).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('kết thúc kể cả khi refresh() ném lỗi đồng bộ ngoài dự kiến', async () => {
    seedSession();
    mocks.me.mockRejectedValue(new Error('hỏng'));
    mocks.refresh.mockImplementation(() => {
      throw new TypeError('lỗi lập trình ngoài dự kiến');
    });

    const useAuthStore = await freshStore();
    await useAuthStore.getState().bootstrap();

    expect(useAuthStore.getState().isBootstrapping).toBe(false);
  });

  it('không có phiên lưu sẵn thì hạ cờ ngay, không gọi mạng', async () => {
    const useAuthStore = await freshStore();
    await useAuthStore.getState().bootstrap();

    expect(useAuthStore.getState().isBootstrapping).toBe(false);
    expect(mocks.me).not.toHaveBeenCalled();
  });
});

describe('apiRequest tự bỏ cuộc', () => {
  it('huỷ request khi quá DEFAULT_TIMEOUT_MS thay vì chờ mãi', async () => {
    vi.useFakeTimers();
    // fetch không bao giờ resolve — đúng hành vi của mạng di động treo.
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
      })),
    );

    const promise = apiRequest('/api/v1/auth/me');
    const asserted = expect(promise).rejects.toMatchObject({ name: 'TimeoutError' });

    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS + 10);
    await asserted;
  });

  it('người gọi tự huỷ thì request dừng ngay, không đợi hết trần thời gian', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
      })),
    );

    const controller = new AbortController();
    const promise = apiRequest('/api/v1/auth/me', { signal: controller.signal });
    controller.abort(new DOMException('người dùng rời trang', 'AbortError'));

    await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
  });
});
