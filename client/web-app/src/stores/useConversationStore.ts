import { create } from 'zustand';
import {
  createServerConversation,
  deleteServerConversation,
  getConversationDetail,
  listConversations,
  renameServerConversation,
  setConversationFavorite,
  updateMessageFeedback,
  type ServerConversationMessage,
} from '../lib/conversationApi';
import {
  type Conversation,
  type ChatMessage,
  type ProductivityAction,
} from '../types/conversation';

function dateGroupOf(iso: string): Conversation['dateGroup'] {
  const d = new Date(iso);
  const now = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86_400_000);
  if (diffDays <= 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  return 'earlier';
}

function lastUpdatedLabelOf(iso: string, language: string): string {
  const group = dateGroupOf(iso);
  const d = new Date(iso);
  if (group === 'today') {
    return d.toLocaleTimeString(language === 'vi' ? 'vi-VN' : 'en-US', { hour: '2-digit', minute: '2-digit' });
  }
  if (group === 'yesterday') return language === 'vi' ? 'Hôm qua' : 'Yesterday';
  return d.toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-US', { day: '2-digit', month: '2-digit' });
}

function toChatMessage(turn: ServerConversationMessage): ChatMessage {
  const extras = (turn.extras ?? {}) as Partial<ChatMessage>;
  return {
    id: String(turn.id),
    sender: turn.role === 'user' ? 'user' : 'ai',
    text: turn.content,
    timestamp: turn.createdAt,
    feedback: turn.feedback ?? null,
    serverMessageId: turn.role === 'assistant' ? turn.id : undefined,
    ...extras,
  };
}

interface ConversationStore {
  conversations: Conversation[];
  activeConversationId: string | null;
  isLoadingList: boolean;
  /** id hội thoại nào đang có 1 lượt agent chạy ngầm (stream chưa "done").
   * Sống ở store toàn cục (không phải state cục bộ của DailyBriefingPage) nên
   * điều hướng sang hội thoại khác hoặc quay lại sidebar không làm mất tín
   * hiệu "vẫn đang chạy" — sidebar tự vẽ node đặc/rỗng dựa vào đây. */
  generatingIds: Set<string>;
  setConversationGenerating: (id: string, generating: boolean) => void;

  setActiveConversationId: (id: string | null) => void;
  getConversation: (id: string) => Conversation | undefined;

  /** Nguồn duy nhất cho sidebar lịch sử — GET /api/v1/conversations thật,
   * KHÔNG đọc localStorage/seed giả (thay useConversationStore bản cũ). */
  fetchConversations: (accessToken: string, language: string) => Promise<void>;
  /** Sidebar chỉ có summary; gọi khi mở 1 hội thoại để lấy đủ messages. */
  fetchConversationDetail: (accessToken: string, id: string, language: string) => Promise<void>;

  /** Tạo hội thoại thật trên backend trước, id trả về = id thật luôn — không
   * còn id giả phía client rồi link sau (nguồn gốc bug "conversation không tồn tại"). */
  createConversation: (accessToken: string, initialQuestion: string, language: string) => Promise<string>;

  addMessage: (
    conversationId: string,
    sender: 'user' | 'ai',
    text: string,
    aiData?: Partial<ChatMessage>,
  ) => void;
  replaceLatestAiMessage: (conversationId: string, text: string, aiData: Partial<ChatMessage>) => void;
  updateProductivityAction: (conversationId: string, messageId: string, action: ProductivityAction) => void;
  updateFeedback: (
    accessToken: string,
    conversationId: string,
    messageId: string,
    feedback: 'helpful' | 'partly' | 'incorrect' | null,
  ) => Promise<void>;
  setFavorite: (accessToken: string, conversationId: string, isFavorite: boolean) => Promise<void>;

  renameConversation: (accessToken: string, id: string, newTitle: string) => Promise<void>;
  deleteConversation: (accessToken: string, id: string) => Promise<void>;
}

export const useConversationStore = create<ConversationStore>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  isLoadingList: false,
  generatingIds: new Set<string>(),

  setConversationGenerating: (id, generating) => {
    set((state) => {
      const next = new Set(state.generatingIds);
      if (generating) next.add(id);
      else next.delete(id);
      return { generatingIds: next };
    });
  },

  setActiveConversationId: (id) => set({ activeConversationId: id }),

  getConversation: (id) => get().conversations.find((c) => c.id === id),

  fetchConversations: async (accessToken, language) => {
    set({ isLoadingList: true });
    try {
      const { conversations } = await listConversations(accessToken);
      const byId = new Map(get().conversations.map((c) => [c.id, c]));
      set({
        conversations: conversations.map((summary) => {
          const id = String(summary.id);
          const existing = byId.get(id);
          return {
            id,
            title: summary.title,
            projectId: summary.projectId ?? null,
            isFavorite: summary.isFavorite,
            dateGroup: dateGroupOf(summary.updatedAt),
            lastUpdated: lastUpdatedLabelOf(summary.updatedAt, language),
            messageCount: summary.messageCount,
            messages: existing?.messages ?? [],
            messagesLoaded: existing?.messagesLoaded ?? false,
          };
        }),
        isLoadingList: false,
      });
    } catch {
      // Chưa đăng nhập hoặc lỗi mạng — giữ list hiện tại, không báo sai dữ liệu.
      set({ isLoadingList: false });
    }
  },

  fetchConversationDetail: async (accessToken, id, language) => {
    const numericId = Number(id);
    if (!Number.isFinite(numericId)) return;
    const detail = await getConversationDetail(numericId, accessToken);
    const messages = detail.messages.map(toChatMessage);
    set((state) => {
      const exists = state.conversations.some((c) => c.id === id);
      if (exists) {
        return {
          conversations: state.conversations.map((c) =>
            c.id === id ? { ...c, title: detail.title, isFavorite: detail.isFavorite, messages, messagesLoaded: true } : c,
          ),
        };
      }
      // Vao thang link /briefing/conversation/{id} truoc khi sidebar fetch
      // xong list — chen hoi thoai nay vao dau list thay vi bo qua.
      const newConv: Conversation = {
        id,
        title: detail.title,
        isFavorite: detail.isFavorite,
        dateGroup: dateGroupOf(detail.updatedAt),
        lastUpdated: lastUpdatedLabelOf(detail.updatedAt, language),
        messageCount: messages.length,
        messages,
        messagesLoaded: true,
      };
      return { conversations: [newConv, ...state.conversations] };
    });
  },

  createConversation: async (accessToken, initialQuestion, language) => {
    const server = await createServerConversation(initialQuestion.trim(), accessToken);
    const id = String(server.id);
    const newConv: Conversation = {
      id,
      title: server.title,
      isFavorite: server.isFavorite,
      dateGroup: dateGroupOf(server.updatedAt),
      lastUpdated: lastUpdatedLabelOf(server.updatedAt, language),
      messageCount: 0,
      messages: [],
      messagesLoaded: true,
    };
    set((state) => ({ conversations: [newConv, ...state.conversations], activeConversationId: id }));
    return id;
  },

  addMessage: (conversationId, sender, text, aiData) => {
    set((state) => ({
      conversations: state.conversations.map((conv) => {
        if (conv.id !== conversationId) return conv;
        const newMsg: ChatMessage = {
          id: `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          sender,
          text,
          timestamp: new Date().toISOString(),
          ...aiData,
        };
        return { ...conv, messages: [...conv.messages, newMsg] };
      }),
    }));
  },

  replaceLatestAiMessage: (conversationId, text, aiData) => {
    set((state) => ({
      conversations: state.conversations.map((conv) => {
        if (conv.id !== conversationId) return conv;
        const messages = [...conv.messages];
        const index = [...messages].reverse().findIndex((message) => message.sender === 'ai');
        const target = index >= 0 ? messages.length - 1 - index : -1;
        if (target >= 0) {
          messages[target] = { ...messages[target], text, ...aiData };
        } else {
          messages.push({ id: `local-${Date.now()}`, sender: 'ai', text, timestamp: new Date().toISOString(), ...aiData });
        }
        return { ...conv, messages };
      }),
    }));
  },

  updateProductivityAction: (conversationId, messageId, action) => {
    set((state) => ({
      conversations: state.conversations.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              messages: conversation.messages.map((message) =>
                message.id === messageId ? { ...message, productivityAction: action } : message,
              ),
            }
          : conversation,
      ),
    }));
  },

  updateFeedback: async (accessToken, conversationId, messageId, feedback) => {
    const numericConvId = Number(conversationId);
    const numericMsgId = Number(messageId);
    if (feedback && Number.isFinite(numericConvId) && Number.isFinite(numericMsgId)) {
      await updateMessageFeedback(numericConvId, numericMsgId, feedback, accessToken);
    }
    set((state) => ({
      conversations: state.conversations.map((conv) => {
        if (conv.id !== conversationId) return conv;
        return { ...conv, messages: conv.messages.map((msg) => (msg.id === messageId ? { ...msg, feedback } : msg)) };
      }),
    }));
  },

  setFavorite: async (accessToken, conversationId, isFavorite) => {
    const numericId = Number(conversationId);
    if (!Number.isFinite(numericId)) return;
    await setConversationFavorite(numericId, isFavorite, accessToken);
    set((state) => ({
      conversations: state.conversations.map((conversation) =>
        conversation.id === conversationId ? { ...conversation, isFavorite } : conversation,
      ),
    }));
  },

  renameConversation: async (accessToken, id, newTitle) => {
    const numericId = Number(id);
    if (!Number.isFinite(numericId)) return;
    await renameServerConversation(numericId, newTitle, accessToken);
    set((state) => ({
      conversations: state.conversations.map((c) => (c.id === id ? { ...c, title: newTitle } : c)),
    }));
  },

  deleteConversation: async (accessToken, id) => {
    const numericId = Number(id);
    if (!Number.isFinite(numericId)) return;
    await deleteServerConversation(numericId, accessToken);
    set((state) => ({
      conversations: state.conversations.filter((c) => c.id !== id),
      activeConversationId: state.activeConversationId === id ? null : state.activeConversationId,
    }));
  },
}));
