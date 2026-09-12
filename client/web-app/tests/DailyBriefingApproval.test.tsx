// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DailyBriefingPage } from '../src/pages/DailyBriefingPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  updateAction: vi.fn(),
  addToast: vi.fn(),
  proposal: {
    status: 'pending_approval' as const,
    kind: 'calendar_event' as const,
    approval_id: 'approval-1',
    message: 'Chờ duyệt',
    draft: {
      title: 'Workshop',
      starts_at: '2026-08-11T20:00:00+07:00',
      ends_at: '2026-08-11T22:00:00+07:00',
    },
  },
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useParams: () => ({ conversationId: '91' }),
    useLocation: () => ({ pathname: '/briefing/conversation/91', state: null }),
  };
});

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'vi',
    t: {
      briefing: {
        askMondaiy: 'Hỏi mondaiy',
        disclaimer: 'mondaiy có thể mắc sai sót. Hãy kiểm tra lại thông tin quan trọng.',
        whatChanged: 'Thay đổi',
        whyItMatters: 'Tại sao quan trọng',
        recommendedNextStep: 'Bước tiếp theo',
        atAGlance: { showPanel: 'Hiện tổng quan', title: 'Tổng quan' },
      },
    },
  }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ openModal: vi.fn(), addToast: mocks.addToast }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useConversationStore', () => ({
  useConversationStore: () => ({
    conversations: [],
    getConversation: () => ({
      id: '91',
      title: 'Thêm workshop',
      dateGroup: 'today',
      lastUpdated: 'Vừa xong',
      messagesLoaded: true,
      messageCount: 1,
      messages: [
        {
          id: 'assistant-1',
          sender: 'ai',
          text: 'Hãy kiểm tra và bấm Chấp nhận để thực hiện.',
          timestamp: 'Vừa xong',
          serverMessageId: 44,
          productivityAction: mocks.proposal,
        },
      ],
    }),
    fetchConversationDetail: vi.fn(),
    createLiveConversation: vi.fn(),
    setServerConversationId: vi.fn(),
    addMessage: vi.fn(),
    updateFeedback: vi.fn(),
    renameConversation: vi.fn(),
    deleteConversation: vi.fn(),
    replaceLatestAiMessage: vi.fn(),
    updateProductivityAction: mocks.updateAction,
    setConversationGenerating: vi.fn(),
  }),
}));

vi.mock('../src/lib/conversationApi', () => ({
  createServerConversation: vi.fn(),
  streamConversationMessage: vi.fn(),
  approveProductivityAction: mocks.approve,
  rejectProductivityAction: mocks.reject,
}));

vi.mock('../src/lib/gmailApi', () => ({
  isGmailBriefingIntent: () => false,
  getConnections: vi.fn(),
  getGmailSources: vi.fn(),
  getGmailStatus: vi.fn(),
  getIntegrations: vi.fn(),
}));

vi.mock('../src/lib/runApi', () => ({
  createGmailRun: vi.fn(),
  extractGmailDateRange: vi.fn(),
  getRunBrief: vi.fn(),
  streamRunEvents: vi.fn(),
  waitForRun: vi.fn(),
}));

vi.mock('../src/hooks/useProductRating', () => ({ recordMeaningfulAction: vi.fn() }));

describe('DailyBriefingPage productivity approval', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.setItem('mondaiy.atAGlanceOpen', 'false');
    mocks.approve.mockResolvedValue({
      ...mocks.proposal,
      status: 'created',
      message: 'Đã thêm Workshop vào Google Calendar.',
      result: { calendar_event_id: 'event-1' },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('executes the stored action only after the user presses approve', async () => {
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.click(screen.getByRole('button', { name: 'Chấp nhận' }));

    await waitFor(() => {
      expect(mocks.approve).toHaveBeenCalledWith(91, 44, 'access-token');
    });
    expect(mocks.updateAction).toHaveBeenCalledWith(
      '91',
      'assistant-1',
      expect.objectContaining({ status: 'created' }),
    );
    expect(mocks.reject).not.toHaveBeenCalled();
  });

  it('shows a friendly toast instead of the raw backend error when approval fails', async () => {
    const user = userEvent.setup();
    mocks.approve.mockRejectedValueOnce(
      new Error('Google Calendar API lỗi 400 khi tạo sự kiện'),
    );
    render(<DailyBriefingPage />);

    await user.click(screen.getByRole('button', { name: 'Chấp nhận' }));

    await waitFor(() => {
      expect(mocks.addToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          message: 'Không thực hiện được thao tác này. Kiểm tra lại thông tin rồi thử lại.',
        }),
      );
    });
    const rawMessageShown = mocks.addToast.mock.calls.some(([toast]) =>
      String(toast.message).includes('Google Calendar API lỗi'),
    );
    expect(rawMessageShown).toBe(false);
  });

  it('shows the AI-mistakes disclaimer under the active chat composer', () => {
    render(<DailyBriefingPage />);

    expect(
      screen.getByText('mondaiy có thể mắc sai sót. Hãy kiểm tra lại thông tin quan trọng.'),
    ).toBeTruthy();
  });

  it('reveals the scroll-to-bottom button only after scrolling away from the latest message', () => {
    const main = document.createElement('main');
    document.body.appendChild(main);
    const container = document.createElement('div');
    main.appendChild(container);

    render(<DailyBriefingPage />, { container });

    expect(screen.queryByLabelText('Về tin nhắn mới nhất')).toBeNull();

    Object.defineProperty(main, 'scrollHeight', { value: 1000, configurable: true });
    Object.defineProperty(main, 'clientHeight', { value: 400, configurable: true });
    Object.defineProperty(main, 'scrollTop', { value: 0, configurable: true, writable: true });
    fireEvent.scroll(main);

    const scrollButton = screen.getByLabelText('Về tin nhắn mới nhất');
    expect(scrollButton).toBeTruthy();

    scrollButton.click();
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();

    main.remove();
  });
});
