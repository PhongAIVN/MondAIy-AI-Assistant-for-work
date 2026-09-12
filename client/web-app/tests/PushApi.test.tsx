// @vitest-environment jsdom

// Hợp đồng của lớp đăng ký Web Push (src/lib/pushApi.ts).
//
// Điều đáng khoá không phải chuyện gọi đúng endpoint, mà là những nhánh mà
// người dùng gặp thật và dễ bị làm sai:
//   - máy chủ chưa cấu hình VAPID -> coi như chưa bật, không nổ lỗi
//   - người dùng từ chối quyền -> là lựa chọn hợp lệ, không phải sự cố
//   - tắt push -> máy chủ PHẢI biết, kể cả khi trình duyệt huỷ thất bại

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  disablePush,
  enablePush,
  pushSupported,
  readPushStatus,
  urlBase64ToUint8Array,
} from '../src/lib/pushApi';

const mocks = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock('../src/lib/apiClient', () => ({ apiRequest: mocks.apiRequest }));

/** Dựng đủ bề mặt Web Push giả để jsdom (vốn không có) chạy được. */
const setupPushEnvironment = (
  options: {
    permission?: NotificationPermission;
    existingSubscription?: unknown;
    subscribeResult?: unknown;
  } = {},
) => {
  const subscription = options.subscribeResult ?? {
    endpoint: 'https://push.example.com/abc',
    toJSON: () => ({ keys: { p256dh: 'khoa-p256dh', auth: 'khoa-auth' } }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  };
  const pushManager = {
    subscribe: vi.fn().mockResolvedValue(subscription),
    getSubscription: vi.fn().mockResolvedValue(options.existingSubscription ?? null),
  };
  const registration = { pushManager };

  Object.defineProperty(globalThis, 'PushManager', { configurable: true, value: function () {} });
  Object.defineProperty(globalThis.navigator, 'serviceWorker', {
    configurable: true,
    value: {
      ready: Promise.resolve(registration),
      getRegistration: vi.fn().mockResolvedValue(registration),
    },
  });
  Object.defineProperty(globalThis, 'Notification', {
    configurable: true,
    value: {
      permission: options.permission ?? 'default',
      requestPermission: vi.fn().mockResolvedValue(options.permission ?? 'granted'),
    },
  });
  return { registration, pushManager, subscription };
};

beforeEach(() => {
  mocks.apiRequest.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('urlBase64ToUint8Array', () => {
  it('giải mã được khoá base64url có thay ký tự và thiếu dấu đệm', () => {
    // "-_" là phần base64url khác base64 chuẩn; atob không hiểu nếu không đổi.
    const decoded = urlBase64ToUint8Array('a-_b');
    expect(decoded).toBeInstanceOf(Uint8Array);
    expect(decoded.length).toBeGreaterThan(0);
  });
});

describe('pushSupported / readPushStatus', () => {
  it('máy không hỗ trợ thì nói rõ là không hỗ trợ, không phải chưa bật', async () => {
    // @ts-expect-error - xoá bề mặt để mô phỏng trình duyệt cũ
    delete globalThis.PushManager;
    expect(pushSupported()).toBe(false);

    const status = await readPushStatus();
    expect(status).toEqual({ supported: false, permission: 'unsupported', subscribed: false });
  });

  it('phân biệt đã hỗ trợ nhưng chưa đăng ký', async () => {
    setupPushEnvironment({ permission: 'default' });

    const status = await readPushStatus();
    expect(status.supported).toBe(true);
    expect(status.subscribed).toBe(false);
  });

  it('báo đã đăng ký khi trình duyệt còn giữ subscription', async () => {
    setupPushEnvironment({ permission: 'granted', existingSubscription: { endpoint: 'https://x' } });

    expect((await readPushStatus()).subscribed).toBe(true);
  });
});

describe('enablePush', () => {
  it('máy chủ chưa cấu hình VAPID thì dừng êm, không xin quyền', async () => {
    const { pushManager } = setupPushEnvironment();
    mocks.apiRequest.mockResolvedValueOnce({ publicKey: '', enabled: false });

    expect(await enablePush('token')).toBe(false);
    // Không được làm phiền người dùng bằng hộp xin quyền khi backend còn chưa bật.
    expect(Notification.requestPermission).not.toHaveBeenCalled();
    expect(pushManager.subscribe).not.toHaveBeenCalled();
  });

  it('người dùng từ chối quyền thì trả false và không đăng ký', async () => {
    const { pushManager } = setupPushEnvironment({ permission: 'denied' });
    mocks.apiRequest.mockResolvedValueOnce({ publicKey: 'khoa-cong-khai', enabled: true });

    expect(await enablePush('token')).toBe(false);
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    // Chỉ có đúng lời gọi lấy khoá, không có lời gọi subscribe lên máy chủ.
    expect(mocks.apiRequest).toHaveBeenCalledTimes(1);
  });

  it('đăng ký thành công thì gửi đủ endpoint và hai khoá về máy chủ', async () => {
    const { pushManager } = setupPushEnvironment({ permission: 'granted' });
    mocks.apiRequest
      .mockResolvedValueOnce({ publicKey: 'khoa-cong-khai', enabled: true })
      .mockResolvedValueOnce(undefined);

    expect(await enablePush('token')).toBe(true);

    // userVisibleOnly bắt buộc phải bật, nếu không trình duyệt từ chối đăng ký.
    expect(pushManager.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    const [path, options] = mocks.apiRequest.mock.calls[1];
    expect(path).toBe('/api/v1/push/subscribe');
    expect(options.method).toBe('POST');
    expect(options.body).toMatchObject({
      endpoint: 'https://push.example.com/abc',
      keys: {
        p256dh: 'khoa-p256dh',
        auth: 'khoa-auth',
      },
    });
  });
});

describe('disablePush', () => {
  it('chưa đăng ký thì không gọi máy chủ', async () => {
    setupPushEnvironment({ existingSubscription: null });

    await disablePush('token');
    expect(mocks.apiRequest).not.toHaveBeenCalled();
  });

  it('vẫn báo máy chủ dù trình duyệt huỷ thất bại', async () => {
    // Bỏ sót nhánh này thì máy chủ giữ một endpoint chết và cứ gửi vào đó.
    const subscription = {
      endpoint: 'https://push.example.com/abc',
      toJSON: () => ({ keys: {} }),
      unsubscribe: vi.fn().mockRejectedValue(new Error('trình duyệt từ chối')),
    };
    setupPushEnvironment({ existingSubscription: subscription });
    mocks.apiRequest.mockResolvedValue(undefined);

    await expect(disablePush('token')).rejects.toThrow();

    const [path, options] = mocks.apiRequest.mock.calls[0];
    expect(path).toBe('/api/v1/push/subscribe');
    expect(options.method).toBe('DELETE');
    expect(options.body).toEqual({ endpoint: 'https://push.example.com/abc' });
  });
});

describe('enablePush khi máy chủ có khoá nhưng còn tắt cờ', () => {
  it('không đăng ký, vì đăng ký xong cũng không thông báo nào tới', async () => {
    // Khoá VAPID và cờ WEB_PUSH_ENABLED tắt độc lập nhau. Bỏ qua cờ thì toggle
    // sáng lên trong khi kênh vẫn im — người dùng tin là đã bật rồi.
    const { pushManager } = setupPushEnvironment({ permission: 'granted' });
    mocks.apiRequest.mockResolvedValueOnce({ publicKey: 'khoa-cong-khai', enabled: false });

    expect(await enablePush('token')).toBe(false);
    expect(pushManager.subscribe).not.toHaveBeenCalled();
  });
});
