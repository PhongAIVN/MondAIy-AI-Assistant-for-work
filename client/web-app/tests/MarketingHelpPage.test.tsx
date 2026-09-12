// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

import { translations } from '../src/i18n/translations';
import { MarketingHelpPage } from '../src/pages/marketing/MarketingHelpPage';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi, language: 'vi' }),
}));

describe('MarketingHelpPage', () => {
  afterEach(cleanup);

  it('documents Meeting Notes and Routines alongside the existing FAQ', () => {
    render(
      <MemoryRouter>
        <MarketingHelpPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: translations.vi.helpPage.q6 })).toBeTruthy();
    expect(screen.getByText(translations.vi.helpPage.a6)).toBeTruthy();
    expect(screen.getByRole('heading', { name: translations.vi.helpPage.q7 })).toBeTruthy();
    expect(screen.getByText(translations.vi.helpPage.a7)).toBeTruthy();
  });

  it('keeps English and Vietnamese FAQ entries in sync', () => {
    const enKeys = Object.keys(translations.en.helpPage);
    const viKeys = Object.keys(translations.vi.helpPage);
    expect(viKeys.sort()).toEqual(enKeys.sort());
  });
});
