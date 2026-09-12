// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MeetingNotesPage } from '../src/pages/MeetingNotesPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  addToast: vi.fn(),
  listMeetingNotes: vi.fn(),
  createMeetingNote: vi.fn(),
  deleteMeetingNote: vi.fn(),
}));

vi.mock('react-router-dom', () => ({ useNavigate: () => mocks.navigate }));
vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) => selector({ accessToken: 'access-token' }),
}));
vi.mock('../src/stores/useAppStore', () => ({ useAppStore: () => ({ addToast: mocks.addToast }) }));
vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'vi',
    t: {
      nav: { meetingNotes: 'Ghi chú cuộc họp' },
      meetingNotes: {
        title: 'Cuộc họp', newNote: 'Ghi chú mới', searchPlaceholder: 'Tìm cuộc họp...',
        emptyTitle: 'Chưa có cuộc họp nào', emptyBody: 'Tạo ghi chú mới.', loading: 'Đang tải...',
        loadFailed: 'Không tải được.', statusOpen: 'Đang ghi', statusSummarized: 'Đã tổng hợp',
        statusStalled: 'Dừng giữa chừng', statusRecorded: 'Đã ghi xong · chưa tổng hợp',
        durationHour: 'giờ', durationMinute: 'phút', durationLessThanMinute: 'dưới 1 phút',
        actionCount: 'việc', openActionCount: 'chờ duyệt', untitled: 'Chưa đặt tên', delete: 'Xoá',
        deleteConfirm: 'Xoá?', deleted: 'Đã xoá.',
      },
    },
  }),
}));
vi.mock('../src/lib/meetingNotesApi', () => ({
  listMeetingNotes: mocks.listMeetingNotes,
  createMeetingNote: mocks.createMeetingNote,
  deleteMeetingNote: mocks.deleteMeetingNote,
}));

describe('MeetingNotesPage', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('creates a blank meeting and opens its editor', async () => {
    mocks.listMeetingNotes.mockResolvedValue({ meetings: [] });
    mocks.createMeetingNote.mockResolvedValue({ id: 21 });
    const user = userEvent.setup();
    render(<MeetingNotesPage />);

    await screen.findByText('Chưa có cuộc họp nào');
    await user.click(screen.getAllByRole('button', { name: 'Ghi chú mới' })[0]);

    await waitFor(() => expect(mocks.createMeetingNote).toHaveBeenCalledWith('access-token'));
    expect(mocks.navigate).toHaveBeenCalledWith('/meeting-notes/21');
  });

  it('hiện giờ bắt đầu, giờ kết thúc và thời lượng của cuộc họp đã ghi xong', async () => {
    // Người dùng nhìn danh sách để nhớ lại cuộc họp nào là cuộc họp nào; chỉ có
    // tên và một mốc giờ thì hai cuộc họp cùng buổi sáng trông y hệt nhau.
    mocks.listMeetingNotes.mockResolvedValue({
      meetings: [
        {
          id: 7,
          title: 'Chốt kế hoạch sprint',
          status: 'summarized',
          startedAt: '2026-08-14T02:00:00Z',
          endedAt: '2026-08-14T03:05:00Z',
          updatedAt: '2026-08-14T03:05:00Z',
          actionItemCount: 3,
          openActionItemCount: 2,
        },
      ],
    });

    render(<MeetingNotesPage />);

    await screen.findByText('Chốt kế hoạch sprint');
    expect(screen.getByText('Đã tổng hợp')).toBeTruthy();
    expect(screen.getByText('1 giờ 05 phút')).toBeTruthy();
    // Giờ hiển thị theo múi giờ máy chạy test nên chỉ khẳng định có đủ hai mốc.
    expect(screen.getByText(/\d{2}:\d{2} – \d{2}:\d{2}/)).toBeTruthy();
  });

  it('cuộc họp mở nhưng im lặng quá lâu không còn hiện là đang ghi', async () => {
    // Extension chết giữa chừng để lại hàng loạt cuộc họp "đang diễn ra" từ
    // những ngày trước — đó chính là thứ làm danh sách mất nghĩa.
    mocks.listMeetingNotes.mockResolvedValue({
      meetings: [
        {
          id: 8,
          title: 'Cuộc họp mới',
          status: 'open',
          startedAt: '2026-08-13T12:00:00Z',
          endedAt: null,
          updatedAt: '2026-08-13T12:30:00Z',
          actionItemCount: 0,
          openActionItemCount: 0,
        },
      ],
    });

    render(<MeetingNotesPage />);

    await screen.findByText('Cuộc họp mới');
    expect(screen.getByText('Dừng giữa chừng')).toBeTruthy();
    expect(screen.getByText('30 phút')).toBeTruthy();
    expect(screen.queryByText('Đang ghi')).toBeNull();
  });
});
