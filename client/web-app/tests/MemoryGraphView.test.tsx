// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MemoryGraphView } from '../src/components/privacy/MemoryGraphView';

const mocks = vi.hoisted(() => ({
  fetchMemoryGraph: vi.fn(),
  useAuthStore: vi.fn(() => 'access-token'),
}));

vi.mock('../src/lib/memoryApi', () => ({ fetchMemoryGraph: mocks.fetchMemoryGraph }));
vi.mock('../src/stores/useAuthStore', () => ({ useAuthStore: mocks.useAuthStore }));

describe('MemoryGraphView', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('renders memory, source and conflict relationships from the graph API', async () => {
    mocks.fetchMemoryGraph.mockResolvedValue({
      nodes: [
        { id: 'memory:1', label: 'working on: P004', nodeType: 'memory', status: 'disputed', metadata: {} },
        { id: 'memory:2', label: 'working on: P005', nodeType: 'memory', status: 'disputed', metadata: {} },
        { id: 'source:user_input:first', label: 'first', nodeType: 'source', metadata: {} },
      ],
      edges: [
        { id: 'conflict:1:2', source: 'memory:1', target: 'memory:2', type: 'conflict', label: 'xung đột' },
        { id: 'evidence:1', source: 'memory:1', target: 'source:user_input:first', type: 'evidence', label: 'evidence' },
      ],
    });

    render(<MemoryGraphView language="vi" />);
    await waitFor(() => expect(mocks.fetchMemoryGraph).toHaveBeenCalledWith('access-token'));
    expect(screen.getByRole('img', { name: 'Đồ thị quan hệ bộ nhớ' })).toBeTruthy();
    expect(screen.getByText(/3 nút · 2 liên kết/)).toBeTruthy();
    expect(screen.getByText('xung đột')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Phóng to' })).toBeTruthy();
    expect(screen.getByText('100%')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Phóng to' }));
    expect(screen.getByText('115%')).toBeTruthy();
  });
});
