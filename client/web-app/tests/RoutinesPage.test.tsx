// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RoutinesPage } from '../src/pages/RoutinesPage';
import { resetRoutineStore } from '../src/stores/useRoutineStore';

const mocks = vi.hoisted(() => ({
  listRoutines: vi.fn(),
  createRoutine: vi.fn(),
  updateRoutine: vi.fn(),
  deleteRoutine: vi.fn(),
  addToast: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) => selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: mocks.addToast }),
}));

vi.mock('../src/lib/routinesApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/lib/routinesApi')>();
  return {
    ...actual,
    listRoutines: mocks.listRoutines,
    createRoutine: mocks.createRoutine,
    updateRoutine: mocks.updateRoutine,
    deleteRoutine: mocks.deleteRoutine,
  };
});

const ROUTINE = {
  id: 1,
  name: 'Tóm tắt việc hôm nay',
  instructions: 'Tóm tắt việc cần xử lý hôm nay.',
  frequency: 'daily' as const,
  hour: 7,
  dayOfWeek: null,
  dayOfMonth: null,
  timezone: 'Asia/Ho_Chi_Minh',
  enabled: true,
  notifyPush: true,
  notifyEmail: false,
  lastRunDate: null,
};

beforeEach(() => {
  resetRoutineStore();
  mocks.listRoutines.mockReset().mockResolvedValue([]);
  mocks.createRoutine.mockReset().mockResolvedValue(ROUTINE);
  mocks.updateRoutine.mockReset().mockImplementation(async (_t: string, _id: number, patch: Record<string, unknown>) => ({
    ...ROUTINE,
    ...patch,
  }));
  mocks.deleteRoutine.mockReset().mockResolvedValue(undefined);
  mocks.addToast.mockReset();
});

afterEach(cleanup);

/** RoutinesPage tự điều hướng bằng useNavigate — cần Router thật bọc ngoài,
 * và 1 route đích /routines/:routineId để xác nhận điều hướng đã xảy ra
 * (không mock react-router, chỉ dựng route giả để quan sát kết quả). */
const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/routines']}>
      <Routes>
        <Route path="/routines" element={<RoutinesPage />} />
        <Route path="/routines/:routineId" element={<div>DETAIL PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe('RoutinesPage — empty state', () => {
  it('shows the schedule hero and the template library when there are no routines yet', async () => {
    renderPage();

    await screen.findByText('Đặt lịch cho AI của bạn');
    expect(screen.getByText('Xem thư viện')).toBeTruthy();
    // Tab mặc định là "Suggested" — template Inbox chỉ hiện sau khi đổi tab.
    expect(screen.getByText('Tóm tắt việc hôm nay')).toBeTruthy();
  });

  it('shows a retryable error instead of inventing a routine after load failure', async () => {
    mocks.listRoutines.mockRejectedValue(new Error('offline'));
    renderPage();

    expect((await screen.findByRole('alert')).textContent).toContain('Không tải được routine');
  });

  it('keeps the routine list without loading historical summaries on the overview', async () => {
    mocks.listRoutines.mockResolvedValue([ROUTINE]);
    renderPage();

    await waitFor(() => expect(screen.getAllByText('Tóm tắt việc hôm nay').length).toBeGreaterThan(0));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByTestId('routine-summaries')).toBeNull();
  });
});

describe('RoutinesPage — create flow', () => {
  it('opens the picker with "start from scratch" and a template library on New routine', async () => {
    renderPage();
    await screen.findByText('Đặt lịch cho AI của bạn');

    await userEvent.click(screen.getByRole('button', { name: 'Routine mới' }));

    const dialog = screen.getByRole('dialog', { name: 'Tạo routine mới' });
    expect(within(dialog).getByText('Tạo từ đầu')).toBeTruthy();
    expect(within(dialog).getByText('Hoặc bắt đầu từ mẫu')).toBeTruthy();
  });

  it('creates a from-scratch routine with real instructions and a schedule', async () => {
    renderPage();
    await screen.findByText('Đặt lịch cho AI của bạn');
    await userEvent.click(screen.getByRole('button', { name: 'Routine mới' }));
    await userEvent.click(screen.getByText('Tạo từ đầu'));

    const dialog = screen.getByRole('dialog', { name: 'Cấu hình routine' });
    await userEvent.type(within(dialog).getByLabelText('Tên'), 'Tóm tắt Jira');
    await userEvent.type(within(dialog).getByLabelText('Hướng dẫn'), 'Tóm tắt issue Jira của tôi.');
    expect(within(dialog).getByText(/không tự gửi email hay ghi vào ứng dụng khác/i)).toBeTruthy();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Tạo routine' }));

    await waitFor(() =>
      expect(mocks.createRoutine).toHaveBeenCalledWith('access-token', {
        name: 'Tóm tắt Jira',
        instructions: 'Tóm tắt issue Jira của tôi.',
        frequency: 'daily',
        hour: 8,
        dayOfWeek: undefined,
        dayOfMonth: undefined,
        notifyPush: true,
        notifyEmail: false,
      }),
    );
  });

  it('sets up a template directly from the library with its schedule prefilled', async () => {
    renderPage();
    await screen.findByText('Đặt lịch cho AI của bạn');
    // Tab mặc định là "Suggested" — phải đổi qua "Inbox" mới thấy template này.
    await userEvent.click(screen.getByRole('button', { name: 'Hộp thư' }));

    await userEvent.click(within(screen.getByTestId('template-inbox-drafts')).getByRole('button', { name: 'Thiết lập' }));

    const dialog = screen.getByRole('dialog', { name: 'Cấu hình routine' });
    expect((within(dialog).getByLabelText('Tên') as HTMLInputElement).value).toBe('Soạn sẵn trả lời email quan trọng');
    expect(within(dialog).getByText('Đổi mẫu')).toBeTruthy();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Tạo routine' }));

    await waitFor(() =>
      expect(mocks.createRoutine).toHaveBeenCalledWith(
        'access-token',
        expect.objectContaining({ name: 'Soạn sẵn trả lời email quan trọng', hour: 17 }),
      ),
    );
  });

  it('reveals a day-of-week picker only for weekly schedules', async () => {
    renderPage();
    await screen.findByText('Đặt lịch cho AI của bạn');
    await userEvent.click(screen.getByRole('button', { name: 'Routine mới' }));
    await userEvent.click(screen.getByText('Tạo từ đầu'));

    const dialog = screen.getByRole('dialog', { name: 'Cấu hình routine' });
    expect(within(dialog).queryByLabelText('Vào ngày')).toBeNull();

    await userEvent.click(within(dialog).getByRole('button', { name: 'Hằng tuần' }));
    expect(within(dialog).getByLabelText('Vào ngày')).toBeTruthy();
  });

  it('picks an hour from the custom popover instead of a native <select>', async () => {
    renderPage();
    await screen.findByText('Đặt lịch cho AI của bạn');
    await userEvent.click(screen.getByRole('button', { name: 'Routine mới' }));
    await userEvent.click(screen.getByText('Tạo từ đầu'));

    const dialog = screen.getByRole('dialog', { name: 'Cấu hình routine' });
    // Không còn <select> gốc — trình duyệt không tự vẽ list 24 mục tràn màn hình nữa.
    expect(within(dialog).queryByRole('combobox')).toBeNull();

    await userEvent.click(within(dialog).getByRole('button', { name: '08:00' }));
    await userEvent.click(within(dialog).getByRole('option', { name: '18:00' }));

    expect(within(dialog).getByRole('button', { name: '18:00' })).toBeTruthy();
    expect(within(dialog).queryByRole('listbox')).toBeNull();
  });
});

describe('RoutinesPage — navigating to a routine', () => {
  // ROUTINE.name trùng tên với mẫu gợi ý "Tóm tắt việc hôm nay" trong thư viện
  // mẫu (luôn hiển thị cùng lúc với danh sách routine thật), nên phải chọn
  // đúng thẻ routine thật — mục đầu tiên trong DOM — thay vì getByText đơn lẻ.
  const findRoutineCardHeading = () => {
    const matches = screen.getAllByText('Tóm tắt việc hôm nay');
    expect(matches.length).toBeGreaterThan(0);
    return matches[0];
  };

  it('navigates to the routine detail page when the card body is clicked', async () => {
    mocks.listRoutines.mockResolvedValue([ROUTINE]);
    renderPage();
    await waitFor(() => expect(findRoutineCardHeading()).toBeTruthy());

    await userEvent.click(findRoutineCardHeading());

    expect(await screen.findByText('DETAIL PAGE')).toBeTruthy();
  });

  it('navigates once and leaves the detail page as the only runner', async () => {
    mocks.listRoutines.mockResolvedValue([ROUTINE]);
    renderPage();
    await waitFor(() => expect(findRoutineCardHeading()).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: 'Chạy thử ngay' }));

    expect(await screen.findByText('DETAIL PAGE')).toBeTruthy();
  });

  it('does not render historical run results on the overview', async () => {
    renderPage();

    await waitFor(() => expect(screen.queryByTestId('routine-summaries')).toBeNull());
  });

  it('pausing or deleting from the card does not navigate away', async () => {
    mocks.listRoutines.mockResolvedValue([ROUTINE]);
    renderPage();
    await waitFor(() => expect(findRoutineCardHeading()).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: 'Tạm dừng' }));
    await waitFor(() => expect(mocks.updateRoutine).toHaveBeenCalledWith('access-token', 1, { enabled: false }));
    expect(screen.queryByText('DETAIL PAGE')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: 'Xoá routine' }));
    await waitFor(() => expect(mocks.deleteRoutine).toHaveBeenCalledWith('access-token', 1));
    expect(screen.queryByText('DETAIL PAGE')).toBeNull();
  });
});
