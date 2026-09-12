import { apiRequest } from './apiClient';

export type RatingTrigger = 'action_count' | 'time_elapsed' | 'manual';

export type RatingPayload = {
  rating: number;
  feedback: string;
  trigger: RatingTrigger;
  sessionId: string;
  meaningfulActionCount: number;
  sessionDurationSeconds: number;
};

export const submitAppRating = (accessToken: string, payload: RatingPayload) =>
  apiRequest<{
    id: number;
    rating: number;
    feedback: string | null;
    bonusQuestionsAwarded: number;
    questionsRemaining: number;
  }>('/api/v1/ratings', {
    method: 'POST',
    accessToken,
    body: payload,
  });
