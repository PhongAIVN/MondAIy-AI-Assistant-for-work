import { afterEach, describe, expect, it, vi } from 'vitest';

import { navigateToTelegramLink, openTelegramConnectWindow } from '../src/pages/SourceLibraryPage';

describe('Telegram connect navigation', () => {
  afterEach(() => vi.restoreAllMocks());

  it('opens a reusable window synchronously and severs its opener', () => {
    const popup = { opener: window } as unknown as Window;
    const open = vi.spyOn(window, 'open').mockReturnValue(popup);

    expect(openTelegramConnectWindow()).toBe(popup);
    expect(open).toHaveBeenCalledWith('about:blank', 'mondaiy-telegram');
    expect(popup.opener).toBeNull();
  });

  it('navigates the prepared popup to the one-time bot deep link', () => {
    const popup = { location: { href: 'about:blank' } } as unknown as Window;

    navigateToTelegramLink(popup, 'https://t.me/mondaiy_bot?start=link_token');

    expect(popup.location.href).toBe('https://t.me/mondaiy_bot?start=link_token');
  });
});
