// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SourceLibraryModal } from '../src/components/briefing/SourceLibraryModal';

const mocks = vi.hoisted(() => ({
  listConnections: vi.fn(),
  disconnect: vi.fn(),
  addToast: vi.fn(),
  closeModal: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({
    activeModal: 'source_library',
    closeModal: mocks.closeModal,
    addToast: mocks.addToast,
  }),
}));

vi.mock('../src/lib/connectionsApi', () => ({
  listConnections: mocks.listConnections,
  disconnect: mocks.disconnect,
}));

vi.mock('../src/stores/usePipelineRunStore', () => ({
  usePipelineRunStore: { getState: () => ({ loadConnections: vi.fn() }) },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('SourceLibraryModal', () => {
  it('only shows sources that are actually connected, with no search bar or category filters', async () => {
    mocks.listConnections.mockResolvedValue({
      connections: [
        { provider: 'google', connected: true, accountLabel: 'alex@gmail.com', expiresAt: null },
        { provider: 'jira', connected: true, accountLabel: 'alex.scholar', expiresAt: null },
        { provider: 'outlook', connected: true, accountLabel: 'alex@outlook.com', expiresAt: null },
        { provider: 'discord', connected: false, accountLabel: null, expiresAt: null },
        { provider: 'telegram', connected: false, accountLabel: null, expiresAt: null },
      ],
    });

    render(<SourceLibraryModal />);

    expect(await screen.findByText('Google')).toBeTruthy();
    expect(screen.getByText('Jira')).toBeTruthy();
    expect(screen.getByText('Outlook')).toBeTruthy();
    expect(screen.queryByText('Discord')).toBeNull();
    expect(screen.queryByText('Telegram')).toBeNull();
    expect(screen.queryByText(/Canvas LMS|Google Drive|Notion|Program Portal/)).toBeNull();

    expect(screen.queryByPlaceholderText(/search sources/i)).toBeNull();
    expect(screen.queryByPlaceholderText(/tìm kiếm nguồn/i)).toBeNull();
    expect(screen.queryByText(/LMS & Academics/i)).toBeNull();
    expect(screen.queryByText(/Storage & Docs/i)).toBeNull();
  });

  it('asks for confirmation before disconnecting, then reloads the connected list', async () => {
    const user = userEvent.setup();
    mocks.listConnections
      .mockResolvedValueOnce({
        connections: [{ provider: 'jira', connected: true, accountLabel: 'alex.scholar', expiresAt: null }],
      })
      .mockResolvedValueOnce({ connections: [] });
    mocks.disconnect.mockResolvedValue(undefined);

    render(<SourceLibraryModal />);

    await screen.findByText('Jira');
    await user.click(screen.getByRole('button', { name: /disconnect|ngắt kết nối/i }));

    // Bấm nút ở card chỉ mở dialog xác nhận — chưa gọi API ngắt thật.
    const dialog = await screen.findByRole('dialog');
    expect(mocks.disconnect).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('button', { name: /disconnect|ngắt kết nối/i }));

    await waitFor(() => expect(mocks.disconnect).toHaveBeenCalledWith('jira', 'access-token'));
    await waitFor(() => expect(mocks.listConnections).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('Jira')).toBeNull());
  });
});
