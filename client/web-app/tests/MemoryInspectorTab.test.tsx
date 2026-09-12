// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MemoryInspectorTab } from '../src/components/privacy/MemoryInspectorTab';

const mocks = vi.hoisted(() => ({
  listLongTermMemory: vi.fn(),
  confirmLongTermMemory: vi.fn(),
  rejectLongTermMemory: vi.fn(),
  deleteLongTermMemory: vi.fn(),
  editLongTermMemory: vi.fn(),
  clearLongTermMemory: vi.fn(),
  fetchMemoryGraph: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/memoryApi', () => ({
  listLongTermMemory: mocks.listLongTermMemory,
  confirmLongTermMemory: mocks.confirmLongTermMemory,
  rejectLongTermMemory: mocks.rejectLongTermMemory,
  deleteLongTermMemory: mocks.deleteLongTermMemory,
  editLongTermMemory: mocks.editLongTermMemory,
  clearLongTermMemory: mocks.clearLongTermMemory,
  fetchMemoryGraph: mocks.fetchMemoryGraph,
}));

const candidate = {
  key: 'user.response_style',
  version: 1,
  kind: 'preference',
  subject: 'user',
  predicate: 'response_style',
  value: 'concise',
  status: 'candidate' as const,
  source: 'inferred' as const,
  confidence: 0.7,
  reinforcementCount: 1,
  negativeFeedbackCount: 0,
  firstObservedAt: '2026-08-01T00:00:00Z',
  lastReinforcedAt: '2026-08-01T00:00:00Z',
  evidence: [{ evidenceType: 'conversation_message', evidenceRef: '42' }],
};

const confirmed = {
  ...candidate,
  key: 'user.timezone',
  predicate: 'timezone',
  value: 'Asia/Ho_Chi_Minh',
  status: 'confirmed' as const,
  source: 'user' as const,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('MemoryInspectorTab', () => {
  it('loads real memory from the API and renders predicate/value instead of a fabricated statement', async () => {
    mocks.listLongTermMemory.mockResolvedValue({ memories: [candidate, confirmed] });

    render(<MemoryInspectorTab />);

    expect(await screen.findByText(/response style: concise/i)).toBeTruthy();
    expect(screen.getByText(/timezone: Asia\/Ho_Chi_Minh/i)).toBeTruthy();
  });

  it('shows evidence for a candidate before the user confirms it', async () => {
    const user = userEvent.setup();
    mocks.listLongTermMemory.mockResolvedValue({ memories: [candidate] });

    render(<MemoryInspectorTab />);
    await screen.findByText(/response style: concise/i);
    await user.click(screen.getByRole('button', { name: /view source|xem nguồn/i }));

    expect(screen.getByText(/conversation message/i)).toBeTruthy();
    expect(screen.getByText(/#42/)).toBeTruthy();
  });

  it('confirms a candidate through the real API and refetches the list', async () => {
    const user = userEvent.setup();
    mocks.listLongTermMemory
      .mockResolvedValueOnce({ memories: [candidate] })
      .mockResolvedValueOnce({ memories: [{ ...candidate, status: 'confirmed' }] });
    mocks.confirmLongTermMemory.mockResolvedValue({ ...candidate, status: 'confirmed' });

    render(<MemoryInspectorTab />);
    await screen.findByText(/response style: concise/i);

    await user.click(screen.getByRole('button', { name: /confirm|xác nhận/i }));

    await waitFor(() => expect(mocks.confirmLongTermMemory).toHaveBeenCalledWith('user.response_style', 'access-token'));
    await waitFor(() => expect(mocks.listLongTermMemory).toHaveBeenCalledTimes(2));
  });

  it('deletes a memory through the real API', async () => {
    const user = userEvent.setup();
    mocks.listLongTermMemory
      .mockResolvedValueOnce({ memories: [confirmed] })
      .mockResolvedValueOnce({ memories: [] });
    mocks.deleteLongTermMemory.mockResolvedValue(undefined);

    render(<MemoryInspectorTab />);
    await screen.findByText(/timezone: Asia\/Ho_Chi_Minh/i);

    await user.click(screen.getByTitle(/delete memory|xóa ghi nhớ/i));

    await waitFor(() => expect(mocks.deleteLongTermMemory).toHaveBeenCalledWith('user.timezone', 'access-token'));
  });

  it('edits a memory through the API and refetches the list', async () => {
    const user = userEvent.setup();
    const edited = { ...confirmed, version: 2, value: 'UTC+07:00' };
    mocks.listLongTermMemory
      .mockResolvedValueOnce({ memories: [confirmed] })
      .mockResolvedValueOnce({ memories: [edited] });
    mocks.editLongTermMemory.mockResolvedValue(edited);

    render(<MemoryInspectorTab />);
    await screen.findByText(/timezone: Asia\/Ho_Chi_Minh/i);
    await user.click(screen.getByRole('button', { name: /view details|xem chi tiết/i }));
    await user.click(screen.getByRole('button', { name: /edit memory|sửa ghi nhớ/i }));
    const editor = screen.getByRole('textbox', { name: /memory value|giá trị ghi nhớ/i });
    await user.clear(editor);
    await user.type(editor, 'UTC+07:00');
    await user.click(screen.getByRole('button', { name: /save new version|lưu phiên bản mới/i }));

    await waitFor(() =>
      expect(mocks.editLongTermMemory).toHaveBeenCalledWith('user.timezone', 'UTC+07:00', 'access-token'),
    );
    await waitFor(() => expect(mocks.listLongTermMemory).toHaveBeenCalledTimes(2));
  });

  it('resets all learned memory only after confirmation', async () => {
    const user = userEvent.setup();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    mocks.listLongTermMemory
      .mockResolvedValueOnce({ memories: [confirmed] })
      .mockResolvedValueOnce({ memories: [] });
    mocks.clearLongTermMemory.mockResolvedValue(undefined);

    render(<MemoryInspectorTab />);
    await screen.findByText(/timezone: Asia\/Ho_Chi_Minh/i);
    await user.click(screen.getByRole('button', { name: /reset learned memory|reset điều đã nhớ/i }));

    await waitFor(() => expect(mocks.clearLongTermMemory).toHaveBeenCalledWith('access-token'));
  });

  it('shows a mutation error instead of silently failing', async () => {
    const user = userEvent.setup();
    mocks.listLongTermMemory.mockResolvedValue({ memories: [candidate] });
    mocks.confirmLongTermMemory.mockRejectedValue(new Error('offline'));

    render(<MemoryInspectorTab />);
    await screen.findByText(/response style: concise/i);
    await user.click(screen.getByRole('button', { name: /confirm|xác nhận/i }));

    expect((await screen.findByRole('alert')).textContent).toMatch(/could not|không thực hiện/i);
  });
});
