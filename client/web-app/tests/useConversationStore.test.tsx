import { beforeEach, describe, expect, it, vi } from 'vitest';

const { setConversationFavorite, updateMessageFeedback } = vi.hoisted(() => ({
  setConversationFavorite: vi.fn(),
  updateMessageFeedback: vi.fn(),
}));

vi.mock('../src/lib/conversationApi', () => ({
  createServerConversation: vi.fn(),
  deleteServerConversation: vi.fn(),
  getConversationDetail: vi.fn(),
  listConversations: vi.fn(),
  renameServerConversation: vi.fn(),
  setConversationFavorite,
  updateMessageFeedback,
}));

import { useConversationStore } from '../src/stores/useConversationStore';

describe('useConversationStore favorites', () => {
  beforeEach(() => {
    setConversationFavorite.mockResolvedValue({});
    updateMessageFeedback.mockReset();
    updateMessageFeedback.mockResolvedValue(undefined);
    useConversationStore.setState({
      conversations: [
        {
          id: '42',
          title: 'Weekly submit',
          dateGroup: 'today',
          lastUpdated: 'Just now',
          messageCount: 2,
          messages: [
            { id: '1', role: 'assistant', content: 'hi', timestamp: 'now', feedback: null } as never,
          ],
          messagesLoaded: false,
          isFavorite: false,
        },
      ],
    });
  });

  it('persists the favorite toggle and updates sidebar state after success', async () => {
    await useConversationStore.getState().setFavorite('token', '42', true);

    expect(setConversationFavorite).toHaveBeenCalledWith(42, true, 'token');
    expect(useConversationStore.getState().conversations[0].isFavorite).toBe(true);
  });
});

describe('useConversationStore feedback', () => {
  beforeEach(() => {
    updateMessageFeedback.mockReset();
    updateMessageFeedback.mockResolvedValue(undefined);
    useConversationStore.setState({
      conversations: [
        {
          id: '42',
          title: 'Weekly submit',
          dateGroup: 'today',
          lastUpdated: 'Just now',
          messageCount: 2,
          messages: [
            { id: '1', role: 'assistant', content: 'hi', timestamp: 'now', feedback: null } as never,
          ],
          messagesLoaded: false,
          isFavorite: false,
        },
      ],
    });
  });

  it('persists thumbs-up feedback to the backend and updates local state', async () => {
    await useConversationStore.getState().updateFeedback('token', '42', '1', 'helpful');

    expect(updateMessageFeedback).toHaveBeenCalledWith(42, 1, 'helpful', 'token');
    expect(useConversationStore.getState().conversations[0].messages[0].feedback).toBe('helpful');
  });

  it('persists thumbs-down feedback as incorrect', async () => {
    await useConversationStore.getState().updateFeedback('token', '42', '1', 'incorrect');

    expect(updateMessageFeedback).toHaveBeenCalledWith(42, 1, 'incorrect', 'token');
    expect(useConversationStore.getState().conversations[0].messages[0].feedback).toBe('incorrect');
  });

  it('does not call the backend when clearing feedback locally', async () => {
    await useConversationStore.getState().updateFeedback('token', '42', '1', null);

    expect(updateMessageFeedback).not.toHaveBeenCalled();
    expect(useConversationStore.getState().conversations[0].messages[0].feedback).toBe(null);
  });
});
