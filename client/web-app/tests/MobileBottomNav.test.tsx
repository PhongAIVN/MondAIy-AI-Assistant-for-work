import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { MobileBottomNav } from '../src/components/layout/MobileBottomNav';

vi.mock('../src/stores/useNotificationsStore', () => ({
  useNotificationsStore: (selector: (state: { unreadCount: () => number }) => unknown) => selector({ unreadCount: () => 2 }),
}));

describe('MobileBottomNav', () => {
  it('provides the pill navigation and routes the primary actions', async () => {
    const user = userEvent.setup();
    const onMenu = vi.fn();
    const onSearch = vi.fn();

    render(
      <MemoryRouter initialEntries={['/briefing']}>
        <MobileBottomNav onOpenMenu={onMenu} onOpenSearch={onSearch} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('navigation', { name: 'Mobile navigation' })).not.toBeNull();
    expect(screen.getByRole('link', { name: 'Home' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Notifications, 2 unread' })).not.toBeNull();
    await user.click(screen.getByRole('button', { name: 'Open menu' }));
    await user.click(screen.getByRole('button', { name: 'Search' }));
    expect(onMenu).toHaveBeenCalledOnce();
    expect(onSearch).toHaveBeenCalledOnce();
  });
});
