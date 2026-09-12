// @vitest-environment jsdom

import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';

import { translations } from '../src/i18n/translations';
import { TryChatPage } from '../src/pages/marketing/TryChatPage';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi, language: 'vi' }),
}));

const faq = translations.vi.marketing;

const setup = (embedded = false) => {
  render(
    <MemoryRouter>
      <TryChatPage embedded={embedded} />
    </MemoryRouter>,
  );
};

const setDocumentHidden = (hidden: boolean) => {
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(hidden);
  document.dispatchEvent(new Event('visibilitychange'));
};

describe('TryChatPage', () => {
  afterEach(() => {
    cleanup();
    usePreferencesStore.setState({
      accessibility: { ...usePreferencesStore.getState().accessibility, reduceMotion: false },
    });
    setDocumentHidden(false);
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('can render inline on the landing page without a back-link', () => {
    setup(true);

    expect(screen.getByRole('heading', { name: faq.tryChatTitle })).toBeTruthy();
    expect(screen.queryByRole('link', { name: translations.vi.marketing.blogBackHome })).toBeNull();
  });

  it('never renders a free-text input, since the demo only auto-plays a script', () => {
    setup();

    expect(screen.queryByRole('textbox')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Gửi' })).toBeNull();
  });

  it('auto-plays the scripted question then reveals its matching answer, without any click', async () => {
    vi.useFakeTimers();
    setup();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(700);
    });
    expect(screen.getByText(faq.tryChatFaqQ1)).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1200 + faq.tryChatFaqA1.split(' ').length * 45);
    });
    expect(screen.getByText(faq.tryChatFaqA1)).toBeTruthy();
  });

  it('cycles to the second scripted question after the first answer settles', async () => {
    vi.useFakeTimers();
    setup();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(700 + 1200 + faq.tryChatFaqA1.split(' ').length * 45 + 1700 + 700);
    });
    expect(screen.getByText(faq.tryChatFaqQ2)).toBeTruthy();
  });

  it('pauses and clears the transcript while the tab is hidden, then restarts fresh once visible again', async () => {
    // Trước đây setTimeout ở tab nền bị trình duyệt throttle mạnh, khiến chuỗi
    // reveal-từng-từ chồng lấn khi quay lại tab và lặp lại câu hỏi/đáp nhiều
    // lần liền nhau. Giờ auto-play phải dừng hẳn (không đặt thêm timer nào)
    // ngay khi ẩn tab, và chạy lại sạch từ câu 1 khi hiện lại.
    vi.useFakeTimers();
    setup();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(700 + 1200 + faq.tryChatFaqA1.split(' ').length * 45);
    });
    expect(screen.getByText(faq.tryChatFaqQ1)).toBeTruthy();

    await act(async () => {
      setDocumentHidden(true);
    });
    expect(screen.queryByText(faq.tryChatFaqQ1)).toBeNull();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(screen.queryByText(faq.tryChatFaqQ1)).toBeNull();
    expect(screen.queryByText(faq.tryChatFaqQ2)).toBeNull();

    await act(async () => {
      setDocumentHidden(false);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(700);
    });
    expect(screen.getByText(faq.tryChatFaqQ1)).toBeTruthy();
    expect(screen.queryByText(faq.tryChatFaqQ2)).toBeNull();
  });

  it('shows a single static example with no auto-play loop when motion is disabled', async () => {
    usePreferencesStore.setState({
      accessibility: { ...usePreferencesStore.getState().accessibility, reduceMotion: true },
    });
    setup();

    expect(screen.getByText(faq.tryChatFaqQ1)).toBeTruthy();
    expect(screen.getByText(faq.tryChatFaqA1)).toBeTruthy();
    expect(screen.queryByText(faq.tryChatFaqQ2)).toBeNull();
  });
});
