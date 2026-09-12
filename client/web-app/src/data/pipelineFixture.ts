// Dữ liệu giả cho trang /run — chỉ dùng khi backend chưa có endpoint tương
// ứng. UI luôn hiện băng cảnh báo khi chạy bằng file này, để không ai nhầm nó
// là dữ liệu thật lúc demo.
//
// Số ở MOCK_NODE_COUNTS lấy từ ví dụ phễu trong docs/architecture/architecture.drawio.
// Nội dung là synthetic, không phải tin nhắn thật của ai.

import type { Brief, PipelineNode, Task } from '../types/pipeline';

export const MOCK_NODE_COUNTS: Record<PipelineNode, number> = {
  fetch: 1680,
  normalize: 1680,
  filter: 90,
  make_batches: 14,
  extract_batch: 63,
  resolve: 46,
  cluster: 26,
  reduce: 26,
  persist: 4,
};

const isoInDays = (days: number, hour: number, minute = 0): string => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
};

const now = new Date().toISOString();

export const MOCK_TASKS: Task[] = [
  {
    id: 9001,
    clusterKey: 'mock-cls-1',
    title: 'Nộp bản đóng băng wireframe cho Gate 2',
    detail: '',
    dueAt: isoInDays(2, 17),
    allDay: false,
    ambiguous: false,
    status: 'proposed',
    sourceCount: 2,
    signalStrength: 0.67,
    calendarEventId: null,
    createdAt: now,
    updatedAt: now,
    evidence: [
      {
        id: 1,
        messageId: 101,
        provider: 'discord',
        evidenceQuote: 'Nhi gửi bản wireframe đóng băng trước 17h thứ sáu nhé, mentor review cuối tuần.',
        deepLink: 'https://discord.com/channels/000/000/1',
        hasAttachment: false,
      },
      {
        id: 2,
        messageId: 102,
        provider: 'google',
        evidenceQuote: 'Nhắc lại: bản PDF wireframe hạn cuối thứ sáu, gửi vào mail nhóm.',
        deepLink: 'https://mail.google.com/mail/u/0/#inbox/mock2',
        hasAttachment: false,
      },
    ],
  },
  {
    id: 9002,
    clusterKey: 'mock-cls-2',
    title: 'Chạy usability test 3-5 người dùng (OI-01)',
    detail: '',
    dueAt: isoInDays(8, 23, 59),
    allDay: false,
    ambiguous: false,
    status: 'proposed',
    sourceCount: 1,
    signalStrength: 0.33,
    calendarEventId: null,
    createdAt: now,
    updatedAt: now,
    evidence: [
      {
        id: 3,
        messageId: 103,
        provider: 'discord',
        evidenceQuote: 'OI-01 vẫn mở, usability test phải xong trước 13/08 mới qua được Gate 2.',
        deepLink: 'https://discord.com/channels/000/000/3',
        hasAttachment: false,
      },
    ],
  },
  {
    id: 9003,
    clusterKey: 'mock-cls-3',
    title: 'Review API danh sách nguồn trước khi FE cắm vào',
    detail: '',
    dueAt: isoInDays(1, 9),
    allDay: false,
    ambiguous: true,
    status: 'proposed',
    sourceCount: 1,
    signalStrength: 0.33,
    calendarEventId: null,
    createdAt: now,
    updatedAt: now,
    evidence: [
      {
        id: 4,
        messageId: 104,
        provider: 'discord',
        evidenceQuote: 'Sáng mai mình đẩy nhánh connections, ai cắm FE thì review giúp shape response.',
        deepLink: 'https://discord.com/channels/000/000/4',
        hasAttachment: false,
      },
    ],
  },
  {
    id: 9004,
    clusterKey: 'mock-cls-4',
    title: 'Gửi biên bản duyệt Checkpoint 1',
    detail: '',
    dueAt: null,
    allDay: false,
    ambiguous: true,
    status: 'proposed',
    sourceCount: 1,
    signalStrength: 0.33,
    calendarEventId: null,
    createdAt: now,
    updatedAt: now,
    evidence: [
      {
        id: 5,
        messageId: 105,
        provider: 'google',
        evidenceQuote: 'Biên bản duyệt Checkpoint 1 mình gửi sau khi test crawl Gmail xong.',
        deepLink: 'https://mail.google.com/mail/u/0/#inbox/mock5',
        hasAttachment: false,
      },
    ],
  },
];

export const MOCK_BRIEF: Brief = {
  id: 1,
  runId: 0,
  summary:
    'Tìm thấy 4 việc cần làm. Gấp nhất là hạn nộp bản đóng băng wireframe cho Gate 2, có hai nguồn cùng nhắc.',
  topPriority: MOCK_TASKS.slice(0, 3).map((task) => ({
    taskId: task.id,
    title: task.title,
    dueAt: task.dueAt,
  })),
  scheduleConflicts: [],
  createdAt: now,
};
