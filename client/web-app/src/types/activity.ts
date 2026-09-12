export type ActivityType = 
  | 'update_detected'
  | 'conflict_identified'
  | 'task_created'
  | 'task_completed'
  | 'feedback_submitted'
  | 'source_synced'
  | 'verification_drafted';

export type ActivityLog = {
  id: string;
  type: ActivityType;
  title: string;
  description: string;
  timestamp: string;
  source: {
    platform: string;
    location: string;
  };
  confidence?: 'certain' | 'possible' | 'ask_mentor';
  userConfirmed?: boolean;
};
