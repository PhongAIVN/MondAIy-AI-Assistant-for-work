// @vitest-environment jsdom

import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MeetingNoteDetailPage } from '../src/pages/MeetingNoteDetailPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  addToast: vi.fn(),
  getMeetingNote: vi.fn(),
  updateMeetingNote: vi.fn(),
  endMeetingNote: vi.fn(),
  acceptActionItem: vi.fn(),
  dismissActionItem: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({ noteId: '12' }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ addToast: mocks.addToast }),
}));

const meetingCopy = {
  loading: 'Đang tải cuộc họp...',
  loadFailed: 'Không tải được danh sách cuộc họp.',
  backToList: 'Tất cả cuộc họp',
  saving: 'Đang lưu...',
  saved: 'Đã lưu',
  saveFailed: 'Chưa lưu được.',
  endMeeting: 'Kết thúc cuộc họp',
  ending: 'Đang tổng hợp...',
  endEmpty: 'Cần có ghi chú.',
  endFailed: 'Không tổng hợp được.',
  titlePlaceholder: 'Tên cuộc họp',
  tabNotes: 'Ghi chú của bạn',
  tabTranscript: 'Transcript',
  tabSummary: 'Tổng hợp',
  statusOpen: 'Đang diễn ra',
  statusSummarized: 'Đã tổng hợp',
  endedAt: 'Kết thúc lúc',
  lockedAfterEnd: 'Chỉ đọc',
  notesPlaceholder: 'Gõ ghi chú trong lúc họp...',
  transcriptPlaceholder: 'Dán transcript cuộc họp vào đây...',
  notEndedYet: 'Kết thúc để tổng hợp.',
  summaryHeading: 'Tóm tắt',
  noSummary: 'Không có tóm tắt.',
  decisionsHeading: 'Quyết định đã chốt',
  noDecisions: 'Không có quyết định.',
  actionsHeading: 'Việc cần làm',
  noActions: 'Không có việc.',
  accepted: 'Đã tạo việc',
  dismissed: 'Đã bỏ qua',
  assigneeUnknown: 'Chưa rõ ai phụ trách',
  assignee: 'Người phụ trách',
  timeAmbiguous: 'Thời gian chưa rõ',
  timeUnknown: 'Không nhắc hạn',
  evidence: 'Trích từ cuộc họp',
  accept: 'Tạo việc',
  dismiss: 'Bỏ qua',
  taskCreated: 'Đã tạo việc.',
  acceptFailed: 'Không tạo được việc.',
  dismissFailed: 'Không bỏ qua được.',
  openTask: 'Xem trong Công việc của tôi',
};

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: { meetingNotes: meetingCopy }, language: 'vi' }),
}));

vi.mock('../src/lib/meetingNotesApi', () => ({
  getMeetingNote: mocks.getMeetingNote,
  updateMeetingNote: mocks.updateMeetingNote,
  endMeetingNote: mocks.endMeetingNote,
  acceptActionItem: mocks.acceptActionItem,
  dismissActionItem: mocks.dismissActionItem,
}));

vi.mock('../src/hooks/useProductRating', () => ({ recordMeaningfulAction: vi.fn() }));

const openMeeting = {
  id: 12,
  title: 'Standup',
  notes: '',
  transcript: '',
  status: 'open' as const,
  summary: '',
  decisions: '',
  startedAt: '2026-08-12T08:00:00+07:00',
  endedAt: null,
  createdAt: '2026-08-12T08:00:00+07:00',
  updatedAt: '2026-08-12T08:00:00+07:00',
  actionItems: [],
};

describe('MeetingNoteDetailPage', () => {
  beforeEach(() => {
    mocks.getMeetingNote.mockResolvedValue(openMeeting);
    mocks.updateMeetingNote.mockResolvedValue(openMeeting);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('merges rapid edits from different fields into one autosave payload', async () => {
    vi.useFakeTimers();
    render(<MeetingNoteDetailPage />);
    await act(async () => Promise.resolve());

    fireEvent.change(screen.getByPlaceholderText('Tên cuộc họp'), { target: { value: 'Sprint sync' } });
    fireEvent.change(screen.getByPlaceholderText('Gõ ghi chú trong lúc họp...'), {
      target: { value: 'An gửi báo cáo.' },
    });
    expect(mocks.updateMeetingNote).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(901);
      await Promise.resolve();
    });

    expect(mocks.updateMeetingNote).toHaveBeenCalledOnce();
    expect(mocks.updateMeetingNote).toHaveBeenCalledWith(12, 'access-token', {
      title: 'Sprint sync',
      notes: 'An gửi báo cáo.',
    });
  });

  it('saves current text before ending and renders grounded action controls', async () => {
    const summarized = {
      ...openMeeting,
      status: 'summarized' as const,
      summary: 'Đã chốt báo cáo.',
      decisions: 'An phụ trách báo cáo',
      endedAt: '2026-08-12T09:00:00+07:00',
      actionItems: [{
        id: 3,
        title: 'Gửi báo cáo',
        detail: '',
        assignee: 'An',
        assigneeAmbiguous: false,
        timeExpression: '',
        dueAt: null,
        allDay: false,
        ambiguous: false,
        evidenceQuote: 'An gửi báo cáo',
        status: 'suggested' as const,
        taskId: null,
      }],
    };
    mocks.endMeetingNote.mockResolvedValue(summarized);
    mocks.acceptActionItem.mockResolvedValue({ id: 44, status: 'proposed' });
    const user = userEvent.setup();
    render(<MeetingNoteDetailPage />);
    await screen.findByDisplayValue('Standup');

    await user.type(screen.getByPlaceholderText('Gõ ghi chú trong lúc họp...'), 'An gửi báo cáo');
    await user.click(screen.getByRole('button', { name: 'Kết thúc cuộc họp' }));

    await waitFor(() => expect(mocks.endMeetingNote).toHaveBeenCalledWith(12, 'access-token'));
    expect(mocks.updateMeetingNote).toHaveBeenCalledWith(12, 'access-token', {
      title: 'Standup',
      notes: 'An gửi báo cáo',
      transcript: '',
    });
    expect(await screen.findByText('Đã chốt báo cáo.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Tạo việc' }));
    await waitFor(() => expect(mocks.acceptActionItem).toHaveBeenCalledWith(12, 3, 'access-token'));
  });
});
