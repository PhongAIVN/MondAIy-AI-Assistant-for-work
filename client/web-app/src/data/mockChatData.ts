export type ChatMessageItem = {
  id: string;
  sender: 'user' | 'navigator';
  text: string;
  timestamp: string;
  sourceReference?: {
    platform: string;
    location: string;
    timestamp: string;
    confidence: 'certain' | 'possible' | 'ask_mentor';
    rawQuote?: string;
  };
  actions?: Array<{ label: string; actionType: string }>;
};

export const defaultChatHistory: ChatMessageItem[] = [
  {
    id: 'welcome',
    sender: 'navigator',
    text: 'Tôi có thể giúp bạn kiểm tra thay đổi, hạn chót và nguồn liên quan.',
    timestamp: 'Now',
  },
];

export const mockQuestionResponses: Record<string, ChatMessageItem> = {
  'What changed today?': {
    id: 'changed-today',
    sender: 'navigator',
    text: 'Hạn nộp Gate 1 đang có mâu thuẫn giữa Jira và Discord. Bạn nên xác minh trước khi tạo lịch.',
    timestamp: 'Now',
    sourceReference: {
      platform: 'Jira & Discord',
      location: 'TAPB / #announcements',
      timestamp: '2026-08-02 09:00 ICT',
      confidence: 'ask_mentor',
    },
    actions: [
      { label: 'So sánh nguồn', actionType: 'compare_conflict' },
      { label: 'Soạn câu hỏi mentor', actionType: 'draft_mentor_msg' },
    ],
  },
};
