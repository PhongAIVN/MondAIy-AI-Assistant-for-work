// @vitest-environment jsdom

import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

import { translations } from '../src/i18n/translations';
import { PolicyPage } from '../src/pages/marketing/PolicyPage';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi, language: 'vi' }),
}));

describe('PolicyPage', () => {
  afterEach(cleanup);

  it('renders every detailed policy section with its title and body', () => {
    render(
      <MemoryRouter>
        <PolicyPage />
      </MemoryRouter>,
    );

    for (const section of translations.vi.marketing.policySections) {
      expect(screen.getByRole('heading', { name: section.title })).toBeTruthy();
      expect(screen.getByText(section.paragraphs[0])).toBeTruthy();
    }
    expect(screen.getByText(translations.vi.marketing.policyUpdated)).toBeTruthy();
  });

  it('keeps the English and Vietnamese section lists the same length', () => {
    expect(translations.en.marketing.policySections.length).toBe(
      translations.vi.marketing.policySections.length,
    );
  });

  it('hides paragraphs after the preview until the reader expands the section', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <PolicyPage />
      </MemoryRouter>,
    );

    const dataSection = translations.vi.marketing.policySections.find(
      (section) => section.paragraphs.length > 1,
    );
    if (!dataSection) throw new Error('fixture cần ít nhất một section nhiều đoạn để test');
    const hiddenParagraph = dataSection.paragraphs[1];

    expect(screen.queryByText(hiddenParagraph)).toBeNull();

    const heading = screen.getByRole('heading', { name: dataSection.title });
    const sectionBlock = within(heading.parentElement as HTMLElement);
    const toggle = sectionBlock.getByRole('button', { name: translations.vi.marketing.policyExpand });
    await user.click(toggle);

    expect(sectionBlock.getByText(hiddenParagraph)).toBeTruthy();
    expect(sectionBlock.getByRole('button', { name: translations.vi.marketing.policyCollapse })).toBeTruthy();
  });
});
