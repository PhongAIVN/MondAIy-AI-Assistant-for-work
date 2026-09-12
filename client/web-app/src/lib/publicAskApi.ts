import { apiRequest } from './apiClient';

export type PublicAskRole = 'user' | 'assistant';

export interface PublicAskTurn {
  role: PublicAskRole;
  content: string;
}

export interface PublicAskResult {
  reply: string;
  turnsUsed: number;
  limitReached: boolean;
}

export async function askPublic(message: string, history: PublicAskTurn[]): Promise<PublicAskResult> {
  return apiRequest<PublicAskResult>('/api/v1/public-ask/messages', {
    method: 'POST',
    body: { message, history },
  });
}
