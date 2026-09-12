import { apiRequest } from './apiClient';

export type PlannerPreferences = {
  workdayStartMinute: number;
  lunchStartMinute: number;
  lunchEndMinute: number;
  workdayEndMinute: number;
  happyTimeEnabled: boolean;
  happyTimeStartMinute: number;
  happyTimeEndMinute: number;
};

export type PlanBlock = {
  taskId: number;
  title: string;
  start: string;
  end: string;
  minutes: number;
  energy: 'deep' | 'shallow';
  why: string;
  communication?: string | null;
};

export type PlannerBusyBlock = {
  title: string;
  start: string;
  end: string;
  source: 'personal_calendar' | 'program_calendar';
  allDay: boolean;
  syncedAt: string | null;
};

export type PlannerRefresh = { newTaskCount: number; newUrgentTodayCount: number; rescheduleCount: number; atRiskCount: number };
export type PlannerRescheduleSuggestion = { taskId: number; title: string; fromStart: string | null; fromEnd: string | null; toStart: string | null; toEnd: string | null; reason: string };
export type PlannerPlan = {
  generatedAt: string;
  days: 1 | 7;
  blocks: PlanBlock[];
  atRisk: PlanBlock[];
  calendarBlocks: PlannerBusyBlock[];
  consideredTaskIds: number[];
  refresh: PlannerRefresh;
  rescheduleSuggestions: PlannerRescheduleSuggestion[];
  notes: string[];
};

export const getPlannerPreferences = (accessToken: string) =>
  apiRequest<PlannerPreferences>('/api/v1/planner/preferences', { accessToken });

export const updatePlannerPreferences = (accessToken: string, body: Partial<PlannerPreferences>) =>
  apiRequest<PlannerPreferences>('/api/v1/planner/preferences', { method: 'PATCH', accessToken, body });

export const generatePlannerPlan = (accessToken: string, days: 1 | 7, previous?: PlannerPlan | null) =>
  apiRequest<PlannerPlan>('/api/v1/planner/generate', {
    method: 'POST',
    accessToken,
    body: {
      days,
      knownTaskIds: previous?.consideredTaskIds ?? [],
      previousBlocks: previous?.blocks.map((block) => ({ taskId: block.taskId, start: block.start, end: block.end })) ?? [],
    },
  });
