import { create } from 'zustand';
import { type ChatMessageItem, defaultChatHistory, mockQuestionResponses } from '../data/mockChatData';
import { streamAgent } from '../lib/agentApi';
import { useAuthStore } from './useAuthStore';

type NavigatorStore = {
  isOpen: boolean;
  messages: ChatMessageItem[];
  suggestedQuestions: string[];
  inputMessage: string;
  isTyping: boolean;

  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  setInputMessage: (msg: string) => void;
  sendMessage: (customText?: string) => Promise<void>;
  askSuggestedQuestion: (question: string) => void;
};

export const useNavigatorStore = create<NavigatorStore>((set, get) => ({
  isOpen: false,
  messages: defaultChatHistory,
  suggestedQuestions: [
    'What changed today?',
    'Why is this deadline important?',
    'What should I do next?',
    'Are any sources conflicting?',
    'How was this briefing generated?',
    'What is missing or uncertain?',
    'Show source evidence',
    'Help me draft a question for my mentor'
  ],
  inputMessage: '',
  isTyping: false,

  openDrawer: () => set({ isOpen: true }),
  closeDrawer: () => set({ isOpen: false }),
  toggleDrawer: () => set((state) => ({ isOpen: !state.isOpen })),

  setInputMessage: (inputMessage) => set({ inputMessage }),

  sendMessage: async (customText) => {
    const textToSend = (customText || get().inputMessage).trim();
    if (!textToSend) return;

    const userMsg: ChatMessageItem = {
      id: 'msg-' + Date.now(),
      sender: 'user',
      text: textToSend,
      timestamp: 'Just now'
    };

    set((state) => ({
      messages: [...state.messages, userMsg],
      inputMessage: '',
      isTyping: true
    }));

    const appendFallback = () => {
      let navResponse: ChatMessageItem;

      if (mockQuestionResponses[textToSend]) {
        navResponse = {
          ...mockQuestionResponses[textToSend],
          id: 'resp-' + Date.now()
        };
      } else {
        navResponse = {
          id: 'resp-' + Date.now(),
          sender: 'navigator',
          text: `Here is the relevant information found regarding "${textToSend}":\n\nI searched your connected channels (Discord #announcements, Canvas LMS, Program Calendar). There are no new policy changes or conflicts regarding this topic.\n\nNext Action: Keep following your scheduled milestones or ask your team mentor if you need further clarification.`,
          timestamp: 'Just now',
          sourceReference: {
            platform: 'Discord & Canvas',
            location: '#announcements & Course Syllabus',
            timestamp: 'July 28 · 8:00 AM',
            confidence: 'certain'
          }
        };
      }

      set((state) => ({
        messages: [...state.messages, navResponse],
        isTyping: false
      }));
    };

    const accessToken = useAuthStore.getState().accessToken;
    if (!accessToken || accessToken === 'mock-access-token') {
      setTimeout(appendFallback, 800);
      return;
    }

    const assistantId = 'resp-' + Date.now();
    let receivedToken = false;
    try {
      await streamAgent(textToSend, accessToken, {
        onToken: (delta) => {
          receivedToken = true;
          set((state) => {
            const existing = state.messages.find((message) => message.id === assistantId);
            if (existing) {
              return {
                messages: state.messages.map((message) =>
                  message.id === assistantId ? { ...message, text: message.text + delta } : message,
                ),
              };
            }
            return {
              messages: [
                ...state.messages,
                { id: assistantId, sender: 'navigator', text: delta, timestamp: 'Just now' },
              ],
            };
          });
        },
        onDone: () => set({ isTyping: false }),
      });
      set({ isTyping: false });
    } catch {
      if (receivedToken) set({ isTyping: false });
      else appendFallback();
    }
  },

  askSuggestedQuestion: (question) => {
    get().sendMessage(question);
  }
}));
