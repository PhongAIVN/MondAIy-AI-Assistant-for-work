// @vitest-environment jsdom

// Hợp đồng đệm-trước của lưới tuần (FR-102). Bốn điều phải giữ được:
//   1. Vẽ bằng phản hồi đệm (refresh=false) trước khi Google trả lời
//   2. Sau đó tự gọi refresh=true ở nền và cập nhật màn hình
//   3. Đệm còn tươi thì KHÔNG gọi Google — nếu không lớp đệm vô nghĩa
//   4. Làm mới hỏng không được xoá dữ liệu đang hiện

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CalendarWeekPanel } from '../src/components/calendar/CalendarWeekPanel';
import { weekWindow } from '../src/lib/calendarApi';

const mocks = vi.hoisted(() => ({ fetchCalendarWeek: vi.fn() }));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/calendarApi', async () => {
  const thuc = await vi.importActual<typeof import('../src/lib/calendarApi')>(
    '../src/lib/calendarApi',
  );
  return { ...thuc, fetchCalendarWeek: mocks.fetchCalendarWeek };
});

const suKien = (id: string, title: string, startAt: string) => ({
  id,
  calendarId: 'primary',
  title,
  description: '',
  startAt,
  endAt: null,
  allDay: false,
  status: 'active',
  deepLink: null,
  syncedAt: startAt,
});

/** Mốc trong cửa sổ tuần đang xem, để sự kiện luôn được nhóm đúng ngày. */
const trongTuan = (): string => new Date(Date.parse(weekWindow().timeFrom) + 36e5).toISOString();

const phanHoi = (overrides: Partial<Record<string, unknown>> = {}) => ({
  events: [],
  calendars: [],
  origin: 'cache',
  lastSyncedAt: null,
  failedCalendars: [],
  ...overrides,
});

/** Mốc đồng bộ đã quá ngưỡng tươi (5 phút) nên phải kích hoạt làm mới nền. */
const mocCu = () => new Date(Date.now() - 60 * 60 * 1000).toISOString();

beforeEach(() => {
  mocks.fetchCalendarWeek.mockReset();
});

afterEach(cleanup);

describe('CalendarWeekPanel — đệm trước, làm mới sau', () => {
  it('vẽ dữ liệu đệm trước rồi mới gọi làm mới nền', async () => {
    const cu = suKien('e-1', 'Bản cũ trong đệm', trongTuan());
    const moi = suKien('e-2', 'Bản vừa lấy từ Google', trongTuan());

    let giaiPhongLamMoi: (value: unknown) => void = () => {};
    const lamMoiTre = new Promise((resolve) => {
      giaiPhongLamMoi = resolve;
    });

    mocks.fetchCalendarWeek.mockImplementation(async (_token, _window, options = {}) => {
      if (!options.refresh) return phanHoi({ events: [cu], lastSyncedAt: mocCu() });
      await lamMoiTre;
      return phanHoi({ events: [moi], origin: 'refreshed', lastSyncedAt: new Date().toISOString() });
    });

    render(<CalendarWeekPanel />);

    // Màn hình có nội dung trong khi lời gọi Google vẫn đang treo — đây chính
    // là điều lớp đệm mua được.
    expect(await screen.findByText('Bản cũ trong đệm')).toBeTruthy();
    expect(screen.queryByText('Bản vừa lấy từ Google')).toBeNull();

    giaiPhongLamMoi(null);

    expect(await screen.findByText('Bản vừa lấy từ Google')).toBeTruthy();
    expect(screen.queryByText('Bản cũ trong đệm')).toBeNull();

    const luotGoi = mocks.fetchCalendarWeek.mock.calls;
    expect(luotGoi[0][2]?.refresh).toBeFalsy();
    expect(luotGoi[1][2]?.refresh).toBe(true);
  });

  it('không gọi Google khi bộ đệm còn tươi', async () => {
    mocks.fetchCalendarWeek.mockResolvedValue(
      phanHoi({
        events: [suKien('e-1', 'Sự kiện còn tươi', trongTuan())],
        lastSyncedAt: new Date().toISOString(),
      }),
    );

    render(<CalendarWeekPanel />);
    await screen.findByText('Sự kiện còn tươi');

    // Chờ một nhịp để bước làm mới nền (nếu có) kịp chạy trước khi khẳng định.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mocks.fetchCalendarWeek).toHaveBeenCalledTimes(1);
    expect(mocks.fetchCalendarWeek.mock.calls[0][2]?.refresh).toBeFalsy();
  });

  it('giữ nguyên dữ liệu đệm khi làm mới hỏng và báo rõ đang xem bản cũ', async () => {
    mocks.fetchCalendarWeek.mockImplementation(async (_token, _window, options = {}) => {
      if (!options.refresh) {
        return phanHoi({ events: [suKien('e-1', 'Vẫn phải thấy tôi', trongTuan())], lastSyncedAt: mocCu() });
      }
      throw new Error('Google Calendar chưa được kết nối.');
    });

    render(<CalendarWeekPanel />);

    // Ngôn ngữ mặc định của store là 'vi' nên khẳng định theo chuỗi tiếng Việt.
    expect(await screen.findByText(/Không làm mới được/)).toBeTruthy();
    // Điều kiện quan trọng nhất: lỗi làm mới không được biến màn hình thành trắng.
    expect(screen.getByText('Vẫn phải thấy tôi')).toBeTruthy();
  });

  it('hiện mốc đồng bộ gần nhất thay vì giả vờ realtime', async () => {
    mocks.fetchCalendarWeek.mockResolvedValue(
      phanHoi({
        events: [suKien('e-1', 'Sự kiện đã lưu', trongTuan())],
        lastSyncedAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
      }),
    );

    render(<CalendarWeekPanel />);
    expect(await screen.findByText(/Cập nhật 2p trước/)).toBeTruthy();
  });

  it('nút làm mới bỏ qua ngưỡng tươi và gọi Google theo yêu cầu người dùng', async () => {
    mocks.fetchCalendarWeek.mockResolvedValue(
      phanHoi({
        events: [suKien('e-1', 'Sự kiện còn tươi', trongTuan())],
        lastSyncedAt: new Date().toISOString(),
      }),
    );

    render(<CalendarWeekPanel />);
    await screen.findByText('Sự kiện còn tươi');

    await userEvent.click(screen.getByRole('button', { name: /Làm mới/ }));

    await waitFor(() => {
      expect(
        mocks.fetchCalendarWeek.mock.calls.some((call) => call[2]?.refresh === true),
      ).toBe(true);
    });
  });

  it('nói rõ tuần có thể còn thiếu khi vài lịch đọc hỏng', async () => {
    mocks.fetchCalendarWeek.mockImplementation(async (_token, _window, options = {}) =>
      options.refresh
        ? phanHoi({
            events: [],
            origin: 'refreshed',
            calendars: [{ id: 'work', name: 'Lịch công việc' }],
            failedCalendars: ['work'],
            lastSyncedAt: new Date().toISOString(),
          })
        : phanHoi({ lastSyncedAt: mocCu() }),
    );

    render(<CalendarWeekPanel />);
    expect(await screen.findByText(/Lịch công việc/)).toBeTruthy();
  });
});
