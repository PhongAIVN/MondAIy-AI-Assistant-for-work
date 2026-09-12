import { apiRequest } from './apiClient';

// Bốn năng lực học độc lập — khớp LEARNING_CAPABILITIES ở src/models/learning.py.
export type LearningCapability =
  | 'chat_learning'
  | 'adaptive_style'
  | 'learned_skills'
  | 'routine_learning';

export type ConsentState = {
  capability: LearningCapability;
  enabled: boolean;
  policyVersion: string | null;
  consentedAt: string | null;
  revokedAt: string | null;
};

export type LearningCandidateType = 'style_preference' | 'skill' | 'routine';

export type LearningCandidate = {
  id: number;
  candidateKey: string;
  version: number;
  candidateType: LearningCandidateType;
  status: string;
  payload: Record<string, unknown>;
  confidence: number | null;
  expiresAt: string | null;
  createdAt: string;
};

export type LearningScope = 'style' | 'skills' | 'routines' | 'all';

export type LearningAuditEvent = {
  id: number;
  actor: string;
  action: string;
  targetType: string;
  targetRef: string;
  reasonCodes: string[];
  createdAt: string;
};

export const getLearningConsent = (accessToken: string): Promise<{ consents: ConsentState[] }> =>
  apiRequest('/api/v1/adaptive-learning/consent', { accessToken });

export const updateLearningConsent = (
  capability: LearningCapability,
  enabled: boolean,
  accessToken: string,
): Promise<{ consents: ConsentState[] }> =>
  apiRequest('/api/v1/adaptive-learning/consent', {
    method: 'PATCH',
    body: { capability, enabled },
    accessToken,
  });

export const listLearningCandidates = (accessToken: string): Promise<{ candidates: LearningCandidate[] }> =>
  apiRequest('/api/v1/adaptive-learning/candidates', { accessToken });

export const rejectLearningCandidate = (
  id: number,
  reasonCodes: string[],
  accessToken: string,
): Promise<LearningCandidate> =>
  apiRequest(`/api/v1/adaptive-learning/candidates/${id}/reject`, {
    method: 'POST',
    body: { reasonCodes },
    accessToken,
  });

export const resetLearning = (scope: LearningScope, accessToken: string): Promise<{ scope: string; forgotten: number }> =>
  apiRequest(`/api/v1/adaptive-learning?scope=${encodeURIComponent(scope)}`, {
    method: 'DELETE',
    accessToken,
  });

export const listLearningAudit = (accessToken: string): Promise<{ events: LearningAuditEvent[] }> =>
  apiRequest('/api/v1/adaptive-learning/audit', { accessToken });
