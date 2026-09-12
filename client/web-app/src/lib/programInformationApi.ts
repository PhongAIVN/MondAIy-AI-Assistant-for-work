import { apiRequest } from './apiClient';

export type ProgramInformationRequest = {
  id: number;
  status: 'open' | 'resolved';
  sharedQuestion: string;
  createdAt: string;
  resolvedItemId: number | null;
};

export function submitProgramInformationRequest(
  accessToken: string,
  sharedQuestion: string,
): Promise<ProgramInformationRequest> {
  return apiRequest<ProgramInformationRequest>('/api/v1/program-information/human-requests', {
    method: 'POST',
    accessToken,
    body: { sharedQuestion, consentToShare: true },
  });
}
