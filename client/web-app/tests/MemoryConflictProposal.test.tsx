// @vitest-environment jsdom

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryConflictProposal } from '../src/components/privacy/MemoryConflictProposal';

const memory = (key: string, version: number, value: string) => ({
  key, version, kind: 'profile', subject: 'user', predicate: 'working_on', value,
  status: 'disputed' as const, source: 'inferred' as const, confidence: 0.8,
  reinforcementCount: 1, negativeFeedbackCount: 0, firstObservedAt: '2026-08-23T00:00:00Z',
  lastReinforcedAt: '2026-08-23T00:00:00Z', evidence: [],
});

describe('MemoryConflictProposal', () => {
  it('lets the user keep one version or delete the memory', async () => {
    const user = userEvent.setup();
    const onChoose = vi.fn();
    const onDelete = vi.fn();
    render(<MemoryConflictProposal memories={[memory('key', 1, 'P004'), memory('key', 2, 'P005')]} language="vi" busyKey={null} onChoose={onChoose} onDelete={onDelete} />);
    await user.click(screen.getByRole('button', { name: 'Giữ phiên bản v1' }));
    await user.click(screen.getByRole('button', { name: 'Xoá toàn bộ memory (đang xem v1)' }));
    expect(onChoose).toHaveBeenCalledWith('key', 1);
    expect(onDelete).toHaveBeenCalledWith('key');
  });
});
