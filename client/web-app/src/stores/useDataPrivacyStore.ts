import { create } from 'zustand';
import {
  type GlobalCaptureStatus,
  type ConnectedSourceAccess,
  type CapturedRecord,
  type CanonicalMemory,
  type PrivacyActivity
  } from '../types/dataPrivacy';
import {
  fillTemplate,
  getPrivacyCatalog,
  localizeControl,
  localizeSourceName,
} from '../i18n/privacyCatalog';
import { usePreferencesStore } from './usePreferencesStore';

const lang = () => usePreferencesStore.getState().language;

interface DataPrivacyState {
  globalCaptureStatus: GlobalCaptureStatus;
  lastDataReview: string;
  sources: ConnectedSourceAccess[];
  records: CapturedRecord[];
  memories: CanonicalMemory[];
  auditLogs: PrivacyActivity[];

  // Actions
  setGlobalCaptureStatus: (status: GlobalCaptureStatus) => void;
  toggleSourceCapture: (sourceId: string, enabled: boolean) => void;
  refreshSource: (sourceId: string) => void;
  updateSourceGranularControl: (sourceId: string, controlId: string, enabled: boolean) => void;
  disconnectSource: (sourceId: string, deleteData: boolean) => void;
  deleteCapturedRecord: (recordId: string) => void;
  redactCapturedRecord: (recordId: string, newContent: string, removedExcerpt: string) => void;
  bulkDeleteRecords: (recordIds: string[]) => void;
  deleteAllSourceData: (sourceId: string) => void;
  confirmMemoryCandidate: (memoryId: string) => void;
  rejectMemoryCandidate: (memoryId: string) => void;
  editMemory: (memoryId: string, newStatement: string) => void;
  deleteMemory: (memoryId: string) => void;
  addAuditLog: (action: string, sourceName?: string, result?: string) => void;
}

const initialSources: ConnectedSourceAccess[] = [
  {
    id: 'src-discord',
    name: 'Discord',
    platform: 'Discord',
    accountEmailOrUser: 'alex_dev#1234',
    connected: true,
    captureEnabled: true,
    coverage: 'continuous',
    lastReviewedAt: 'today935',
    capturedRecordsCount: 348,
    icon: 'MessageSquare',
    permissions: {
      canAccess: ['discord.server', 'discord.announcements', 'discord.teamChat', 'discord.publicThreads'],
      cannotAccess: ['discord.dms', 'discord.personalServers', 'discord.voice', 'discord.friends'],
      granularControls: [
        { id: 'gc-disc-announcements', enabled: true },
        { id: 'gc-disc-teamchat', enabled: true },
        { id: 'gc-disc-general', enabled: false },
        { id: 'gc-disc-dms', enabled: false, alwaysUnavailable: true },
      ],
    },
  },
  {
    id: 'src-canvas',
    name: 'Canvas LMS',
    platform: 'Learning Platform',
    accountEmailOrUser: 'alex.student (SAML SSO)',
    connected: true,
    captureEnabled: true,
    coverage: 'continuous',
    lastReviewedAt: 'today700',
    capturedRecordsCount: 412,
    icon: 'VLearn',
    permissions: {
      canAccess: ['canvas.syllabus', 'canvas.assignments', 'canvas.gradebook', 'canvas.announcements'],
      cannotAccess: ['canvas.otherCourses', 'canvas.tuition', 'canvas.peerGrades'],
      granularControls: [
        { id: 'gc-canvas-assignments', enabled: true },
        { id: 'gc-canvas-announcements', enabled: true },
        { id: 'gc-canvas-discussions', enabled: false },
      ],
    },
  },
  {
    id: 'src-email',
    name: 'Gmail',
    platform: 'Email',
    accountEmailOrUser: 'alex.student@university.edu',
    connected: true,
    captureEnabled: true,
    coverage: 'continuous',
    lastReviewedAt: 'today815',
    capturedRecordsCount: 284,
    icon: 'Mail',
    permissions: {
      canAccess: ['email.directors', 'email.newsletter', 'email.schedule'],
      cannotAccess: ['email.personal', 'email.finance', 'email.security'],
      granularControls: [
        { id: 'gc-email-director', enabled: true },
        { id: 'gc-email-newsletter', enabled: true },
        { id: 'gc-email-personal', enabled: false, alwaysUnavailable: true },
      ],
    },
  },
  {
    id: 'src-calendar',
    name: 'Google Drive & Calendar',
    platform: 'Program Calendar',
    accountEmailOrUser: 'alex.student@gmail.com',
    connected: true,
    captureEnabled: false,
    coverage: 'limited',
    lastReviewedAt: 'yesterday600',
    capturedRecordsCount: 204,
    icon: 'GoogleCalendar',
    permissions: {
      canAccess: ['cal.events', 'cal.officeHours', 'cal.driveFolders'],
      cannotAccess: ['cal.privateEvents', 'cal.unsharedDrive', 'cal.photos'],
      granularControls: [
        { id: 'gc-cal-officehours', enabled: true },
        { id: 'gc-cal-deadlines', enabled: true },
        { id: 'gc-drive-shared', enabled: false },
      ],
    },
  },
];

const initialRecords: CapturedRecord[] = [
  {
    id: 'rec-1',
    sourceId: 'src-discord',
    sourceName: 'Discord',
    sourceLocation: '#announcements',
    originalTimestamp: 'July 30, 2026 · 8:42 AM',
    capturedAt: 'July 30, 2026 · 8:44 AM',
    contentPreview: 'The proposal deadline has been moved to July 29 at 11:59 PM to give everyone extra time following server downtime.',
    originalContent: 'Attention Cohort! The Milestone 1 Proposal submission deadline has been officially moved to July 29 at 11:59 PM to give everyone extra time following yesterday\'s AWS server downtime. Please update your team calendars accordingly.',
    extractedInformation: 'Milestone 1 Proposal deadline updated to July 29 at 11:59 PM.',
    confidence: 'Certain',
    retentionStatus: 'active',
    processingStatus: 'used_in_briefing',
    usedInBriefingTitle: 'Daily Briefing — July 30, 2026',
  },
  {
    id: 'rec-2',
    sourceId: 'src-canvas',
    sourceName: 'Canvas LMS',
    sourceLocation: 'Assignments Portal',
    originalTimestamp: 'July 28, 2026 · 11:00 PM',
    capturedAt: 'July 29, 2026 · 7:00 AM',
    contentPreview: 'Milestone 1 Proposal Portal: Due July 28 at 11:59 PM. Maximum 5 pages PDF format.',
    originalContent: 'Milestone 1 Proposal Portal: Submit your initial 5-page research proposal document in PDF format. Submission deadline: July 28 at 11:59 PM PST. Late submissions subject to 10% penalty per day.',
    extractedInformation: 'Canvas portal displays submission deadline as July 28 at 11:59 PM.',
    confidence: 'Possible',
    retentionStatus: 'active',
    processingStatus: 'used_in_briefing',
    usedInBriefingTitle: 'Deadline Discrepancy Analysis',
  },
  {
    id: 'rec-3',
    sourceId: 'src-email',
    sourceName: 'Gmail',
    sourceLocation: 'Program Email Digest',
    originalTimestamp: 'July 29, 2026 · 6:30 AM',
    capturedAt: 'July 29, 2026 · 6:32 AM',
    contentPreview: 'Reminder: Mentor Office Hours with Dr. Chen are scheduled for tomorrow, July 30 at 3:00 PM PST via Zoom.',
    originalContent: 'Dear Scholars, This is a reminder that Dr. Chen will be holding dedicated office hours tomorrow, Thursday July 30 from 3:00 PM to 4:30 PM PST. Bring your pitch deck outlines and technical architecture diagrams. Zoom link: https://zoom.us/j/99881122',
    extractedInformation: 'Mentor Office Hours with Dr. Chen on July 30 at 3:00 PM PST.',
    confidence: 'Certain',
    retentionStatus: 'active',
    processingStatus: 'used_in_briefing',
    usedInBriefingTitle: 'Schedule Summary & Preparation',
  },
  {
    id: 'rec-4',
    sourceId: 'src-discord',
    sourceName: 'Discord',
    sourceLocation: '#team-chat',
    originalTimestamp: 'July 29, 2026 · 2:15 PM',
    capturedAt: 'July 29, 2026 · 2:18 PM',
    contentPreview: 'Alex: I can draft the architecture overview slide before our sync if anyone wants to review.',
    originalContent: 'Alex: I can draft the architecture overview slide before our sync if anyone wants to review. We should also double check the API endpoints with Dr. Chen tomorrow during office hours.',
    extractedInformation: 'Draft architecture overview slide before team sync.',
    confidence: 'Possible',
    retentionStatus: 'active',
    processingStatus: 'saved_as_memory',
    usedInBriefingTitle: 'Team Action Items Tracker',
  },
  {
    id: 'rec-5',
    sourceId: 'src-calendar',
    sourceName: 'Google Drive & Calendar',
    sourceLocation: 'Program Calendar',
    originalTimestamp: 'July 27, 2026 · 9:00 AM',
    capturedAt: 'July 27, 2026 · 9:05 AM',
    contentPreview: 'Cohort Demo Day Presentation: August 15, 2026 · 10:00 AM - 1:00 PM PST',
    originalContent: 'Event: Final Cohort Demo Day & Investor Showcase. Date: August 15, 2026. Location: Main Auditorium & Virtual Stream. Attendance mandatory for all scholars.',
    extractedInformation: 'Final Cohort Demo Day scheduled for August 15, 2026.',
    confidence: 'Certain',
    retentionStatus: 'active',
    processingStatus: 'used_in_briefing',
  },
  {
    id: 'rec-6',
    sourceId: 'src-canvas',
    sourceName: 'Canvas LMS',
    sourceLocation: 'Syllabus & Milestones',
    originalTimestamp: 'July 25, 2026 · 4:00 PM',
    capturedAt: 'July 26, 2026 · 7:00 AM',
    contentPreview: 'Technical Stack Requirement: Node.js / React with full-stack TypeScript architecture.',
    originalContent: 'Project Specification: All scholar team prototypes must be constructed using TypeScript, Node.js runtime, and standard React component state architecture with server proxy API routes.',
    extractedInformation: 'Full-stack TypeScript and React requirement confirmed.',
    confidence: 'Certain',
    retentionStatus: 'active',
    processingStatus: 'saved_as_memory',
  },
  {
    id: 'rec-7',
    sourceId: 'src-email',
    sourceName: 'Gmail',
    sourceLocation: 'Weekly Newsletter',
    originalTimestamp: 'July 22, 2026 · 9:00 AM',
    capturedAt: 'July 22, 2026 · 9:05 AM',
    contentPreview: 'Scholar Profile Note: Alex prefers daily briefing notifications sent at 8:00 AM PST.',
    originalContent: 'Survey Response: Alex requested morning digest delivery at 8:00 AM PST every weekday with summary bullets highlighted.',
    extractedInformation: 'User prefers 8:00 AM PST daily briefings.',
    confidence: 'Certain',
    retentionStatus: 'active',
    processingStatus: 'saved_as_memory',
  },
];

const initialMemories: CanonicalMemory[] = [
  {
    id: 'mem-1',
    statement: 'Your Milestone 1 Proposal submission deadline is July 29 at 11:59 PM PST (updated via Discord announcement).',
    category: 'Deliverable rule',
    sourceId: 'src-discord',
    sourceReference: 'Discord #announcements',
    originalContent: 'The proposal deadline has been officially moved to July 29 at 11:59 PM to give everyone extra time.',
    aiInterpretation: 'The proposal deadline has been extended by 24 hours to July 29 at 11:59 PM.',
    confidence: 'Certain',
    status: 'confirmed',
    createdAt: 'July 30, 2026',
    updatedAt: 'July 30, 2026',
    lastUsedAt: 'Today',
    versions: [
      {
        version: 2,
        statement: 'Your Milestone 1 Proposal submission deadline is July 29 at 11:59 PM PST (updated via Discord announcement).',
        updatedAt: 'July 30, 2026',
        source: 'Discord #announcements',
        reason: 'Deadline extended by 24 hours due to server downtime.',
      },
      {
        version: 1,
        statement: 'Your Milestone 1 Proposal submission deadline is July 28 at 11:59 PM PST.',
        updatedAt: 'July 28, 2026',
        source: 'Canvas LMS Portal',
        reason: 'Initial assignment entry on Canvas gradebook.',
      },
    ],
  },
  {
    id: 'mem-2',
    statement: 'You prefer daily morning briefings delivered at 8:00 AM PST with bullet summaries.',
    category: 'Personal preference',
    sourceId: 'src-email',
    sourceReference: 'Gmail Newsletter Survey',
    originalContent: 'Alex requested morning digest delivery at 8:00 AM PST every weekday with summary bullets highlighted.',
    aiInterpretation: 'User explicitly set preferred briefing time to 8:00 AM PST.',
    confidence: 'Certain',
    status: 'confirmed',
    createdAt: 'July 22, 2026',
    updatedAt: 'July 22, 2026',
    lastUsedAt: 'Today',
    versions: [
      {
        version: 1,
        statement: 'You prefer daily morning briefings delivered at 8:00 AM PST with bullet summaries.',
        updatedAt: 'July 22, 2026',
        source: 'Gmail Newsletter Survey',
      },
    ],
  },
  {
    id: 'mem-3',
    statement: 'Your primary program mentor is Dr. Chen (Office Hours: Thursdays at 3:00 PM PST).',
    category: 'Program context',
    sourceId: 'src-email',
    sourceReference: 'Gmail Program Digest',
    originalContent: 'Dr. Chen will be holding dedicated office hours tomorrow, Thursday July 30 from 3:00 PM to 4:30 PM PST.',
    aiInterpretation: 'Primary mentor is Dr. Chen with weekly Thursday office hours.',
    confidence: 'Certain',
    status: 'confirmed',
    createdAt: 'July 20, 2026',
    updatedAt: 'July 29, 2026',
    lastUsedAt: 'Yesterday',
    versions: [
      {
        version: 1,
        statement: 'Your primary program mentor is Dr. Chen (Office Hours: Thursdays at 3:00 PM PST).',
        updatedAt: 'July 20, 2026',
        source: 'Gmail Program Digest',
      },
    ],
  },
  {
    id: 'mem-4',
    statement: 'mondaiy detected a potential task: Prepare pitch deck architecture overview slides prior to mentor office hours.',
    category: 'Deliverable rule',
    sourceId: 'src-discord',
    sourceReference: 'Discord #team-chat',
    originalContent: 'I can draft the architecture overview slide before our sync if anyone wants to review.',
    aiInterpretation: 'Suggested deliverable task extracted from Discord project conversation.',
    confidence: 'Possible',
    status: 'pending_review',
    createdAt: 'July 29, 2026',
    updatedAt: 'July 29, 2026',
    lastUsedAt: 'July 29, 2026',
    reason: 'New draft item suggested from team conversation.',
    versions: [
      {
        version: 1,
        statement: 'mondaiy detected a potential task: Prepare pitch deck architecture overview slides prior to mentor office hours.',
        updatedAt: 'July 29, 2026',
        source: 'Discord #team-chat',
      },
    ],
  },
  {
    id: 'mem-5',
    statement: 'Discrepancy detected between Canvas assignment portal (July 28) and Discord announcement (July 29).',
    category: 'Mentor guidance',
    sourceId: 'src-canvas',
    sourceReference: 'Canvas vs Discord',
    originalContent: 'Sources disagree on official proposal deadline.',
    aiInterpretation: 'Requires explicit mentor verification or submission confirmation.',
    confidence: 'Ask Mentor',
    status: 'low_confidence',
    createdAt: 'July 29, 2026',
    updatedAt: 'July 30, 2026',
    lastUsedAt: 'Today',
    versions: [
      {
        version: 1,
        statement: 'Discrepancy detected between Canvas assignment portal (July 28) and Discord announcement (July 29).',
        updatedAt: 'July 29, 2026',
        source: 'Canvas vs Discord',
      },
    ],
  },
];

const initialAuditLogs: PrivacyActivity[] = [
  { id: 'aud-1', action: '', sourceId: 'src-calendar', timestamp: '', result: '' },
  { id: 'aud-2', action: '', sourceId: 'src-discord', timestamp: '', result: '' },
  { id: 'aud-3', action: '', timestamp: '', result: '' },
];

export const useDataPrivacyStore = create<DataPrivacyState>((set, get) => ({
  globalCaptureStatus: 'active',
  lastDataReview: 'today942',
  sources: initialSources,
  records: initialRecords,
  memories: initialMemories,
  auditLogs: initialAuditLogs,

  setGlobalCaptureStatus: (status) => {
    set({ globalCaptureStatus: status });
    const copy =
      status === 'paused'
        ? getPrivacyCatalog(lang()).runtime.pausedAll
        : getPrivacyCatalog(lang()).runtime.resumedAll;
    get().addAuditLog(copy.action, copy.sourceName, copy.result);
  },

  toggleSourceCapture: (sourceId, enabled) => {
    set((state) => ({
      sources: state.sources.map((s) =>
        s.id === sourceId ? { ...s, captureEnabled: enabled } : s
      ),
    }));
    const src = get().sources.find((s) => s.id === sourceId);
    const sourceName = localizeSourceName(sourceId, src?.name || 'source', lang());
    const tpl = enabled
      ? getPrivacyCatalog(lang()).runtime.resumedSource
      : getPrivacyCatalog(lang()).runtime.pausedSource;
    get().addAuditLog(
      fillTemplate(tpl.action, { source: sourceName }),
      sourceName,
      tpl.result,
    );
  },

  refreshSource: (sourceId) => {
    const reviewedAt = 'justNow';
    set((state) => ({
      sources: state.sources.map((s) =>
        s.id === sourceId ? { ...s, lastReviewedAt: reviewedAt } : s
      ),
      lastDataReview: reviewedAt,
    }));
    const src = get().sources.find((s) => s.id === sourceId);
    const sourceName = localizeSourceName(sourceId, src?.name || 'source', lang());
    const tpl = getPrivacyCatalog(lang()).runtime.refreshedSource;
    get().addAuditLog(
      fillTemplate(tpl.action, { source: sourceName }),
      sourceName,
      tpl.result,
    );
  },

  updateSourceGranularControl: (sourceId, controlId, enabled) => {
    set((state) => ({
      sources: state.sources.map((s) => {
        if (s.id !== sourceId) return s;
        return {
          ...s,
          permissions: {
            ...s.permissions,
            granularControls: s.permissions.granularControls.map((c) =>
              c.id === controlId ? { ...c, enabled } : c
            ),
          },
        };
      }),
    }));
    const src = get().sources.find((s) => s.id === sourceId);
    const sourceName = localizeSourceName(sourceId, src?.name || 'source', lang());
    const controlName = localizeControl(controlId, lang()).name;
    const tpl = enabled
      ? getPrivacyCatalog(lang()).runtime.controlEnabled
      : getPrivacyCatalog(lang()).runtime.controlDisabled;
    get().addAuditLog(
      fillTemplate(tpl.action, { source: sourceName, control: controlName }),
      sourceName,
      tpl.result,
    );
  },

  disconnectSource: (sourceId, deleteData) => {
    const src = get().sources.find((s) => s.id === sourceId);
    if (!src) return;

    set((state) => ({
      sources: state.sources.map((s) =>
        s.id === sourceId
          ? { ...s, connected: false, captureEnabled: false, coverage: 'expired' }
          : s
      ),
      records: deleteData
        ? state.records.filter((r) => r.sourceId !== sourceId)
        : state.records,
      memories: deleteData
        ? state.memories.filter((m) => m.sourceId !== sourceId)
        : state.memories,
    }));

    get().addAuditLog(
      `Disconnected ${src.name}`,
      src.name,
      deleteData ? 'Source disconnected and associated stored data deleted.' : 'Source disconnected. Existing data retained.'
    );
  },

  deleteCapturedRecord: (recordId) => {
    const rec = get().records.find((r) => r.id === recordId);
    set((state) => ({
      records: state.records.filter((r) => r.id !== recordId),
    }));
    get().addAuditLog(
      'Deleted captured record',
      rec?.sourceName,
      `Removed record "${rec?.extractedInformation || recordId}" from retained data.`
    );
  },

  redactCapturedRecord: (recordId, newContent, removedExcerpt) => {
    set((state) => ({
      records: state.records.map((r) => {
        if (r.id !== recordId) return r;
        const excerpts = r.userRemovedExcerpts || [];
        return {
          ...r,
          originalContent: newContent,
          retentionStatus: 'edited',
          userRemovedExcerpts: [...excerpts, removedExcerpt],
        };
      }),
    }));
    const rec = get().records.find((r) => r.id === recordId);
    get().addAuditLog(
      'Redacted content from record',
      rec?.sourceName,
      `Removed text excerpt: "${removedExcerpt.slice(0, 30)}..."`
    );
  },

  bulkDeleteRecords: (recordIds) => {
    const count = recordIds.length;
    set((state) => ({
      records: state.records.filter((r) => !recordIds.includes(r.id)),
    }));
    get().addAuditLog('Bulk deleted records', 'Multiple Sources', `Removed ${count} captured records from retained storage.`);
  },

  deleteAllSourceData: (sourceId) => {
    const src = get().sources.find((s) => s.id === sourceId);
    const count = get().records.filter((r) => r.sourceId === sourceId).length;
    set((state) => ({
      records: state.records.filter((r) => r.sourceId !== sourceId),
      memories: state.memories.filter((m) => m.sourceId !== sourceId),
    }));
    get().addAuditLog(
      `Deleted all data for ${src?.name || sourceId}`,
      src?.name,
      `Purged ${count} captured records and related memory items.`
    );
  },

  confirmMemoryCandidate: (memoryId) => {
    set((state) => ({
      memories: state.memories.map((m) =>
        m.id === memoryId ? { ...m, status: 'confirmed', updatedAt: 'Today' } : m
      ),
    }));
    const mem = get().memories.find((m) => m.id === memoryId);
    get().addAuditLog('Confirmed memory record', mem?.sourceReference, `Validated memory statement.`);
  },

  rejectMemoryCandidate: (memoryId) => {
    set((state) => ({
      memories: state.memories.map((m) =>
        m.id === memoryId ? { ...m, status: 'rejected', updatedAt: 'Today' } : m
      ),
    }));
    const mem = get().memories.find((m) => m.id === memoryId);
    get().addAuditLog('Rejected memory candidate', mem?.sourceReference, `Memory candidate rejected by user.`);
  },

  editMemory: (memoryId, newStatement) => {
    set((state) => ({
      memories: state.memories.map((m) => {
        if (m.id !== memoryId) return m;
        const newVersionNum = (m.versions.length || 0) + 1;
        const newVersions = [
          {
            version: newVersionNum,
            statement: newStatement,
            updatedAt: 'Today',
            source: 'User Manual Edit',
            reason: 'User directly updated memory statement.',
          },
          ...m.versions,
        ];
        return {
          ...m,
          statement: newStatement,
          updatedAt: 'Today',
          versions: newVersions,
        };
      }),
    }));
    get().addAuditLog('Edited memory record', 'Memory Inspector', `Updated memory statement to new version.`);
  },

  deleteMemory: (memoryId) => {
    const mem = get().memories.find((m) => m.id === memoryId);
    set((state) => ({
      memories: state.memories.filter((m) => m.id !== memoryId),
    }));
    get().addAuditLog('Deleted memory record', mem?.sourceReference, `Memory removed from retained personalization storage.`);
  },

  addAuditLog: (action, sourceName, result) => {
    const newLog: PrivacyActivity = {
      id: `aud-${Date.now()}`,
      action,
      sourceName: sourceName || 'System',
      timestamp: 'Just now',
      result: result || 'Action executed successfully.',
    };
    set((state) => ({
      auditLogs: [newLog, ...state.auditLogs],
    }));
  },
}));
