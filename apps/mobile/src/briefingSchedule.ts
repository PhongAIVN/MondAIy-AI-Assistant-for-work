import type { Routine } from './api/client';

export const BRIEFING_ROUTINE_NAME = 'Briefing tự động';

/** Không lấy routine mới nhất vì có thể đó là automation khác của người dùng. */
export const findBriefingRoutine = (routines: Routine[]): Routine | null =>
  routines.find((routine) => routine.name === BRIEFING_ROUTINE_NAME) ?? null;
