// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DailyBriefingPage } from '../src/pages/DailyBriefingPage';
import { AgentStreamError } from '../src/lib/agentStream';
import { translations } from '../src/i18n/translations';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  streamConversationMessage: vi.fn(),
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
  triggerChatSync: vi.fn(),
  listTasks: vi.fn(),
  isGmailBriefingIntent: vi.fn(),
  getGmailStatus: vi.fn(),
  getConnections: vi.fn(),
  getGmailSources: vi.fn(),
  getIntegrations: vi.fn(),
  createGmailRun: vi.fn(),
  extractGmailDateRange: vi.fn(),
  getRunBrief: vi.fn(),
  waitForRun: vi.fn(),
  conversationId: undefined as string | undefined,
  activeConversation: undefined as unknown,
  location: { pathname: '/briefing', state: null as unknown },
  pipelineState: {
    connections: [],
    connectionsLoaded: true,
    connectionsLoading: false,
    connectionsError: null,
  },
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useParams: () => ({ conversationId: mocks.conversationId }),
    useLocation: () => mocks.location,
  };
});

vi.mock('../src/i18n/useTranslation', async () => {
  const { translations } = await import('../src/i18n/translations');
  return {
    useTranslation: () => ({
      language: 'vi',
      t: {
        ...translations.vi,
        briefing: {
          ...translations.vi.briefing,
          askMondaiy: 'Hỏi mondaiy',
          disclaimer: 'mondaiy có thể mắc sai sót. Hãy kiểm tra lại thông tin quan trọng.',
          atAGlance: {
            ...translations.vi.briefing.atAGlance,
            showPanel: 'Hiện tổng quan',
            title: 'Tổng quan',
          },
        },
      },
    }),
  };
});

vi.mock('../src/lib/runsApi', () => ({
  // Trang chat nay tự kéo đồng bộ trước khi hỏi agent (nút Sync tay đã ẩn).
  // Mặc định trả "không cần đồng bộ" để các test ở file này vẫn kiểm đúng thứ
  // chúng quan tâm: câu hỏi có đi qua agent SSE thật hay không.
  triggerChatSync: mocks.triggerChatSync,
  streamRunEvents: vi.fn(),
}));

vi.mock('../src/lib/tasksApi', () => ({
  listCalendarEvents: vi.fn().mockResolvedValue({ events: [] }),
  listTasks: mocks.listTasks,
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({ openModal: vi.fn(), addToast: mocks.addToast }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: () => ({ accessToken: 'access-token', user: { id: 'u1' } }),
}));

vi.mock('../src/stores/usePipelineRunStore', () => ({
  usePipelineRunStore: (selector: (state: typeof mocks.pipelineState) => unknown) => selector(mocks.pipelineState),
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
  isGmailBriefingIntent: mocks.isGmailBriefingIntent,
  getConnections: mocks.getConnections,
  getGmailSources: mocks.getGmailSources,
  getGmailStatus: mocks.getGmailStatus,
  getIntegrations: mocks.getIntegrations,
}));

vi.mock('../src/lib/runApi', () => ({
  createGmailRun: mocks.createGmailRun,
  extractGmailDateRange: mocks.extractGmailDateRange,
  getRunBrief: mocks.getRunBrief,
  streamRunEvents: vi.fn(),
  waitForRun: mocks.waitForRun,
}));

vi.mock('../src/hooks/useProductRating', () => ({
  recordMeaningfulAction: vi.fn(),
  requestProductRating: mocks.requestProductRating,
}));

describe('DailyBriefingPage live streaming', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    localStorage.setItem('mondaiy.atAGlanceOpen', 'false');
    mocks.createConversation.mockResolvedValue('91');
    mocks.triggerChatSync.mockResolvedValue({ triggered: false, reason: 'recent_enough', run: null });
    mocks.listTasks.mockResolvedValue({ tasks: [] });
    mocks.isGmailBriefingIntent.mockReturnValue(false);
    mocks.getConnections.mockResolvedValue([{ provider: 'google', connected: true }]);
    mocks.getIntegrations.mockResolvedValue([{ id: 7, provider: 'google' }]);
    mocks.getGmailSources.mockResolvedValue([{ id: 'INBOX', name: 'Inbox', itemCount: 0 }]);
    mocks.extractGmailDateRange.mockReturnValue(null);
    mocks.createGmailRun.mockResolvedValue({ id: 42, status: 'queued', errorMessage: null });
    mocks.waitForRun.mockResolvedValue(undefined);
    mocks.getRunBrief.mockResolvedValue({ summary: 'summary', evidence: [] });
    mocks.createLiveConversation.mockReturnValue('local-91');
    mocks.conversationId = undefined;
    mocks.activeConversation = undefined;
    mocks.location = { pathname: '/briefing', state: null };
    mocks.pipelineState = {
      connections: [],
      connectionsLoaded: true,
      connectionsLoading: false,
      connectionsError: null,
    };
    localStorage.removeItem('mondaiy.no-data-invite-dismissed.v1.u1');
    mocks.streamConversationMessage.mockImplementation(async (_id, _message, _token, handlers) => {
      handlers.onProgress?.({ phase: 'thinking' });
      handlers.onProgress?.({ phase: 'responding' });
      handlers.onToken('Câu trả lời thật');
      handlers.onDone?.({
        response: 'Câu trả lời thật',
        analysis: '',
        taskDrafts: [],
        taskBacklogCount: 4,
        taskSuggestions: [],
      });
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('mời ba cách khởi đầu khi chưa có nguồn và chưa có task', async () => {
    render(<DailyBriefingPage />);
    expect(await screen.findByTestId('cold-start-invites')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Gửi ảnh thời khoá biểu / lịch trình của bạn' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Hôm nay bạn có việc gì cần tôi nhắc không?' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Giúp mondaiy hiểu điều gì quan trọng với tôi' })).toBeTruthy();
    expect(mocks.createConversation).not.toHaveBeenCalled();
    expect(mocks.streamConversationMessage).not.toHaveBeenCalled();
  });

  it.each([
    [[0, 4], 'Đã khuya rồi', 'Nếu có thể, hãy dừng công việc, hạ ánh sáng màn hình và nghỉ ngơi. Việc còn lại có thể ghi nhanh để xử lý sau.'],
    [[5, 8], 'Chào buổi sáng', 'Uống một cốc nước, chuẩn bị bữa sáng hoặc vận động nhẹ trước khi bắt đầu ngày.'],
    [[9, 11], 'Buổi sáng của bạn thế nào?', 'Chọn một việc quan trọng cho phiên tập trung đầu tiên, rồi cho mắt nghỉ một nhịp.'],
    [[12, 13], 'Chào buổi trưa', 'Tạm rời màn hình để ăn trưa và nghỉ ngắn trước buổi chiều.'],
    [[14, 17], 'Chào buổi chiều', 'Chọn một phiên tập trung vừa sức; nhớ đứng dậy và uống nước giữa các phiên.'],
    [[18, 21], 'Chào buổi tối', 'Khép lại việc hôm nay, ăn tối hoặc đi bộ nhẹ, rồi ghi một ưu tiên cho ngày mai.'],
    [[22, 23], 'Sắp hết ngày rồi', 'Đã muộn; hãy cất công việc, giảm ánh sáng màn hình và chuẩn bị nghỉ thay vì làm tiếp.'],
  ])('hiện ngay lời chào và routine tĩnh cho hai biên giờ %j', async (hours, greeting, routine) => {
    vi.useFakeTimers({ toFake: ['Date'] });
    for (const hour of hours as number[]) {
      vi.setSystemTime(new Date(2026, 7, 29, hour, 0, 0));
      const view = render(<DailyBriefingPage />);
      expect(await screen.findByText(greeting as string)).toBeTruthy();
      expect(screen.getByText(routine as string)).toBeTruthy();
      expect(mocks.createConversation).not.toHaveBeenCalled();
      expect(mocks.streamConversationMessage).not.toHaveBeenCalled();
      view.unmount();
    }
  });

  it('không mời cold-start khi người dùng đã có task', async () => {
    mocks.listTasks.mockResolvedValueOnce({
      tasks: [{ id: 1, title: 'Đã có việc', status: 'completed', updatedAt: '2026-08-27T10:00:00Z', dueAt: null }],
    });
    render(<DailyBriefingPage />);
    await waitFor(() => expect(mocks.listTasks).toHaveBeenCalled());
    expect(screen.queryByTestId('cold-start-invites')).toBeNull();
  });

  it('nút gửi ảnh mở file picker và đưa ảnh qua cùng preview của acceptImageFile', async () => {
    render(<DailyBriefingPage />);
    await screen.findByTestId('cold-start-invites');
    const input = screen.getByLabelText('Chọn ảnh thời khoá biểu hoặc lịch trình') as HTMLInputElement;
    const click = vi.spyOn(input, 'click');
    await userEvent.click(screen.getByRole('button', { name: 'Gửi ảnh' }));
    expect(click).toHaveBeenCalled();
    const file = new File(['fake'], 'schedule.png', { type: 'image/png' });
    Object.defineProperty(global, 'FileReader', {
      writable: true,
      value: class {
        onload: (() => void) | null = null;
        result = 'data:image/png;base64,ZmFrZQ==';
        readAsDataURL() { this.onload?.(); }
      },
    });
    await userEvent.upload(input, file);
    expect(await screen.findByAltText('Ảnh chuẩn bị gửi')).toBeTruthy();
  });

  it('bỏ qua cold-start thì không hiện lại sau khi mount lại', async () => {
    const view = render(<DailyBriefingPage />);
    await screen.findByTestId('cold-start-invites');
    await userEvent.click(screen.getByRole('button', { name: translations.vi.onboarding.dismissColdStartInvites }));
    expect(screen.queryByTestId('cold-start-invites')).toBeNull();
    view.unmount();
    render(<DailyBriefingPage />);
    await waitFor(() => expect(screen.queryByTestId('cold-start-invites')).toBeNull());
  });

  it('CTA nhắc việc điều hướng vào chat với đúng câu hỏi', async () => {
    render(<DailyBriefingPage />);
    await screen.findByTestId('cold-start-invites');
    await userEvent.click(screen.getByRole('button', { name: 'Hôm nay bạn có việc gì cần tôi nhắc không?' }));
    await waitFor(() => expect(mocks.createConversation).toHaveBeenCalledWith(
      'access-token',
      'Hôm nay bạn có việc gì cần tôi nhắc không?',
      'vi',
    ));
  });

  it('CTA tìm hiểu người dùng mở chat bằng lời mời hữu ích và cho phép bỏ qua', async () => {
    render(<DailyBriefingPage />);
    await screen.findByTestId('cold-start-invites');
    await userEvent.click(screen.getByRole('button', { name: 'Giúp mondaiy hiểu điều gì quan trọng với tôi' }));

    await waitFor(() => expect(mocks.createConversation).toHaveBeenCalledWith(
      'access-token',
      'Hãy giúp tôi chỉ chia sẻ những gì có ích: giờ làm việc, việc đang làm tôi bận và nguồn tôi có thể muốn kết nối. Hỏi từng câu ngắn, nói rõ mỗi câu trả lời giúp gì và cho phép tôi bỏ qua bất kỳ câu nào.',
      'vi',
    ));
  });

  it('giữ lời gợi ý nghỉ ngơi và quyền bỏ qua ở cả tiếng Việt lẫn tiếng Anh', () => {
    expect(translations.vi.onboarding.timeOvernightRoutine).toContain('nghỉ ngơi');
    expect(translations.vi.onboarding.timeLateNightRoutine).toContain('thay vì làm tiếp');
    expect(translations.vi.onboarding.profileInvitePrompt).toContain('cho phép tôi bỏ qua');
    expect(translations.en.onboarding.timeOvernightRoutine).toContain('rest');
    expect(translations.en.onboarding.timeLateNightRoutine).toContain('instead of pushing on');
    expect(translations.en.onboarding.profileInvitePrompt).toContain('let me skip');
  });

  it('nút chọn ảnh có nhãn accessible và accept image/*', async () => {
    render(<DailyBriefingPage />);
    await screen.findByTestId('cold-start-invites');
    const input = screen.getByLabelText('Chọn ảnh thời khoá biểu hoặc lịch trình') as HTMLInputElement;
    expect(input.getAttribute('accept')).toBe('image/*');
    expect(screen.getByRole('button', { name: 'Gửi ảnh' })).toBeTruthy();
  });

  it('nhận ảnh từ onboarding handoff và đưa vào composer qua acceptImageFile', async () => {
    const file = new File(['fake'], 'schedule.png', { type: 'image/png' });
    mocks.location = { pathname: '/briefing', state: { chatPrompt: '', chatImageFile: file } };
    Object.defineProperty(global, 'FileReader', {
      writable: true,
      value: class {
        onload: (() => void) | null = null;
        result = 'data:image/png;base64,ZmFrZQ==';
        readAsDataURL() { this.onload?.(); }
      },
    });
    render(<DailyBriefingPage />);
    expect(await screen.findByAltText('Ảnh chuẩn bị gửi')).toBeTruthy();
    expect(mocks.navigate).toHaveBeenCalledWith('/briefing', { replace: true, state: null });
  });

  it('sends a planning/day-summary prompt through the live SSE agent instead of a mock reply', async () => {
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'hôm nay tôi cần làm gì');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => {
      expect(mocks.createConversation).toHaveBeenCalledWith(
        'access-token',
        'hôm nay tôi cần làm gì',
        'vi',
      );
    });
    // Giữa createConversation và streamConversationMessage nay có một lượt hỏi
    // server "câu này có cần đồng bộ không", nên phải chờ chứ không assert ngay.
    await waitFor(() => {
      expect(mocks.streamConversationMessage).toHaveBeenCalledWith(
        91,
        'hôm nay tôi cần làm gì',
        'access-token',
        expect.objectContaining({
          onProgress: expect.any(Function),
          onToken: expect.any(Function),
          onDone: expect.any(Function),
        }),
      );
    });
    expect(mocks.addMessage).toHaveBeenCalledWith('91', 'user', 'hôm nay tôi cần làm gì');
    expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
      '91',
      'Câu trả lời thật',
      {
        groundingStatus: undefined,
        isError: false,
        productivityAction: undefined,
        programQuestionHandoffEligible: undefined,
        serverMessageId: undefined,
        sources: [],
        taskDrafts: [],
        taskBacklogCount: 4,
        taskSuggestions: [],
      },
    );
  });

  it('nhận query từ trang công việc và chỉ gửi đúng một lần', async () => {
    mocks.location = {
      pathname: '/briefing',
      state: { chatPrompt: 'lên kế hoạch trong ngày cho tôi' },
    };

    render(<DailyBriefingPage />);

    await waitFor(() => expect(mocks.createConversation).toHaveBeenCalledWith(
      'access-token',
      'lên kế hoạch trong ngày cho tôi',
      'vi',
    ));
    await waitFor(() => expect(mocks.streamConversationMessage).toHaveBeenCalledWith(
      91,
      'lên kế hoạch trong ngày cho tôi',
      'access-token',
      expect.any(Object),
    ));
    expect(mocks.createConversation).toHaveBeenCalledTimes(1);
    expect(mocks.navigate).toHaveBeenCalledWith('/briefing', { replace: true, state: null });
  });

  it('routes a natural retro question through the retro and weekly-planning context', async () => {
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'Hôm nay tôi đã làm gì?');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => expect(mocks.streamConversationMessage).toHaveBeenCalledWith(
      91,
      expect.stringContaining('Đây là yêu cầu Retro và lập kế hoạch tuần'),
      'access-token',
      expect.any(Object),
    ));
  });

  it('suggests connecting Gmail in the chat instead of sending an error when Gmail is unavailable', async () => {
    mocks.isGmailBriefingIntent.mockReturnValue(true);
    mocks.getGmailStatus.mockResolvedValue({
      status: 'disconnected',
      oauthValid: false,
      mailboxAccessible: false,
      initialSyncCompleted: false,
      emailCount: 0,
    });
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'Tóm tắt email của tôi');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
      '91',
      expect.stringContaining('kết nối Gmail trong Quản lý nguồn'),
      { isError: false },
    ));
  });

  it('starts the online Gmail run before the initial sync has completed', async () => {
    mocks.isGmailBriefingIntent.mockReturnValue(true);
    mocks.getGmailStatus.mockResolvedValue({
      status: 'connected_pending_sync',
      oauthValid: true,
      mailboxAccessible: true,
      initialSyncCompleted: false,
      emailCount: 0,
    });
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'Tóm tắt email của tôi');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => expect(mocks.createGmailRun).toHaveBeenCalledWith(
      'access-token',
      7,
      ['INBOX'],
      null,
    ));
    expect(mocks.replaceLatestAiMessage).not.toHaveBeenCalledWith(
      '91',
      expect.stringContaining('Sau khi đồng bộ xong'),
      expect.anything(),
    );
  });

  it('keeps a real Gmail status request failure as an error', async () => {
    mocks.isGmailBriefingIntent.mockReturnValue(true);
    mocks.getGmailStatus.mockRejectedValueOnce(new Error('network unavailable'));
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'Tóm tắt email của tôi');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
      '91',
      'Tôi chưa thể tổng hợp Gmail ngay lúc này. Vui lòng thử lại sau.',
      { isError: true },
    ));
  });

  it('transcribes a browser voice result and sends that transcript through the existing agent flow', async () => {
    class Recognition {
      static current: Recognition | null = null;
      lang = '';
      interimResults = false;
      continuous = false;
      onresult = null;
      onerror = null;
      onend = null;
      constructor() { Recognition.current = this; }
      start() {}
      stop() { (this.onend as any)?.(); }
    }
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: Recognition });
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.click(screen.getByRole('button', { name: 'Gửi bằng giọng nói' }));
    const activeRecognition: any = Recognition.current;
    activeRecognition?.onresult?.({
      resultIndex: 0,
      results: [{ 0: { transcript: 'Tôi cần làm gì hôm nay?' } }],
    });
    activeRecognition?.onend?.();

    await waitFor(() => expect(mocks.createConversation).toHaveBeenCalledWith(
      'access-token',
      'Tôi cần làm gì hôm nay?',
      'vi',
    ));
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: undefined });
  });

  it('writes an agent failure into the conversation instead of showing an error toast', async () => {
    mocks.streamConversationMessage.mockRejectedValueOnce(new Error('upstream failed'));
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'hello, chiều nay tôi cần làm cái gì');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => {
      expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
        '91',
        expect.stringContaining('Tôi chưa thể trả lời ngay lúc này'),
        { isError: true },
      );
    });
    expect(mocks.addToast).not.toHaveBeenCalledWith(
      expect.objectContaining({ type: 'error' }),
    );
  });

  it('shows the actual daily quota reason and opens the feedback prompt', async () => {
    mocks.streamConversationMessage.mockRejectedValueOnce(
      new AgentStreamError(
        429,
        'Bạn hãy góp ý cải thiện sản phẩm của chúng tôi sẽ nhận được thêm 5 lượt dùng nữa. Đóng góp của bạn là quý giá với đội ngũ phát triển của chúng tôi.',
      ),
    );
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'câu hỏi thứ mười một');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    await waitFor(() => expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
      '91',
      'Bạn hãy góp ý cải thiện sản phẩm của chúng tôi sẽ nhận được thêm 5 lượt dùng nữa. Đóng góp của bạn là quý giá với đội ngũ phát triển của chúng tôi.',
      { isError: true },
    ));
    expect(mocks.requestProductRating).toHaveBeenCalledOnce();
  });

  it('uses theme tokens for persisted agent errors in dark mode', () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Hôm nay tôi cần làm gì?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        {
          id: 'user-1',
          sender: 'user',
          text: 'Hôm nay tôi cần làm gì?',
          timestamp: 'Just now',
        },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn hãy góp ý cải thiện sản phẩm của chúng tôi.',
          timestamp: 'Just now',
          isError: true,
        },
      ],
    };

    render(<DailyBriefingPage />);

    const errorAlert = screen.getByRole('alert');
    expect(errorAlert.className).toContain('bg-[var(--color-danger-soft)]');
    expect(errorAlert.className).toContain('text-[var(--color-text-primary)]');
    expect(errorAlert.className).not.toContain('bg-[#F9DEDE]');
  });

  it('wraps long URLs inside the user message bubble', () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Hôm nay bạn đang làm gì?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 1,
      messagesLoaded: true,
      messages: [
        {
          id: 'user-1',
          sender: 'user',
          text: 'bạn xem được cái này không https://docs.google.com/spreadsheets/d/1LySiaVYzscbgh48nj8_BEa70DXkED7Blfttmfv52tk/edit?gid=1355342090#gid=1355342090',
          timestamp: 'Just now',
        },
      ],
    };

    render(<DailyBriefingPage />);

    const userMessage = screen.getByText(/bạn xem được cái này không/);
    expect(userMessage.parentElement?.className).toContain('break-words');
    expect(userMessage.parentElement?.className).toContain('whitespace-pre-wrap');
  });

  it('sends the task-draft quick action to the real agent instead of opening a fake modal', async () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Hôm nay tôi cần làm gì?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        {
          id: 'user-1',
          sender: 'user',
          text: 'Hôm nay tôi cần làm gì?',
          timestamp: 'Just now',
        },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn cần chuẩn bị báo cáo trước 15:00 ngày mai.',
          timestamp: 'Just now',
        },
      ],
    };
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.click(screen.getByRole('button', { name: 'Tạo bản nháp nhiệm vụ' }));

    await waitFor(() => {
      expect(mocks.streamConversationMessage).toHaveBeenCalledWith(
        91,
        expect.stringContaining('tạo một task draft'),
        'access-token',
        expect.any(Object),
      );
    });
    expect(mocks.addMessage).toHaveBeenCalledWith(
      '91',
      'user',
      expect.stringContaining('không tự đoán dữ kiện còn thiếu'),
    );
  });

  it('adds the user follow-up message exactly once, not duplicated', async () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Hôm nay tôi cần làm gì?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        { id: 'user-1', sender: 'user', text: 'Hôm nay tôi cần làm gì?', timestamp: 'Just now' },
        { id: 'ai-1', sender: 'ai', text: 'Bạn cần chuẩn bị báo cáo trước 15:00 ngày mai.', timestamp: 'Just now' },
      ],
    };
    const user = userEvent.setup();
    render(<DailyBriefingPage />);

    await user.type(screen.getByPlaceholderText('Hỏi thêm...'), '1+1 bằng mấy{Enter}');

    await waitFor(() => expect(mocks.streamConversationMessage).toHaveBeenCalled());
    const userMessageCalls = mocks.addMessage.mock.calls.filter(
      (call) => call[0] === '91' && call[1] === 'user' && call[2] === '1+1 bằng mấy',
    );
    expect(userMessageCalls).toHaveLength(1);
  });

  it('renders created task cards with edit and delete actions', () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Tôi nên làm gì tiếp theo?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        {
          id: 'user-1',
          sender: 'user',
          text: 'Tôi nên làm gì tiếp theo?',
          timestamp: 'Just now',
        },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn có một số công việc cần chú ý.',
          timestamp: 'Just now',
          taskDrafts: [
            {
              id: 130,
              title: 'Nối UI chọn nguồn với danh sách nguồn thật',
              dueAt: '2026-08-15T09:00:00+07:00',
              allDay: false,
              status: 'proposed',
              calendarWriteReady: false,
              calendarEventId: null,
            },
          ],
        },
      ],
    };

    render(<DailyBriefingPage />);

    screen.getByRole('region', {
      name: 'Bản nháp task Nối UI chọn nguồn với danh sách nguồn thật',
    });
    screen.getByRole('button', { name: 'Chỉnh sửa' });
    screen.getByRole('button', { name: 'Xóa task' });
    expect(screen.queryByRole('button', { name: 'Xác nhận task' })).toBeNull();
  });

  it('hiện số task tồn đọng và mở trang task đầy đủ', async () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Tôi nên làm gì tiếp theo?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        { id: 'user-1', sender: 'user', text: 'Tôi nên làm gì tiếp theo?', timestamp: 'Just now' },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn có một số công việc cần chú ý.',
          timestamp: 'Just now',
          taskBacklogCount: 4,
        },
      ],
    };
    const user = userEvent.setup();

    render(<DailyBriefingPage />);

    await user.click(screen.getByRole('button', { name: 'Còn 4 việc tồn đọng →' }));

    expect(mocks.navigate).toHaveBeenCalledWith('/tasks');
  });

  it.each([
    ['bằng 0', 0],
    ['bị thiếu', undefined],
  ])('không hiện dòng task tồn đọng khi số lượng %s', (_case, taskBacklogCount) => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Tôi nên làm gì tiếp theo?',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        { id: 'user-1', sender: 'user', text: 'Tôi nên làm gì tiếp theo?', timestamp: 'Just now' },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Bạn có một số công việc cần chú ý.',
          timestamp: 'Just now',
          ...(taskBacklogCount === undefined ? {} : { taskBacklogCount }),
        },
      ],
    };

    render(<DailyBriefingPage />);

    expect(screen.queryByRole('button', { name: /việc tồn đọng/ })).toBeNull();
  });

  it('shows the evening retro card from real task data', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-08-23T20:00:00+07:00'));
    mocks.listTasks.mockResolvedValue({
      tasks: [
        {
          id: 12,
          title: 'Hoàn thành báo cáo tuần',
          detail: '',
          status: 'completed',
          updatedAt: '2026-08-23T16:00:00+07:00',
          dueAt: null,
        },
      ],
    });

    render(<DailyBriefingPage />);

    expect(await screen.findByTestId('daily-retro-card')).toBeTruthy();
    expect(screen.getByText('Hoàn thành báo cáo tuần')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Gợi ý kế hoạch tuần' })).toBeTruthy();
    vi.useRealTimers();
  });

  it('Dừng trả lời bấm trong lúc đang đồng bộ (trước khi agent stream bắt đầu) phải huỷ ngay, không chờ đồng bộ tự xong', async () => {
    const user = userEvent.setup();
    // Đồng bộ THỰC SỰ được kích hoạt lần này (khác default triggered:false của
    // beforeEach) và không bao giờ tự resolve trong test — mô phỏng đúng tình
    // huống lỗi thật: đồng bộ có thể treo hàng phút, nút Dừng phải cắt được nó
    // chứ không chỉ cắt được stream của agent.
    let rejectWaitForRun!: (err: unknown) => void;
    mocks.triggerChatSync.mockResolvedValue({ triggered: true, reason: 'first_chat_of_day', run: { id: 99, status: 'running', errorMessage: null, createdAt: 'now' } });
    mocks.waitForRun.mockImplementation(
      () => new Promise((_resolve, reject) => { rejectWaitForRun = reject; }),
    );

    render(<DailyBriefingPage />);
    await user.type(screen.getByPlaceholderText('Hỏi mondaiy'), 'kể chuyện dài cho tôi nghe');
    await user.click(screen.getByRole('button', { name: 'Gửi' }));

    const stopButton = await screen.findByRole('button', { name: 'Dừng trả lời' });
    await waitFor(() => expect(mocks.waitForRun).toHaveBeenCalledWith('access-token', 99, expect.any(AbortSignal)));
    const signalPassed = mocks.waitForRun.mock.calls[0][2] as AbortSignal;
    expect(signalPassed.aborted).toBe(false);

    await user.click(stopButton);

    // Bấm Dừng phải abort() ngay controller đã truyền cho waitForRun — kể cả
    // khi promise đó chưa reject, cờ aborted đã phải bật tức thì.
    expect(signalPassed.aborted).toBe(true);
    rejectWaitForRun(new DOMException('Aborted', 'AbortError'));

    await waitFor(() => expect(mocks.replaceLatestAiMessage).toHaveBeenCalledWith(
      expect.any(String),
      'Đã dừng.',
      { isError: false },
    ));
    // Agent thật không bao giờ được gọi — đồng bộ bị huỷ trước khi tới bước đó.
    expect(mocks.streamConversationMessage).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Dừng trả lời' })).toBeNull());
  });

  it('renders persisted source citations as safe external links', () => {
    mocks.conversationId = '91';
    mocks.activeConversation = {
      id: '91',
      title: 'Lịch workshop',
      dateGroup: 'today',
      lastUpdated: 'Just now',
      messageCount: 2,
      messagesLoaded: true,
      messages: [
        { id: 'user-1', sender: 'user', text: 'Workshop khi nào?', timestamp: 'Just now' },
        {
          id: 'ai-1',
          sender: 'ai',
          text: 'Workshop diễn ra tối nay.',
          timestamp: 'Just now',
          sources: [
            {
              tool: 'program_schedule',
              title: 'Workshop AI',
              url: 'https://example.test/program/workshop',
              occurred_at: '2026-08-20T19:00:00+07:00',
            },
          ],
        },
      ],
    };

    render(<DailyBriefingPage />);

    const citation = screen.getByRole('link', { name: /Workshop AI/ });
    expect(citation.getAttribute('href')).toBe('https://example.test/program/workshop');
    expect(citation.getAttribute('target')).toBe('_blank');
    expect(citation.getAttribute('rel')).toBe('noreferrer');
  });
});
