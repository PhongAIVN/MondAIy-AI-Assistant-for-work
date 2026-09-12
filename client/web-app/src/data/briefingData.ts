import type { BriefingItem } from '../types/briefing';

export const conflictBriefingItem: BriefingItem = {
  id: 'brief-conflict-1',
  title: 'Cần xác minh hạn nộp Gate 1',
  summary: 'Jira và Discord đang hiển thị hai thời điểm khác nhau.',
  relevance: 'Ảnh hưởng trực tiếp đến mốc nộp của nhóm.',
  nextAction: 'Mở hai nguồn và xin mentor xác nhận.',
  source: { platform: 'Jira + Discord', location: 'TAPB / #announcements', timestamp: '2026-08-02 09:00 ICT' },
  confidence: 'ask_mentor',
  commitment: 'committed',
  priority: 'urgent',
  category: 'changes',
  previousValue: '22:00',
  currentValue: '23:59',
  conflictDetails: {
    sourceA: { platform: 'Jira', location: 'TAPB', value: '22:00', timestamp: '08:30', content: 'Gate 1 due at 22:00.' },
    sourceB: { platform: 'Discord', location: '#announcements', value: '23:59', timestamp: '09:00', content: 'Gate 1 deadline is 23:59 ICT.' },
    mentorVerificationDraft: 'Mentor xác nhận giúp nhóm thời điểm nộp Gate 1 chính thức?',
  },
};

export const initialBriefingItems: BriefingItem[] = [
  {
    id: 'brief-1',
    title: 'Gate 1 đến hạn hôm nay',
    summary: 'Bộ hồ sơ cần được rà soát và gắn tag trước khi nộp.',
    relevance: 'Bạn là người chịu trách nhiệm điều phối hồ sơ.',
    nextAction: 'Kiểm tra manifest và tạo snapshot.',
    source: { platform: 'Jira', location: 'TAPB backlog', timestamp: '2026-08-02 09:00 ICT' },
    confidence: 'certain',
    commitment: 'committed',
    priority: 'urgent',
    category: 'needs_attention',
    dueDate: '2026-08-02T23:59:00+07:00',
  },
  conflictBriefingItem,
];
