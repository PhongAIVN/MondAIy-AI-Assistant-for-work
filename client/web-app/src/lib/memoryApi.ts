import { apiRequest } from './apiClient';

export type MemoryStatus = 'candidate' | 'confirmed' | 'disputed' | 'superseded' | 'rejected' | 'forgotten';
export type MemorySource = 'user' | 'official' | 'inferred';

export type MemoryEvidence = {
  evidenceType: string;
  evidenceRef: string;
};

export type MemoryItem = {
  key: string;
  version: number;
  kind: string;
  subject: string;
  predicate: string;
  value: unknown;
  status: MemoryStatus;
  source: MemorySource;
  confidence: number;
  reinforcementCount: number;
  negativeFeedbackCount: number;
  firstObservedAt: string;
  lastReinforcedAt: string;
  evidence: MemoryEvidence[];
};

export type MemoryGraphNode = {
  id: string;
  label: string;
  nodeType: 'memory' | 'source';
  status?: string;
  metadata: Record<string, unknown>;
};

export type MemoryGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: 'evidence' | 'supersedes' | 'conflict';
  label?: string;
};

export type MemoryGraph = { nodes: MemoryGraphNode[]; edges: MemoryGraphEdge[] };

export const listLongTermMemory = (accessToken: string): Promise<{ memories: MemoryItem[] }> =>
  apiRequest('/api/v1/memory/long-term', { accessToken });

export const fetchMemoryGraph = (accessToken: string): Promise<MemoryGraph> =>
  apiRequest('/api/v1/memory/graph', { accessToken });

export const confirmLongTermMemory = (key: string, accessToken: string, version?: number): Promise<MemoryItem> =>
  apiRequest(`/api/v1/memory/long-term/${encodeURIComponent(key)}/confirm${version ? `?version=${version}` : ''}`, { method: 'POST', accessToken });

export const rejectLongTermMemory = (key: string, accessToken: string): Promise<MemoryItem> =>
  apiRequest(`/api/v1/memory/long-term/${encodeURIComponent(key)}/reject`, { method: 'POST', accessToken });

export const deleteLongTermMemory = (key: string, accessToken: string): Promise<void> =>
  apiRequest(`/api/v1/memory/long-term/${encodeURIComponent(key)}`, { method: 'DELETE', accessToken });

export const editLongTermMemory = (key: string, value: string, accessToken: string): Promise<MemoryItem> =>
  apiRequest(`/api/v1/memory/long-term/${encodeURIComponent(key)}`, {
    method: 'PATCH',
    body: { value },
    accessToken,
  });

export const clearLongTermMemory = (accessToken: string): Promise<void> =>
  apiRequest('/api/v1/memory/long-term', { method: 'DELETE', accessToken });
