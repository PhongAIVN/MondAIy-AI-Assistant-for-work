import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ apiRequest: vi.fn() }));

vi.mock('../src/lib/apiClient', () => ({
  API_BASE_URL: 'http://test',
  ApiError: class ApiError extends Error {},
  apiRequest: mocks.apiRequest,
}));

import { fetchAutoSyncPreference, updateAutoSyncPreference } from '../src/lib/pipelineApi';

describe('auto-sync preference API client', () => {
  afterEach(() => vi.clearAllMocks());

  it('sends the caller preference as a PATCH request', async () => {
    mocks.apiRequest.mockResolvedValue({
      autoSyncEnabled: false,
      userAutoSyncEnabled: false,
      autoSyncIntervalMinutes: 180,
    });

    await updateAutoSyncPreference(false, 'access-token');

    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/runs/auto-sync-preference', {
      method: 'PATCH',
      body: { autoSyncEnabled: false },
      accessToken: 'access-token',
    });
  });

  it('loads the saved preference without sending a user identifier', async () => {
    mocks.apiRequest.mockResolvedValue({
      autoSyncEnabled: false,
      userAutoSyncEnabled: true,
      autoSyncIntervalMinutes: 180,
    });

    await fetchAutoSyncPreference('access-token');

    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/runs/auto-sync-preference', {
      accessToken: 'access-token',
    });
  });
});
