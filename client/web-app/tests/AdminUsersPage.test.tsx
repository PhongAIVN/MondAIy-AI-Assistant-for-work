// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminUsersPage } from '../src/pages/admin/AdminUsersPage';

const mocks = vi.hoisted(() => ({
  listUsers: vi.fn(),
  updateUser: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string; user: { id: string } }) => unknown) =>
    selector({ accessToken: 'access-token', user: { id: 'admin-1' } }),
}));

vi.mock('../src/lib/adminApi', async () => {
  const actual = await vi.importActual<typeof import('../src/lib/adminApi')>('../src/lib/adminApi');
  return { ...actual, listUsers: mocks.listUsers, updateUser: mocks.updateUser };
});

const userRows = [
  {
    id: '1',
    email: 'a@example.com',
    displayName: 'Verified',
    role: 'participant',
    isActive: true,
    createdAt: '2026-08-01T00:00:00Z',
    lastSyncedAt: null,
    connectionCount: 1,
    runCount: 2,
    programAccessLevel: 'A',
    programCohortSlug: 'cohort-iii',
  },
  {
    id: '2',
    email: 'b@example.com',
    displayName: 'Pending',
    role: 'mentor',
    isActive: true,
    createdAt: '2026-08-02T00:00:00Z',
    lastSyncedAt: null,
    connectionCount: 1,
    runCount: 0,
    programAccessLevel: 'B',
    programCohortSlug: null,
  },
  {
    id: '3',
    email: 'c@example.com',
    displayName: 'Outside',
    role: 'participant',
    isActive: true,
    createdAt: '2026-08-03T00:00:00Z',
    lastSyncedAt: null,
    connectionCount: 0,
    runCount: 0,
    programAccessLevel: 'C',
    programCohortSlug: null,
  },
] as const;

const response = (items = userRows) => ({ items, total: items.length, limit: 100, offset: 0 });

beforeEach(() => {
  mocks.listUsers.mockReset();
  mocks.updateUser.mockReset();
  mocks.listUsers.mockResolvedValue(response());
});

afterEach(cleanup);

describe('AdminUsersPage program access classification', () => {
  it('renders distinct A/B/C classifications without collapsing pending users', async () => {
    render(<AdminUsersPage />);

    expect(await screen.findByText('Verified')).toBeTruthy();
    expect(screen.getAllByText('A').length).toBeGreaterThan(0);
    expect(screen.getAllByText('B').length).toBeGreaterThan(0);
    expect(screen.getAllByText('C').length).toBeGreaterThan(0);
    expect(screen.getByText('Chờ đối soát')).toBeTruthy();
    expect(screen.getByText('Không có quyền chương trình')).toBeTruthy();
  });

  it('sends the selected program access filter to the backend', async () => {
    const user = userEvent.setup();
    render(<AdminUsersPage />);
    await screen.findByText('Verified');

    await user.selectOptions(screen.getByLabelText('Phân loại chương trình'), 'C');

    await waitFor(() =>
      expect(mocks.listUsers).toHaveBeenLastCalledWith('access-token', {
        search: '',
        role: '',
        programAccessLevel: 'C',
        limit: 100,
      }),
    );
  });

  it('trims and saves a changed cohort assignment on blur', async () => {
    mocks.updateUser.mockResolvedValue({ ...userRows[0], programCohortSlug: 'cohort-iv' });
    const user = userEvent.setup();
    render(<AdminUsersPage />);
    await screen.findByText('Verified');

    const cohortInput = screen.getByLabelText('Cohort của a@example.com');
    await user.clear(cohortInput);
    await user.type(cohortInput, '  cohort-iv  ');
    await user.tab();

    await waitFor(() =>
      expect(mocks.updateUser).toHaveBeenCalledWith('access-token', '1', {
        programCohortSlug: 'cohort-iv',
      }),
    );
  });
});
