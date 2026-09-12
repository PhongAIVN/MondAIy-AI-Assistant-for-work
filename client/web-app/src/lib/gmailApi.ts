import { apiRequest } from './apiClient';
export { isGmailBriefingIntent } from './gmailIntent';

export type ConnectionStatus = {
  provider: 'discord' | 'google' | 'telegram';
  connected: boolean;
  accountLabel: string | null;
  expiresAt: string | null;
};

export type Integration = {
  id: number;
  provider: string;
  accountLabel: string | null;
  expiresAt: string | null;
};

export type GmailSource = {
  id: string;
  name: string;
  itemCount: number | null;
};

export type GmailStatus = {
  source: 'gmail';
  status: 'disconnected' | 'connected_pending_sync' | 'syncing' | 'connected_ready' | 'error' | string;
  accountEmail: string | null;
  permission: string | null;
  emailCount: number;
  lastSyncedAt: string | null;
  oauthValid: boolean;
  mailboxAccessible: boolean;
  initialSyncCompleted: boolean;
  lastError: string | null;
};

export async function getConnections(accessToken: string): Promise<ConnectionStatus[]> {
  const data = await apiRequest<{ connections: ConnectionStatus[] }>('/api/v1/connections', { accessToken });
  return data.connections;
}

export async function getIntegrations(accessToken: string): Promise<Integration[]> {
  const data = await apiRequest<{ integrations: Integration[] }>('/api/v1/integrations', { accessToken });
  return data.integrations;
}

export async function getGmailSources(accessToken: string, integrationId: number): Promise<GmailSource[]> {
  const data = await apiRequest<{ sources: GmailSource[] }>(`/api/v1/integrations/${integrationId}/sources`, { accessToken });
  return data.sources;
}

export async function createGoogleConnectIntent(accessToken: string, redirectUri: string): Promise<string> {
  const data = await apiRequest<{ authorizeUrl: string }>('/api/v1/connections/gmail/oauth/start', {
    method: 'POST',
    accessToken,
    body: { extRedirectUri: redirectUri },
  });
  return data.authorizeUrl;
}

export async function getGmailStatus(accessToken: string): Promise<GmailStatus> {
  return apiRequest<GmailStatus>('/api/v1/connections/gmail/status', { accessToken });
}

export async function startGmailInitialSync(accessToken: string): Promise<{ runId: number; status: string }> {
  return apiRequest<{ runId: number; status: string }>('/api/v1/connections/gmail/initial-sync', {
    method: 'POST',
    accessToken,
  });
}

export async function disconnectGoogle(accessToken: string): Promise<void> {
  await apiRequest('/api/v1/connections/google/disconnect', { method: 'POST', accessToken });
}
