export type ConfidenceLevel = 'certain' | 'possible' | 'ask_mentor';

export type CommitmentLevel = 'committed' | 'draft';

export type PriorityLevel = 'urgent' | 'important' | 'update' | 'suggestion';

export type FeedbackType = 'relevant' | 'not_relevant' | 'inaccurate' | 'already_knew';

export type BriefingItem = {
  id: string;
  title: string;
  summary: string;
  relevance: string;
  nextAction: string;

  source: {
    platform: string;
    location: string;
    author?: string;
    timestamp: string;
    rawContent?: string;
  };

  confidence: ConfidenceLevel;
  commitment: CommitmentLevel;
  priority: PriorityLevel;

  category: 'needs_attention' | 'changes' | 'upcoming' | 'possible_tasks';

  dueDate?: string;
  previousValue?: string;
  currentValue?: string;

  conflictDetails?: {
    sourceA: {
      platform: string;
      location: string;
      value: string;
      timestamp: string;
      content: string;
    };
    sourceB: {
      platform: string;
      location: string;
      value: string;
      timestamp: string;
      content: string;
    };
    mentorVerificationDraft?: string;
  };

  userFeedback?: FeedbackType;
  dismissed?: boolean;
};

export type BriefingFeedbackOverall = 'useful' | 'partly_useful' | 'not_useful';
