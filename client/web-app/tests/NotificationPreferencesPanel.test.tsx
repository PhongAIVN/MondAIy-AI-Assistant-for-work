// @vitest-environment jsdom

// Bảng cài đặt thông báo trong Settings.
//
// Điều quan trọng nhất cần chứng minh: mỗi công tắc đi thẳng ra máy chủ. Bản
// trước của tab này chỉ ghi localStorage, nên người dùng tắt xong vẫn nhận đủ
// mọi thông báo họ vừa tắt — công tắc nói dối còn tệ hơn không có công tắc.

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { NotificationPreferencesPanel } from '../src/components/settings/NotificationPreferencesPanel';

const mocks = vi.hoisted(() => ({
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/reminderApi', () => ({
  getNotificationPreferences: mocks.getNotificationPreferences,
  updateNotificationPreferences: mocks.updateNotificationPreferences,
}));

const PREFS = {
  timezone: 'Asia/Ho_Chi_Minh',
  quietHoursStart: 22,
  quietHoursEnd: 7,
  hourlyCap: 5,
  batchWindowMinutes: 15,
  dailyBriefHour: null as number | null,
  extensionEnabled: true,
  telegramEnabled: true,
  webPushEnabled: true,
  mutedKinds: [] as string[],
};

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
};

beforeEach(() => {
  mocks.getNotificationPreferences.mockReset().mockResolvedValue({ ...PREFS });
  mocks.updateNotificationPreferences
    .mockReset()
    .mockImplementation(async (_token: string, patch: Record<string, unknown>) => ({
      ...PREFS,
      ...patch,
    }));
});

afterEach(cleanup);

describe('NotificationPreferencesPanel', () => {
  it('tắt một kênh là gửi thẳng thay đổi đó lên máy chủ', async () => {
    render(<NotificationPreferencesPanel />);
    const toggle = await screen.findByRole('switch', { name: 'Telegram' });

    await userEvent.click(toggle);

    await waitFor(() =>
      expect(mocks.updateNotificationPreferences).toHaveBeenCalledWith('access-token', {
        telegramEnabled: false,
      }),
    );
    expect(toggle.getAttribute('aria-checked')).toBe('false');
  });

  it('tắt một loại tin gửi nguyên danh sách đã tắt, không gửi từng phần', async () => {
    // Backend coi mutedKinds là thay cả danh sách, nên client phải luôn gửi
    // trạng thái đầy đủ chứ không gửi mỗi loại vừa đổi.
    render(<NotificationPreferencesPanel />);
    const toggle = await screen.findByRole('switch', { name: 'Tổng hợp cuối ngày' });

    await userEvent.click(toggle);

    await waitFor(() =>
      expect(mocks.updateNotificationPreferences).toHaveBeenCalledWith('access-token', {
        mutedKinds: ['daily_brief'],
      }),
    );
  });

  it('công tắc loại tin hiển thị theo hướng "có nhận", ngược với mutedKinds lưu ở máy chủ', async () => {
    mocks.getNotificationPreferences.mockResolvedValue({ ...PREFS, mutedKinds: ['task_due'] });

    render(<NotificationPreferencesPanel />);

    const disabledToggle = await screen.findByRole('switch', { name: 'Việc sắp tới hạn' });
    expect(disabledToggle.getAttribute('aria-checked')).toBe('false');
    expect(screen.getByRole('switch', { name: 'Tổng hợp cuối ngày' }).getAttribute('aria-checked')).toBe(
      'true',
    );
  });

  it('tắt tổng hợp cuối ngày phải gửi cờ riêng, không gửi giờ trống', async () => {
    // dailyBriefHour bỏ trống ở backend nghĩa là "không đổi"; dùng nó để tắt
    // thì thao tác trôi đi im lặng.
    mocks.getNotificationPreferences.mockResolvedValue({ ...PREFS, dailyBriefHour: 18 });
    render(<NotificationPreferencesPanel />);
    const timeSelect = await screen.findByRole('combobox', { name: 'Tổng hợp cuối ngày' });

    await userEvent.selectOptions(timeSelect, 'off');

    await waitFor(() =>
      expect(mocks.updateNotificationPreferences).toHaveBeenCalledWith('access-token', {
        disableDailyBrief: true,
      }),
    );
  });

  it('lưu hỏng thì trả công tắc về trạng thái cũ và nói rõ lỗi', async () => {
    mocks.updateNotificationPreferences.mockRejectedValue(new Error('mạng rớt'));
    render(<NotificationPreferencesPanel />);
    const toggle = await screen.findByRole('switch', { name: 'Telegram' });

    await userEvent.click(toggle);

    expect(await screen.findByRole('alert')).toBeTruthy();
    // Không được để lại một công tắc trông như đã tắt trong khi máy chủ vẫn bật.
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
  });

  it('phản hồi cũ về muộn không được ghi đè một công tắc vừa đổi sau đó', async () => {
    const firstRequest = deferred<typeof PREFS>();
    const latestRequest = deferred<typeof PREFS>();
    mocks.updateNotificationPreferences
      .mockReset()
      .mockReturnValueOnce(firstRequest.promise)
      .mockReturnValueOnce(latestRequest.promise);
    render(<NotificationPreferencesPanel />);
    const toggle = await screen.findByRole('switch', { name: 'Telegram' });

    await userEvent.click(toggle);
    await userEvent.click(toggle);
    expect(mocks.updateNotificationPreferences).toHaveBeenCalledTimes(2);

    latestRequest.resolve({ ...PREFS, telegramEnabled: true });
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
    firstRequest.resolve({ ...PREFS, telegramEnabled: false });
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
  });

  it('không tải được cài đặt thì báo lỗi thay vì hiện giá trị bịa', async () => {
    mocks.getNotificationPreferences.mockRejectedValue(new Error('401'));

    render(<NotificationPreferencesPanel />);

    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByRole('switch')).toBeNull();
  });
});
