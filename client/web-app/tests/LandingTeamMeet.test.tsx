// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { translations } from '../src/i18n/translations';
import { LandingTeamMeet } from '../src/components/marketing/LandingSections';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi }),
}));

describe('LandingTeamMeet', () => {
  afterEach(cleanup);

  it.each([
    ['Thái Hoài An', 'https://ahtportfolio.vercel.app/'],
    ['Nguyễn Văn Phong', 'https://nguyenvanphong.net/'],
    ['Lê Thị Yến Nhi', 'https://portfoliolynn.vercel.app/'],
    ['Nguyễn Đức Dũng', 'https://www.nddung.io.vn/'],
  ])('links %s to the correct portfolio', (name, href) => {
    render(<LandingTeamMeet />);

    const link = screen.getByRole('link', { name: `${name} portfolio` });
    expect(link.getAttribute('href')).toBe(href);
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noreferrer');
  });

  it('uses chat-oriented sidebar labels in both languages', () => {
    expect(translations.en.nav.newBriefing).toBe('New Chat');
    expect(translations.en.briefing.history.title).toBe('Recent');
    expect(translations.vi.nav.newBriefing).toBe('Đoạn trò chuyện mới');
    expect(translations.vi.briefing.history.title).toBe('Gần đây');
  });
});
