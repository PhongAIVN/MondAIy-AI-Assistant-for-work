export type GlobalCaptureStatus = 'active' | 'paused';

export type SourceCoverageType = 'continuous' | 'limited' | 'expired' | 'permission_required';

export type ConfidenceLevel = 'Certain' | 'Possible' | 'Ask Mentor';

export type RetentionStatus = 'active' | 'edited' | 'scheduled_deletion' | 'deleted';

export type RecordProcessingStatus = 'used_in_briefing' | 'saved_as_memory' | 'pending_review' | 'deleted';

export type MemoryStatus = 'confirmed' | 'pending_review' | 'rejected' | 'low_confidence' | 'outdated' | 'paused';

export type MemoryCategory = 'Program context' | 'Personal preference' | 'Deliverable rule' | 'Mentor guidance';

export interface GranularControlItem {
  id: string;
  enabled: boolean;
  alwaysUnavailable?: boolean;
}

export interface ConnectedSourceAccess {
  id: string;
  /** Key ổn định — tên hiển thị resolve qua privacyCatalog.sourceNames */
  name: string;
  platform: 'Discord' | 'Email' | 'Learning Platform' | 'Program Calendar' | 'Google Drive';
  accountEmailOrUser: string;
  connected: boolean;
  captureEnabled: boolean;
  coverage: SourceCoverageType;
  /** Key thời gian trong privacyCatalog.timeLabels */
  lastReviewedAt: string;
  capturedRecordsCount: number;
  icon: string;
  permissions: {
    /** Key trong privacyCatalog.scopes */
    canAccess: string[];
    cannotAccess: string[];
    granularControls: GranularControlItem[];
  };
}

export interface CapturedRecord {
  id: string;
  sourceId: string;
  sourceName: string;
  sourceLocation: string;
  originalTimestamp: string;
  capturedAt: string;
  contentPreview: string;
  originalContent: string;
  extractedInformation: string;
  confidence: ConfidenceLevel;
  retentionStatus: RetentionStatus;
  processingStatus: RecordProcessingStatus;
  usedInBriefingTitle?: string;
  redactedContent?: string;
  userRemovedExcerpts?: string[];
}

export interface MemoryVersion {
  version: number;
  statement: string;
  updatedAt: string;
  source: string;
  reason?: string;
}

export interface CanonicalMemory {
  id: string;
  statement: string;
  category: MemoryCategory;
  sourceId: string;
  sourceReference: string;
  originalContent?: string;
  aiInterpretation?: string;
  confidence: ConfidenceLevel;
  status: MemoryStatus;
  createdAt: string;
  updatedAt: string;
  lastUsedAt: string;
  reason?: string;
  versions: MemoryVersion[];
}

export interface PrivacyActivity {
  id: string;
  action: string;
  sourceId?: string;
  sourceName?: string;
  timestamp: string;
  result: string;
}
