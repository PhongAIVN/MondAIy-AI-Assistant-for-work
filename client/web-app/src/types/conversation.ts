import type { AgentSourceCitation, TaskDraftAction, TaskSuggestionAction } from '../lib/agentStream.js';

export interface EvidenceItem {
  id: string;
  title: string;
  summary: string;
  confidence: 'certain' | 'possible' | 'ask_mentor';
  source: {
    platform: string;
    location: string;
    timestamp: string;
    author?: string;
  };
}

export type ProductivityAction = {
  status: 'needs_clarification' | 'pending_approval' | 'created' | 'rejected' | 'error';
  kind: 'calendar_event' | 'task' | 'todo';
  approval_id?: string;
  signature?: string;
  message: string;
  missing_fields?: string[];
  draft?: {
    title?: string;
    starts_at?: string;
    ends_at?: string;
    duration_minutes?: number | null;
    deadline?: string;
    description?: string;
    calendar_id?: string;
    attendees?: string[];
  };
  result?: {
    task_id?: number;
    calendar_event_id?: string;
    calendar_url?: string | null;
    deadline?: string;
    starts_at?: string;
    ends_at?: string;
    already_created?: boolean;
  };
  approved_at?: string;
  rejected_at?: string;
  provenance?: Record<string, boolean>;
};

export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  // Grounded AI response fields
  summary?: string;
  whatChanged?: string;
  whyItMatters?: string;
  recommendedNextStep?: string;
  confidence?: 'certain' | 'possible' | 'ask_mentor';
  source?: {
    platform: string;
    location: string;
    timestamp: string;
  };
  evidenceItems?: EvidenceItem[];
  feedback?: 'helpful' | 'partly' | 'incorrect' | null;
  scenario?: 'standard' | 'urgent' | 'conflict' | 'noupdates';
  /** Lỗi xử lý gắn với lượt hỏi này; render trực tiếp trong luồng chat. */
  isError?: boolean;
  /** ID server của assistant turn, dùng để duyệt đúng action trong message. */
  serverMessageId?: number;
  productivityAction?: ProductivityAction;
  /** Task do agent vừa tạo, kèm trạng thái để render hành động xác nhận thật. */
  taskDrafts?: TaskDraftAction[];
  /** Số task proposed bị ẩn vì quá cũ hoặc vượt trần card. */
  taskBacklogCount?: number;
  /** Việc nhận ra từ nguồn nhưng chưa ghi DB; chỉ tạo khi người dùng bấm. */
  taskSuggestions?: TaskSuggestionAction[];
  calendarSuggestions?: import('../lib/visionApi.js').CalendarSuggestionAction[];
  /** Tín hiệu bằng chứng để người dùng chủ động chuyển câu hỏi cho đội ngũ. */
  groundingStatus?: 'grounded' | 'uncertain' | 'abstain' | 'reject';
  /** Server xác nhận câu hỏi thuộc thông tin chương trình và thiếu bằng chứng. */
  programQuestionHandoffEligible?: boolean;
  /** Các link nguồn backend đã dùng để tạo câu trả lời. */
  sources?: AgentSourceCitation[];
}

export interface Conversation {
  // Luon la String(id) that tu backend — khong con id gia phia client.
  id: string;
  title: string;
  dateGroup: 'today' | 'yesterday' | 'earlier';
  lastUpdated: string;
  messageCount: number;
  messages: ChatMessage[];
  // Sidebar chi co summary luc fetch list; true sau khi da GET chi tiet 1 lan.
  messagesLoaded: boolean;
  /** Du an chua hoi thoai; null/undefined = chua xep. */
  projectId?: number | null;
  isFavorite: boolean;
}
