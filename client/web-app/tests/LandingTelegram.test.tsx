// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { LandingTelegram } from '../src/components/marketing/LandingSections';
import { translations } from '../src/i18n/translations';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi }),
}));

describe('LandingTelegram', () => {
  afterEach(cleanup);

  it('promotes mobile work tracking and opens the official bot safely', () => {
    render(<LandingTelegram />);

    expect(
      screen.getByRole('heading', { name: translations.vi.marketing.telegramTitle }),
    ).toBeTruthy();

    const link = screen.getByRole('link', {
      name: translations.vi.marketing.telegramCtaAria,
    });
    expect(link.getAttribute('href')).toBe('https://t.me/mondaiy_bot');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('shows an observable preview of reminders delivered in Telegram', () => {
    render(<LandingTelegram />);

    expect(screen.getByText(translations.vi.marketing.telegramPreviewDue)).toBeTruthy();
    expect(screen.getByText(translations.vi.marketing.telegramPreviewWaiting)).toBeTruthy();
  });
});
