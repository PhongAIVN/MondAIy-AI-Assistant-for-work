// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RoutineDetailPage } from '../src/pages/RoutineDetailPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  addToast: vi.fn(),
  getRoutine: vi.fn(),
  listRoutineRuns: vi.fn(),
  runRoutineNow: vi.fn(),
  updateRoutine: vi.fn(),
  deleteRoutine: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({ routineId: '1' }),
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
    getRoutine: mocks.getRoutine,
    listRoutineRuns: mocks.listRoutineRuns,
    runRoutineNow: mocks.runRoutineNow,
    updateRoutine: mocks.updateRoutine,
    deleteRoutine: mocks.deleteRoutine,
  };
});

const ROUTINE = {
  id: 1,
  name: "Don't Let Me Drop the Ball",
  instructions: 'Kiểm tra việc quá hạn.',
  frequency: 'daily' as const,
  hour: 8,
  dayOfWeek: null,
  dayOfMonth: null,
  timezone: 'Asia/Ho_Chi_Minh',
  enabled: true,
  notifyPush: true,
  notifyEmail: false,
  lastRunDate: '2026-08-14',
};

const OLDER_RUN = {
  id: 2,
  routineId: 1,
  status: 'done' as const,
  outputText: 'Có 1 việc quá hạn hôm qua.',
  outputJson: null,
  errorMessage: null,
  startedAt: '2026-08-13T11:48:00Z',
  finishedAt: '2026-08-13T11:48:07Z',
};

const AUTO_RUN_RESULT = {
  id: 3,
  routineId: 1,
  status: 'done' as const,
  outputText: 'Mọi thứ trong tầm kiểm soát.',
  outputJson: null,
  errorMessage: null,
  startedAt: '2026-08-14T11:48:00Z',
  finishedAt: '2026-08-14T11:48:07Z',
};

beforeEach(() => {
  mocks.navigate.mockReset();
  mocks.addToast.mockReset();
  mocks.getRoutine.mockReset().mockResolvedValue(ROUTINE);
  mocks.listRoutineRuns.mockReset().mockResolvedValue([AUTO_RUN_RESULT, OLDER_RUN]);
  // Chính sách 2026-08-25: mở trang KHÔNG tự chạy nữa — hiển thị run đã lưu
  // mới nhất; runRoutineNow chỉ gọi khi người dùng bấm "Chạy ngay" tường minh.
  mocks.runRoutineNow.mockReset().mockResolvedValue(AUTO_RUN_RESULT);
  mocks.updateRoutine.mockReset().mockImplementation(async (_t: string, _id: number, patch: Record<string, unknown>) => ({
    ...ROUTINE,
    ...patch,
  }));
  mocks.deleteRoutine.mockReset().mockResolvedValue(undefined);
});

afterEach(cleanup);

describe('RoutineDetailPage — mở trang hiển thị run đã lưu', () => {
  it('không tự chạy khi mở trang: hiện ngay nội dung run mới nhất đã lưu', async () => {
    render(<RoutineDetailPage />);

    await screen.findByText("Don't Let Me Drop the Ball");
    const content = await screen.findByTestId('routine-run-content');
    // Run đã lưu trong DB hiện ngay, không có trạng thái generating.
    expect(await within(content).findByText('Mọi thứ trong tầm kiểm soát.')).toBeTruthy();
    expect(within(content).queryByText('Đang tạo ghi chú của bạn...')).toBeNull();
    expect(mocks.runRoutineNow).not.toHaveBeenCalled();
  });

  it('chỉ chạy lại khi người dùng bấm "Chạy ngay" tường minh', async () => {
    render(<RoutineDetailPage />);
    const content = await screen.findByTestId('routine-run-content');
    await waitFor(() => expect(within(content).getByText('Mọi thứ trong tầm kiểm soát.')).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: 'Chạy ngay' }));
    await waitFor(() => expect(mocks.runRoutineNow).toHaveBeenCalledTimes(1));
  });
});

describe('RoutineDetailPage — reviewing runs', () => {
  it('can switch back to an older run from history', async () => {
    render(<RoutineDetailPage />);
    const content = await screen.findByTestId('routine-run-content');
    await waitFor(() => expect(within(content).getByText('Mọi thứ trong tầm kiểm soát.')).toBeTruthy());

    await userEvent.click(screen.getByText(/Có 1 việc quá hạn hôm qua\./));

    expect(within(content).getByText('Có 1 việc quá hạn hôm qua.')).toBeTruthy();
    expect(within(content).queryByText('Mọi thứ trong tầm kiểm soát.')).toBeNull();
  });

  it('lets the user manually trigger another run on top of the saved result', async () => {
    render(<RoutineDetailPage />);
    const initialContent = await screen.findByTestId('routine-run-content');
    await waitFor(() => expect(within(initialContent).getByText('Mọi thứ trong tầm kiểm soát.')).toBeTruthy());

    mocks.runRoutineNow.mockResolvedValue({ ...AUTO_RUN_RESULT, id: 4, outputText: 'Kết quả chạy lại thủ công.' });
    await userEvent.click(screen.getByRole('button', { name: 'Chạy ngay' }));

    const content = screen.getByTestId('routine-run-content');
    expect(await within(content).findByText('Kết quả chạy lại thủ công.')).toBeTruthy();
  });

  it('shows a not-found state instead of a blank page when the routine cannot be loaded', async () => {
    mocks.getRoutine.mockRejectedValue(new Error('404'));
    render(<RoutineDetailPage />);

    expect((await screen.findByRole('alert')).textContent).toContain('Không tìm thấy routine');
    expect(mocks.runRoutineNow).not.toHaveBeenCalled();
  });

  it('deletes the routine and navigates back to the list', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<RoutineDetailPage />);
    await screen.findByText("Don't Let Me Drop the Ball");

    await userEvent.click(screen.getByRole('button', { name: 'Xoá routine' }));

    await waitFor(() => expect(mocks.deleteRoutine).toHaveBeenCalledWith('access-token', 1));
    expect(mocks.navigate).toHaveBeenCalledWith('/routines');
  });
});
