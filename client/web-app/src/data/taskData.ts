import type { TaskItem } from '../types/task';

export const initialTasks: TaskItem[] = [
  {
    id: 'task-1',
    title: 'Hoàn thiện tài liệu Gate 1',
    description: 'Rà soát PRD, luồng giao diện và nguồn dẫn trước khi nộp.',
    dueDate: '2026-08-02T23:59:00+07:00',
    status: 'in_progress',
    priority: 'urgent',
    confidence: 'certain',
    commitment: 'committed',
    source: {
      platform: 'Jira',
      location: 'TAPB backlog',
      timestamp: '2026-08-02 09:00 ICT',
    },
    tags: ['Gate 1'],
  },
];
