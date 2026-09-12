// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DailyBriefingPage } from '../src/pages/DailyBriefingPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  streamConversationMessage: vi.fn(),
  runVisionAction: vi.fn(),
  fetchConversationDetail: vi.fn(),
  createConversation: vi.fn(),
  createLiveConversation: vi.fn(),
  addMessage: vi.fn(),
  replaceLatestAiMessage: vi.fn(),
  updateProductivityAction: vi.fn(),
  approveProductivityAction: vi.fn(),
  rejectProductivityAction: vi.fn(),
  addToast: vi.fn(),
  requestProductRating: vi.fn(),
  conversationId: undefined as string | undefined,
  activeConversation: undefined as unknown,
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useParams: () => ({ conversationId: mocks.conversationId }),
    useLocation: () => ({ pathname: '/briefing', state: null }),
  };
});

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({
    language: 'vi',
    t: {
      briefing: {
        askMondaiy: 'Hỏi mondaiy',
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
    getConversation: () => mocks.activeConversation,
    fetchConversationDetail: mocks.fetchConversationDetail,
    createConversation: mocks.createConversation,
    createLiveConversation: mocks.createLiveConversation,
    setServerConversationId: vi.fn(),
    addMessage: mocks.addMessage,
    updateFeedback: vi.fn(),
    renameConversation: vi.fn(),
    deleteConversation: vi.fn(),
    replaceLatestAiMessage: mocks.replaceLatestAiMessage,
    updateProductivityAction: mocks.updateProductivityAction,
    setConversationGenerating: vi.fn(),
  }),
}));

vi.mock('../src/lib/conversationApi', () => ({
  streamConversationMessage: mocks.streamConversationMessage,
  approveProductivityAction: mocks.approveProductivityAction,
  rejectProductivityAction: mocks.rejectProductivityAction,
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

vi.mock('../src/lib/visionApi', () => ({
  runVisionAction: mocks.runVisionAction,
}));

vi.mock('../src/hooks/useProductRating', () => ({
  recordMeaningfulAction: vi.fn(),
  requestProductRating: mocks.requestProductRating,
}));

describe('DailyBriefingPage vision image task suggestions', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.setItem('mondaiy.atAGlanceOpen', 'false');
    mocks.createConversation.mockResolvedValue('91');
    mocks.createLiveConversation.mockReturnValue('local-91');
    mocks.conversationId = undefined;
    mocks.activeConversation = undefined;
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('carries taskSuggestions and warnings from a pasted-image reply onto the chat message', async () => {
    mocks.runVisionAction.mockResolvedValue({
      actionType: 'task',
      response: 'Bạn có 2 buổi thi trong tuần này.',
      analysis: '',
      sources: [],
      taskSuggestions: [
        { title: 'Ôn thi Toán', detail: 'Thi giữa kỳ', dueAt: '2026-08-20T09:00:00+07:00', allDay: false, source: 'vision' },
      ],
      calendarSuggestions: [],
      warnings: ['Không đọc được ngày ở góc dưới ảnh.'],
      visualContextUsed: true,
    });

    render(<DailyBriefingPage />);

    // Dán ảnh vào ô nhập bằng cách bắn sự kiện paste chứa file ảnh.
    const textarea = screen.getByPlaceholderText('Hỏi mondaiy');
    const file = new File(['fake'], 'lich-thi.png', { type: 'image/png' });
    const pasteEvent = Object.assign(new Event('paste', { bubbles: true, cancelable: true }), {
      clipboardData: {
        items: [{ type: 'image/png', kind: 'file', getAsFile: () => file }],
      },
    });
    Object.defineProperty(global, 'FileReader', {
      writable: true,
      value: class {
        onload: ((ev: unknown) => void) | null = null;
        result: string = 'data:image/png;base64,ZmFrZQ==';
        readAsDataURL() {
          this.onload?.({ target: this });
        }
      },
    });
    textarea.dispatchEvent(pasteEvent);

    await waitFor(() => expect(screen.getByAltText('Ảnh chuẩn bị gửi')).toBeTruthy());

    await userEvent.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => {
      expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
        '91',
        'Bạn có 2 buổi thi trong tuần này.',
        {
          taskSuggestions: [
            { title: 'Ôn thi Toán', detail: 'Thi giữa kỳ', dueAt: '2026-08-20T09:00:00+07:00', allDay: false, source: 'vision' },
          ],
        },
      );
    });
    expect(mocks.addToast).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'info', message: 'Không đọc được ngày ở góc dưới ảnh.' }),
    );
  });

  it('renders ChatTaskSuggestionCard for a stored message carrying vision-sourced taskSuggestions', () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Lịch thi tuần này',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        {
          id: 'user-1',
          sender: 'user',
          text: '📷 Ảnh đã gửi',
          timestamp: 'Just now',
        },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn có 2 buổi thi trong tuần này.',
          timestamp: 'Just now',
          taskSuggestions: [
            { title: 'Ôn thi Toán', detail: 'Thi giữa kỳ', dueAt: '2026-08-20T09:00:00+07:00', allDay: false, source: 'vision' },
          ],
        },
      ],
    };

    render(<DailyBriefingPage />);

    screen.getByText('Ôn thi Toán');
  });
});
