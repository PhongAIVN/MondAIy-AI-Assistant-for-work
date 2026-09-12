// @vitest-environment jsdom

// Toggle bật thông báo đẩy trong Settings.
//
// Bốn lý do "không bật được" phải ra bốn câu khác nhau — đó là toàn bộ giá trị
// của component này. Gộp thành một câu chung là bỏ mặc người dùng tự đoán, và
// riêng trường hợp iOS chưa cài thì cái toggle còn bấm vào cũng vô ích.

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { PushToggle } from '../src/components/pwa/PushToggle';

const mocks = vi.hoisted(() => ({
  readPushStatus: vi.fn(),
  enablePush: vi.fn(),
  disablePush: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/pushApi', () => ({
  readPushStatus: mocks.readPushStatus,
  enablePush: mocks.enablePush,
  disablePush: mocks.disablePush,
}));

/** Giả lập user agent và chế độ hiển thị để kiểm nhánh iOS. */
const setPlatform = (userAgent: string, standalone = false) => {
  Object.defineProperty(globalThis.navigator, 'userAgent', { configurable: true, value: userAgent });
  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    value: () => ({ matches: standalone }),
  });
};

const setPermission = (permission: NotificationPermission) => {
  Object.defineProperty(globalThis, 'Notification', {
    configurable: true,
    value: { permission, requestPermission: vi.fn() },
  });
};

const ANDROID = 'Mozilla/5.0 (Linux; Android 14) Chrome/120';
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Version/17.0 Mobile Safari';

beforeEach(() => {
  mocks.readPushStatus.mockReset();
  mocks.enablePush.mockReset();
  mocks.disablePush.mockReset();
  setPlatform(ANDROID);
  setPermission('default');
});

afterEach(cleanup);

describe('PushToggle', () => {
  it('bật thành công thì toggle chuyển sang đã đăng ký', async () => {
    mocks.readPushStatus
      .mockResolvedValueOnce({ supported: true, permission: 'default', subscribed: false })
      .mockResolvedValueOnce({ supported: true, permission: 'granted', subscribed: true });
    mocks.enablePush.mockResolvedValue(true);

    render(<PushToggle />);
    const toggle = await screen.findByRole('switch');
    await userEvent.click(toggle);

    await waitFor(() =>
      expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('true'),
    );
    expect(mocks.enablePush).toHaveBeenCalledWith('access-token');
  });

  it('người dùng đã chặn thông báo thì chỉ đúng cách mở lại', async () => {
    mocks.readPushStatus.mockResolvedValue({
      supported: true,
      permission: 'denied',
      subscribed: false,
    });
    mocks.enablePush.mockResolvedValue(false);
    setPermission('denied');

    render(<PushToggle />);
    await userEvent.click(await screen.findByRole('switch'));

    expect((await screen.findByRole('alert')).textContent).toMatch(/blocked|chặn/i);
  });

  it('máy chủ chưa bật thì nói rõ là do máy chủ, không đổ cho người dùng', async () => {
    mocks.readPushStatus.mockResolvedValue({
      supported: true,
      permission: 'default',
      subscribed: false,
    });
    mocks.enablePush.mockResolvedValue(false);

    render(<PushToggle />);
    await userEvent.click(await screen.findByRole('switch'));

    expect((await screen.findByRole('alert')).textContent).toMatch(/server|máy chủ/i);
  });

  it('trình duyệt không hỗ trợ thì khoá toggle và nói lý do', async () => {
    mocks.readPushStatus.mockResolvedValue({
      supported: false,
      permission: 'unsupported',
      subscribed: false,
    });

    render(<PushToggle />);
    expect((await screen.findByRole('switch') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/does not support|không hỗ trợ/i)).toBeTruthy();
  });

  it('iOS chưa cài lên màn hình chính: khoá toggle và chỉ cách cài trước', async () => {
    // Bấm vào cũng chắc chắn thất bại — Apple chỉ cho push với web app đã cài.
    mocks.readPushStatus.mockResolvedValue({
      supported: true,
      permission: 'default',
      subscribed: false,
    });
    setPlatform(IPHONE, false);

    render(<PushToggle />);
    expect((await screen.findByRole('switch') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/Home Screen|Màn hình chính/i)).toBeTruthy();
    expect(mocks.enablePush).not.toHaveBeenCalled();
  });

  it('iOS đã cài rồi thì cho bật bình thường', async () => {
    mocks.readPushStatus.mockResolvedValue({
      supported: true,
      permission: 'default',
      subscribed: false,
    });
    setPlatform(IPHONE, true);

    render(<PushToggle />);
    expect((await screen.findByRole('switch') as HTMLButtonElement).disabled).toBe(false);
  });

  it('tắt thì gọi disablePush', async () => {
    mocks.readPushStatus
      .mockResolvedValueOnce({ supported: true, permission: 'granted', subscribed: true })
      .mockResolvedValueOnce({ supported: true, permission: 'granted', subscribed: false });
    mocks.disablePush.mockResolvedValue(undefined);

    render(<PushToggle />);
    await userEvent.click(await screen.findByRole('switch'));

    await waitFor(() => expect(mocks.disablePush).toHaveBeenCalledWith('access-token'));
  });
});
