import { type ConfidenceLevel, type CommitmentLevel, type PriorityLevel } from './briefing';

export type TaskStatus = 'pending' | 'in_progress' | 'completed';

export type TaskItem = {
  id: string;
  title: string;
  description: string;
  dueDate: string;
  status: TaskStatus;
  priority: PriorityLevel;
  confidence: ConfidenceLevel;
  commitment: CommitmentLevel;
  
  source: {
    platform: string;
    location: string;
    timestamp: string;
  };
  
  estimatedPrepTime?: string;
  tags?: string[];
  createdFromBriefingId?: string;
};
