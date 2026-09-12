import { apiRequest } from './apiClient';

export type ConnectionProvider = 'discord' | 'google' | 'telegram' | 'jira' | 'outlook' | 'slack';

export type IntegrationResponse = {
  id: number;
  provider: ConnectionProvider;
  accountLabel: string | null;
  expiresAt: string | null;
};

export type SourceInfo = {
  id: string;
  name: string;
  itemCount: number | null;
};

export type ConnectionStatus = {
  provider: ConnectionProvider;
  connected: boolean;
  accountLabel: string | null;
  expiresAt: string | null;
  // true khi refresh token đã bị provider thu hồi/hết hạn — connected vẫn
  // true (bản ghi tồn tại) nhưng mọi lời gọi API thật sẽ luôn lỗi cho tới khi
  // người dùng bấm kết nối lại (đăng nhập lại qua OAuth, không cần tự đi thu
  // hồi quyền thủ công — provider luôn ép cấp token mới ở mỗi lần connect).
  needsReconnect: boolean;
  lastError: string | null;
};

export const listConnections = (accessToken: string): Promise<{ connections: ConnectionStatus[] }> =>
  apiRequest('/api/v1/connections', { accessToken });

export const listIntegrations = (accessToken: string): Promise<{ integrations: IntegrationResponse[] }> =>
  apiRequest('/api/v1/integrations', { accessToken });

export const listIntegrationSources = (
  integrationId: number,
  accessToken: string,
): Promise<{ sources: SourceInfo[]; warnings: string[] }> =>
  apiRequest(`/api/v1/integrations/${integrationId}/sources`, { accessToken });

export const createConnectIntent = (
  provider: ConnectionProvider,
  extRedirectUri: string,
  accessToken: string,
): Promise<{ authorizeUrl: string }> =>
  apiRequest(`/api/v1/connections/${provider}/intent`, {
    method: 'POST',
    body: { extRedirectUri },
    accessToken,
  });

export const disconnect = (provider: ConnectionProvider, accessToken: string): Promise<void> =>
  apiRequest(`/api/v1/connections/${provider}/disconnect`, { method: 'POST', accessToken });
