// @vitest-environment jsdom

import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
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

// Bản sao rút gọn của phần copy tiếng Việt, chỉ giữ các nhãn mà test cần khẳng
// định. Mock i18n để test không vỡ khi văn phong trong translations.ts đổi.
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
  transcriptEmpty: 'Chưa có nội dung cuộc họp.',
  transcriptEmptyHint: 'Bạn có thể ghi âm qua extension, hoặc dán transcript thủ công vào ô bên dưới.',
  transcriptUnparsed: 'Dòng chưa nhận dạng được — giữ nguyên văn',
  transcriptRawToggle: 'Sửa transcript nguyên văn',
  liveStart: 'Đang ghi — tự cập nhật',
  liveStop: 'Dừng tự cập nhật',
  liveLastSynced: 'Cập nhật lúc',
  liveFailed: 'Không lấy được nội dung mới.',
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

/** Ba lượt nói đúng định dạng backend append vào trong lúc ghi âm. */
const threeTurns = [
  '[00:20] Tôi: mình sẽ deploy cái endpoint tasks trước thứ năm',
  '[00:41] Người khác: ok để anh xem lại phần schema',
  '[01:05] Tôi: vậy chốt thứ năm nhé',
].join('\n');

/** Render trang và chờ lần tải đầu xong, rồi mở sang tab transcript. */
const renderTranscriptTab = async (transcript: string) => {
  mocks.getMeetingNote.mockResolvedValue({ ...openMeeting, transcript });
  render(<MeetingNoteDetailPage />);
  await act(async () => {
    await Promise.resolve();
  });
  fireEvent.click(screen.getByRole('button', { name: 'Transcript' }));
};

describe('MeetingNoteDetailPage transcript', () => {
  beforeEach(() => {
    mocks.getMeetingNote.mockResolvedValue(openMeeting);
    mocks.updateMeetingNote.mockResolvedValue(openMeeting);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('renders one bubble per speaker turn, labelled but without a timestamp chip', async () => {
    await renderTranscriptTab(threeTurns);

    expect(screen.getAllByText('Tôi')).toHaveLength(2);
    expect(screen.getByText('Người khác')).toBeTruthy();
    expect(screen.getByText('mình sẽ deploy cái endpoint tasks trước thứ năm')).toBeTruthy();
    expect(screen.getByText('ok để anh xem lại phần schema')).toBeTruthy();
    // Mốc giờ chỉ còn trong nguyên văn, không bày ra mặt đọc.
    expect(screen.queryByText('00:20')).toBeNull();
    expect(screen.queryByText('01:05')).toBeNull();
  });

  it('keeps the raw transcript editor collapsed instead of repeating the text below', async () => {
    await renderTranscriptTab(threeTurns);

    const toggle = screen.getByText('Sửa transcript nguyên văn');
    const editor = toggle.closest('details');
    expect(editor).not.toBeNull();
    expect(editor?.open).toBe(false);

    // Mở ra thì vẫn sửa được nguyên văn — thu gọn chứ không bỏ.
    fireEvent.click(toggle);
    expect(screen.getByPlaceholderText('Dán transcript cuộc họp vào đây...')).toBeTruthy();
  });

  it('keeps a malformed line visible verbatim instead of dropping it', async () => {
    const brokenLine = 'ghi chú rời không có mốc giờ';
    await renderTranscriptTab(`${threeTurns}\n${brokenLine}`);

    expect(screen.getByText(brokenLine)).toBeTruthy();
    expect(screen.getByText('Dòng chưa nhận dạng được — giữ nguyên văn')).toBeTruthy();
  });

  it('shows the empty state when the transcript has no content', async () => {
    await renderTranscriptTab('');

    expect(screen.getByText('Chưa có nội dung cuộc họp.')).toBeTruthy();
    expect(
      screen.getByText('Bạn có thể ghi âm qua extension, hoặc dán transcript thủ công vào ô bên dưới.'),
    ).toBeTruthy();
  });

  it('merges consecutive lines from the same speaker into one growing turn', async () => {
    // Extension cắt chunk 5 giây nên một mạch nói dài về thành nhiều dòng liền
    // nhau; người đọc phải thấy một đoạn văn, không phải bốn bong bóng vụn.
    await renderTranscriptTab(
      [
        '[00:05] Tôi: mình sẽ deploy',
        '[00:10] Tôi: cái endpoint tasks',
        '[00:15] Tôi: trước thứ năm',
        '[00:20] Người khác: ok để anh xem lại',
      ].join('\n'),
    );

    expect(screen.getAllByText('Tôi')).toHaveLength(1);
    expect(screen.getByText('mình sẽ deploy cái endpoint tasks trước thứ năm')).toBeTruthy();
    // Người khác xen vào thì phải là một lượt riêng.
    expect(screen.getByText('ok để anh xem lại')).toBeTruthy();
  });

  it('keeps a long silence between two lines of the same speaker as separate turns', async () => {
    await renderTranscriptTab(
      ['[00:05] Tôi: mình sẽ deploy', '[02:00] Tôi: quay lại chuyện lúc nãy'].join('\n'),
    );

    expect(screen.getAllByText('Tôi')).toHaveLength(2);
    expect(screen.getByText('mình sẽ deploy')).toBeTruthy();
    expect(screen.getByText('quay lại chuyện lúc nãy')).toBeTruthy();
  });

  it('refetches the note about every second and a half while auto refresh is on', async () => {
    vi.useFakeTimers();
    mocks.getMeetingNote.mockResolvedValue({ ...openMeeting, transcript: threeTurns });
    render(<MeetingNoteDetailPage />);
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Transcript' }));
    expect(mocks.getMeetingNote).toHaveBeenCalledTimes(1);

    const grown = `${threeTurns}\n[01:30] Người khác: anh gửi lại schema chiều nay`;
    mocks.getMeetingNote.mockResolvedValue({ ...openMeeting, transcript: grown });
    fireEvent.click(screen.getByRole('button', { name: 'Đang ghi — tự cập nhật' }));

    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    expect(mocks.getMeetingNote).toHaveBeenCalledTimes(2);
    expect(screen.getByText('anh gửi lại schema chiều nay')).toBeTruthy();
    expect(screen.getByText(/Cập nhật lúc/)).toBeTruthy();
  });

  it('follows a meeting that is still recording without waiting for a click', async () => {
    vi.useFakeTimers();
    // `updatedAt` là ngay bây giờ nên cuộc họp còn ở pha "đang ghi".
    const liveMeeting = {
      ...openMeeting,
      transcript: threeTurns,
      updatedAt: new Date().toISOString(),
    };
    mocks.getMeetingNote.mockResolvedValue(liveMeeting);
    render(<MeetingNoteDetailPage />);
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Transcript' }));

    const grown = `${threeTurns}\n[01:30] Người khác: anh gửi lại schema chiều nay`;
    mocks.getMeetingNote.mockResolvedValue({ ...liveMeeting, transcript: grown });
    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });

    expect(mocks.getMeetingNote).toHaveBeenCalledTimes(2);
    expect(screen.getByText('anh gửi lại schema chiều nay')).toBeTruthy();
  });

  it('clears the polling interval on unmount so no request fires afterwards', async () => {
    vi.useFakeTimers();
    mocks.getMeetingNote.mockResolvedValue({ ...openMeeting, transcript: threeTurns });
    const view = render(<MeetingNoteDetailPage />);
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Transcript' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đang ghi — tự cập nhật' }));

    await act(async () => {
      vi.advanceTimersByTime(1500);
      await Promise.resolve();
    });
    expect(mocks.getMeetingNote).toHaveBeenCalledTimes(2);

    view.unmount();
    await act(async () => {
      vi.advanceTimersByTime(20000);
      await Promise.resolve();
    });

    expect(mocks.getMeetingNote).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });
});
