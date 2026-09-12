import type { GoogleSheetsTaskProposal } from './googleSheetsApi';
import type { GoogleDocsTaskProposal } from './googleDocsApi';

/** Hình dạng chung để render đề xuất task từ Google Docs hoặc Google Sheets
 * bằng cùng một UI — Docs và Sheets ngang hàng nhau trong luồng chọn file Drive. */
export type NormalizedTaskProposal = {
  key: string;
  title: string;
  detail: string;
  assignee: string | null;
  dueAt: string | null;
  allDay: boolean;
  needsConfirmation: boolean;
  clarificationQuestion: string | null;
  source: string;
  sourceUrl: string;
  /** VD: "Dòng 12" (Sheets) hoặc "Đoạn 3" (Docs). */
  positionLabel: string;
};

export const normalizeSheetProposal = (proposal: GoogleSheetsTaskProposal): NormalizedTaskProposal => ({
  key: proposal.externalKey,
  title: proposal.title,
  detail: proposal.detail,
  assignee: proposal.assignee,
  dueAt: proposal.dueAt,
  allDay: proposal.allDay,
  needsConfirmation: proposal.needsConfirmation,
  clarificationQuestion: proposal.clarificationQuestion,
  source: proposal.source,
  sourceUrl: proposal.sourceUrl,
  positionLabel: `Dòng ${proposal.rowNumber}`,
});

export const normalizeDocProposal = (proposal: GoogleDocsTaskProposal, documentId: string): NormalizedTaskProposal => ({
  key: `${documentId}:${proposal.paragraphIndex}`,
  title: proposal.title,
  detail: proposal.detail,
  assignee: proposal.assignee,
  dueAt: proposal.dueAt,
  allDay: proposal.allDay,
  needsConfirmation: proposal.needsConfirmation,
  clarificationQuestion: proposal.clarificationQuestion,
  source: proposal.source,
  sourceUrl: proposal.sourceUrl,
  positionLabel: `Đoạn ${proposal.paragraphIndex + 1}`,
});
